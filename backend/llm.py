"""Gemini LLM integration for NL→SQL pipeline with streaming."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from collections import defaultdict

import google.generativeai as genai

from .database import get_schema, get_sample_rows
from .guardrails import check_domain_relevance, validate_sql, extract_sql_from_response, REJECTION_MESSAGE

# Configure Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-2.0-flash-lite"

# In-memory conversation store
conversations: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY = 10


def _build_system_prompt(conn: sqlite3.Connection) -> str:
    """Build schema-aware system prompt for Gemini."""
    schema = get_schema(conn)

    schema_text = "DATABASE SCHEMA:\n"
    for table in schema["tables"]:
        cols = ", ".join(f'{c["name"]} ({c["type"]})' for c in table["columns"])
        schema_text += f'\nTable: {table["name"]} ({table["rowCount"]} rows)\n  Columns: {cols}\n'

    # Add sample rows for key tables
    key_tables = [
        "sales_order_headers", "outbound_delivery_headers",
        "billing_document_headers", "journal_entry_items_accounts_receivable",
        "payments_accounts_receivable", "business_partners", "products",
    ]
    sample_text = "\nSAMPLE DATA:\n"
    for table_name in key_tables:
        try:
            samples = get_sample_rows(conn, table_name, limit=2)
            if samples:
                sample_text += f"\n{table_name} (first 2 rows):\n"
                for s in samples:
                    sample_text += f"  {json.dumps(s, default=str)}\n"
        except Exception:
            pass

    relationship_text = """
KEY RELATIONSHIPS (for JOIN queries):
- sales_order_headers.soldToParty = business_partners.businessPartner (customer link)
- sales_order_items.material = products.product (product link)
- outbound_delivery_items.referenceSdDocument = sales_order_headers.salesOrder (delivery→order)
- billing_document_items.referenceSdDocument = outbound_delivery_headers.deliveryDocument (billing→delivery)
- billing_document_headers.accountingDocument = journal_entry_items_accounts_receivable.accountingDocument (billing→journal)
- payments_accounts_receivable.clearingAccountingDocument = journal_entry_items_accounts_receivable.accountingDocument (payment→journal)
- outbound_delivery_items.plant = plants.plant (delivery→plant)
- sales_order_items.material = products.product (order→product)

IMPORTANT NOTES:
- The billing_document_items.referenceSdDocument links to outbound_delivery_headers.deliveryDocument (NOT directly to sales orders)
- To trace a full flow from billing to sales order, chain: billing_document_items → outbound_delivery_items → sales_order_headers
- journal_entry_items has referenceDocument which stores the billing document number
- billingDocumentIsCancelled flag indicates cancelled invoices
"""

    return f"""You are a SAP Order-to-Cash (O2C) data analyst assistant. You help users explore and query an SAP O2C dataset stored in a SQLite database.

RULES:
1. ONLY answer questions about the SAP Order-to-Cash dataset. If asked about anything unrelated (general knowledge, creative writing, coding), respond with: "{REJECTION_MESSAGE}"
2. Generate SQLite-compatible SQL queries to answer data questions
3. Always wrap your SQL in ```sql code blocks
4. After the SQL, explain the results in plain language
5. When mentioning specific documents, include their IDs so they can be highlighted in the graph
6. Use proper JOINs based on the relationships below
7. Always use double quotes around table names that contain special characters

{schema_text}
{sample_text}
{relationship_text}"""


def _get_model(primary: bool = True, system_instruction: str = None):
    """Get a Gemini model instance."""
    model_name = PRIMARY_MODEL if primary else FALLBACK_MODEL
    return genai.GenerativeModel(model_name, system_instruction=system_instruction)


async def process_chat_query(query: str, session_id: str, conn: sqlite3.Connection):
    """Process a chat query and yield SSE events.

    Yields dicts with event type and data for SSE streaming.
    """
    # Layer 1: Domain relevance check
    is_relevant, rejection = check_domain_relevance(query)
    if not is_relevant:
        yield {"event": "result", "data": {"answer": rejection, "nodeIds": [], "sql": None}}
        yield {"event": "done", "data": {}}
        return

    system_prompt = _build_system_prompt(conn)

    # Build conversation history
    history = conversations[session_id][-MAX_HISTORY:]
    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "parts": [msg["content"]]})
    messages.append({"role": "user", "parts": [query]})

    # Store user message
    conversations[session_id].append({"role": "user", "content": query})
    if len(conversations[session_id]) > MAX_HISTORY:
        conversations[session_id] = conversations[session_id][-MAX_HISTORY:]

    try:
        model = _get_model(primary=True, system_instruction=system_prompt)
        response = model.generate_content(
            messages,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2048,
            ),
        )
        full_text = response.text
    except Exception as e:
        print(f"[LLM ERROR] Primary model failed: {e}")
        error_str = str(e)
        if "429" in error_str or "quota" in error_str.lower():
            # Fallback to lite model
            try:
                model = _get_model(primary=False, system_instruction=system_prompt)
                response = model.generate_content(
                    messages,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=2048,
                    ),
                )
                full_text = response.text
            except Exception as e2:
                print(f"[LLM ERROR] Fallback model also failed: {e2}")
                yield {"event": "error", "data": {"message": "I'm having trouble processing that query. Please try again."}}
                yield {"event": "done", "data": {}}
                return
        else:
            yield {"event": "error", "data": {"message": "I'm having trouble processing that query. Please try again."}}
            yield {"event": "done", "data": {}}
            return

    # Extract and execute SQL
    sql = extract_sql_from_response(full_text)
    sql_results = None
    node_ids = []

    if sql:
        is_valid, error = validate_sql(sql)
        if is_valid:
            yield {"event": "sql", "data": {"sql": sql}}
            try:
                cursor = conn.execute(sql)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                sql_results = [dict(zip(columns, row)) for row in rows[:100]]  # Cap at 100 rows

                # Extract node IDs from results
                node_ids = _extract_node_ids(sql_results, columns)
            except Exception as e:
                sql_results = None
                yield {"event": "error", "data": {"message": f"SQL execution returned an error. Let me try rephrasing."}}

    # If we have SQL results, generate a natural language summary
    answer = full_text
    if sql_results is not None:
        # Re-prompt with results for a clean summary
        try:
            result_text = json.dumps(sql_results[:20], default=str)
            summary_prompt = f"""The user asked: "{query}"

I ran this SQL: {sql}

Results ({len(sql_results)} rows, showing first 20):
{result_text}

Provide a clear, concise answer based on these results. Include specific document numbers and amounts. Do not include SQL in your response."""

            model = _get_model(
                primary=True,
                system_instruction="You are a data analyst. Summarize query results clearly and concisely. Mention specific numbers and document IDs.",
            )
            summary_response = model.generate_content(
                [{"role": "user", "parts": [summary_prompt]}],
                generation_config=genai.types.GenerationConfig(temperature=0.1, max_output_tokens=1024),
            )
            answer = summary_response.text
        except Exception:
            # Use original response if summary fails
            pass

    # Store assistant response
    conversations[session_id].append({"role": "model", "content": answer})

    yield {"event": "result", "data": {
        "answer": answer,
        "nodeIds": node_ids,
        "sql": sql,
        "resultCount": len(sql_results) if sql_results else 0,
    }}
    yield {"event": "done", "data": {}}


def _extract_node_ids(results: list[dict], columns: list[str]) -> list[str]:
    """Extract node IDs from SQL results for graph highlighting."""
    node_ids = []

    # Column name → node type prefix mapping
    col_to_prefix = {
        "salesOrder": "SO", "salesorder": "SO",
        "deliveryDocument": "DL", "deliverydocument": "DL",
        "billingDocument": "BD", "billingdocument": "BD",
        "accountingDocument": "JE", "accountingdocument": "JE",
        "businessPartner": "CU", "businesspartner": "CU",
        "soldToParty": "CU", "soldtoparty": "CU",
        "customer": "CU",
        "product": "PR", "material": "PR",
        "plant": "PL",
    }

    for row in results:
        for col, value in row.items():
            prefix = col_to_prefix.get(col) or col_to_prefix.get(col.lower())
            if prefix and value:
                node_id = f"{prefix}:{value}"
                if node_id not in node_ids:
                    node_ids.append(node_id)

    return node_ids[:50]  # Cap at 50 highlighted nodes
