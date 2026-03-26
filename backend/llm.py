"""Gemini LLM integration for NL→SQL pipeline with streaming."""
from __future__ import annotations

import asyncio
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
        "sales_order_headers", "sales_order_items",
        "outbound_delivery_headers", "outbound_delivery_items",
        "billing_document_headers", "billing_document_items",
        "journal_entry_items_accounts_receivable",
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
- sales_order_items.salesOrder = sales_order_headers.salesOrder (order items link)
- sales_order_items.material = products.product (product link)
- outbound_delivery_items.referenceSdDocument = sales_order_headers.salesOrder (delivery→order)
- billing_document_items.referenceSdDocument = outbound_delivery_headers.deliveryDocument (billing→delivery)
- billing_document_headers.accountingDocument = journal_entry_items_accounts_receivable.accountingDocument (billing→journal)
- payments_accounts_receivable.clearingAccountingDocument = journal_entry_items_accounts_receivable.accountingDocument (payment→journal)
- outbound_delivery_items.plant = plants.plant (delivery→plant)

CRITICAL JOIN PATTERNS (use these exact queries as templates):

1. Products with most billing documents (SIMPLEST — billing_document_items has material column directly):
```sql
SELECT bdi.material, pd.productDescription, COUNT(DISTINCT bdi.billingDocument) AS billingCount
FROM billing_document_items bdi
JOIN products p ON bdi.material = p.product
LEFT JOIN product_descriptions pd ON p.product = pd.product AND pd.language = 'EN'
WHERE bdi.material IS NOT NULL AND bdi.material != ''
GROUP BY bdi.material, pd.productDescription
ORDER BY billingCount DESC
LIMIT 10
```

2. Trace full O2C flow for a billing document (e.g., 90504259):
```sql
SELECT bdh.billingDocument, bdi.referenceSdDocument AS deliveryDoc,
       odi.referenceSdDocument AS salesOrder, bdh.accountingDocument AS journalEntry,
       bdh.totalNetAmount, bdh.transactionCurrency
FROM billing_document_headers bdh
JOIN billing_document_items bdi ON bdh.billingDocument = bdi.billingDocument
LEFT JOIN outbound_delivery_items odi ON bdi.referenceSdDocument = odi.deliveryDocument
WHERE bdh.billingDocument = '90504259'
```

3. Sales orders with broken/incomplete flows:
```sql
SELECT soh.salesOrder, soh.totalNetAmount,
       CASE WHEN odi.deliveryDocument IS NULL THEN 'No delivery' ELSE 'Delivered' END AS deliveryStatus,
       CASE WHEN bdi.billingDocument IS NULL THEN 'Not billed' ELSE 'Billed' END AS billingStatus
FROM sales_order_headers soh
LEFT JOIN outbound_delivery_items odi ON odi.referenceSdDocument = soh.salesOrder
LEFT JOIN billing_document_items bdi ON bdi.referenceSdDocument = odi.deliveryDocument
WHERE odi.deliveryDocument IS NULL OR bdi.billingDocument IS NULL
GROUP BY soh.salesOrder
```

IMPORTANT:
- billing_document_items has a direct 'material' column — use it for product lookups, no need to chain through deliveries
- billing_document_items.referenceSdDocument links to deliveryDocument (NOT salesOrder directly)
- To go from billing to sales order, chain through delivery items
- product_descriptions uses language = 'EN' (not 'E')
- journal_entry_items_accounts_receivable has referenceDocument which may store billing doc number
- billingDocumentIsCancelled flag on billing_document_headers indicates cancelled invoices
- Always use table names exactly as shown (with underscores)
- For COUNT queries, always include the actual count column with a clear alias
"""

    return f"""You are a SAP Order-to-Cash (O2C) data analyst. You help users explore an SAP O2C dataset in SQLite.

YOUR RULES:
1. ONLY answer questions about the SAP O2C dataset. For anything unrelated, respond EXACTLY with: "{REJECTION_MESSAGE}"
2. Generate SQLite-compatible SQL to answer data questions. Always wrap SQL in ```sql blocks.
3. Write efficient SQL — use JOINs from the relationship map below.
4. After the SQL block, write a brief explanation of what the query does.
5. When results mention specific documents, include their IDs for graph highlighting.
6. For "trace the flow" queries, find all connected entities in the O2C chain.
7. For "broken/incomplete flow" queries, use LEFT JOINs and IS NULL checks.
8. Always use exact table and column names from the schema. Never invent column names.
9. Use GROUP BY with aggregate functions, ORDER BY for rankings, LIMIT for top-N queries.
10. For ambiguous queries, make reasonable assumptions and explain them.

{schema_text}
{sample_text}
{relationship_text}"""


def _get_model(primary: bool = True, system_instruction: str = None):
    """Get a Gemini model instance."""
    model_name = PRIMARY_MODEL if primary else FALLBACK_MODEL
    return genai.GenerativeModel(model_name, system_instruction=system_instruction)


def _call_gemini(model, messages, temperature=0.1, max_tokens=2048):
    """Synchronous Gemini call (will be run in thread pool)."""
    response = model.generate_content(
        messages,
        generation_config=genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text


def _stream_gemini(model, messages, temperature=0.1, max_tokens=1024):
    """Synchronous streaming Gemini call — yields text chunks."""
    response = model.generate_content(
        messages,
        generation_config=genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
        stream=True,
    )
    for chunk in response:
        if chunk.text:
            yield chunk.text


async def process_chat_query(query: str, session_id: str, conn: sqlite3.Connection):
    """Process a chat query and yield SSE events."""
    # Layer 1: Domain relevance check (keyword-based, fast)
    has_history = len(conversations[session_id]) > 0
    is_relevant, rejection = check_domain_relevance(query, has_history=has_history)
    if not is_relevant:
        yield {"event": "result", "data": {"answer": rejection, "nodeIds": [], "sql": None}}
        yield {"event": "done", "data": {}}
        return

    system_prompt = _build_system_prompt(conn)

    # Build conversation context
    history = conversations[session_id][-MAX_HISTORY:]
    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "parts": [msg["content"]]})
    messages.append({"role": "user", "parts": [query]})

    # Store user message
    conversations[session_id].append({"role": "user", "content": query})
    if len(conversations[session_id]) > MAX_HISTORY:
        conversations[session_id] = conversations[session_id][-MAX_HISTORY:]

    # Layer 2: LLM call with domain-restricted system prompt
    full_text = None
    for attempt_primary in [True, False]:
        try:
            model = _get_model(primary=attempt_primary, system_instruction=system_prompt)
            # Run blocking Gemini call in thread pool to not block event loop
            full_text = await asyncio.to_thread(
                _call_gemini, model, messages, 0.1, 2048
            )
            break
        except Exception as e:
            error_str = str(e)
            print(f"[LLM ERROR] {'Primary' if attempt_primary else 'Fallback'} model failed: {e}")
            if attempt_primary and ("429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower()):
                continue  # Try fallback
            # Final failure
            yield {"event": "error", "data": {"message": "I'm having trouble connecting to the AI service. Please check the API key and try again."}}
            yield {"event": "done", "data": {}}
            return

    if not full_text:
        yield {"event": "error", "data": {"message": "No response from AI. Please try again."}}
        yield {"event": "done", "data": {}}
        return

    # Extract and execute SQL (Layer 3: SQL validation)
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
                sql_results = [dict(zip(columns, row)) for row in rows[:100]]
                node_ids = _extract_node_ids(sql_results, columns)
            except Exception as e:
                print(f"[SQL ERROR] {e}\nSQL: {sql}")
                # SQL failed — ask LLM to retry with a simpler query
                retry_messages = messages + [
                    {"role": "model", "parts": [full_text]},
                    {"role": "user", "parts": [
                        f"The SQL query failed with error: {e}\n"
                        "Please fix the SQL query. Use only the exact table and column names from the schema. "
                        "Make sure all JOINs use correct column names."
                    ]},
                ]
                try:
                    model = _get_model(primary=True, system_instruction=system_prompt)
                    retry_text = await asyncio.to_thread(
                        _call_gemini, model, retry_messages, 0.1, 2048
                    )
                    retry_sql = extract_sql_from_response(retry_text)
                    if retry_sql:
                        is_valid2, _ = validate_sql(retry_sql)
                        if is_valid2:
                            yield {"event": "sql", "data": {"sql": retry_sql}}
                            cursor2 = conn.execute(retry_sql)
                            columns2 = [desc[0] for desc in cursor2.description] if cursor2.description else []
                            rows2 = cursor2.fetchall()
                            sql_results = [dict(zip(columns2, row)) for row in rows2[:100]]
                            sql = retry_sql
                            node_ids = _extract_node_ids(sql_results, columns2)
                            full_text = retry_text
                except Exception:
                    pass  # Retry also failed — use original LLM text as answer
        else:
            print(f"[SQL VALIDATION] Rejected: {error}\nSQL: {sql}")

    # Generate clean answer — stream it token by token
    if sql_results is not None and len(sql_results) > 0:
        # Summarize results with streaming
        result_preview = json.dumps(sql_results[:20], default=str)
        summary_prompt = f"""The user asked: "{query}"

SQL executed: {sql}

Results ({len(sql_results)} rows, showing up to 20):
{result_preview}

IMPORTANT: Answer ONLY based on the actual result data above. Do NOT use information from prior conversation or memory.
Report the EXACT values (names, IDs, amounts) from the result rows — do not substitute or guess.

Write a clear, concise answer:
- State the key findings with specific numbers and document IDs from the results
- Use bold (**text**) for important values
- If there are multiple results, present them as a brief list
- Do NOT include any SQL in your answer
- Keep it under 200 words"""

        model = _get_model(
            primary=True,
            system_instruction="You are a data analyst. Summarize SQL query results clearly and accurately. Use ONLY the data provided in the results — never guess or use prior context. Be concise and specific. Use bold for key values.",
        )

        # Stream the summary token by token via async queue
        answer_chunks = []
        try:
            queue: asyncio.Queue = asyncio.Queue()

            def _run_stream():
                try:
                    for chunk in _stream_gemini(model, [{"role": "user", "parts": [summary_prompt]}], 0.2, 1024):
                        queue.put_nowait(chunk)
                finally:
                    queue.put_nowait(None)  # sentinel

            # Start streaming in background thread
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, _run_stream)

            # Yield chunks as they arrive
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                answer_chunks.append(chunk)
                yield {"event": "token", "data": {"token": chunk}}
        except Exception:
            # Fallback: strip SQL blocks from original response
            fallback = re.sub(r'```sql.*?```', '', full_text, flags=re.DOTALL).strip()
            answer_chunks = [fallback]
            yield {"event": "token", "data": {"token": fallback}}

        answer = "".join(answer_chunks)
    else:
        # No SQL results — clean up the response (remove SQL blocks)
        answer = re.sub(r'```sql.*?```', '', full_text, flags=re.DOTALL).strip()
        if not answer:
            answer = full_text
        yield {"event": "token", "data": {"token": answer}}

    # Store assistant response in conversation memory
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
    seen = set()
    node_ids = []

    col_to_prefix = {
        "salesorder": "SO", "salesOrder": "SO",
        "deliverydocument": "DL", "deliveryDocument": "DL",
        "billingdocument": "BD", "billingDocument": "BD",
        "accountingdocument": "JE", "accountingDocument": "JE",
        "businesspartner": "CU", "businessPartner": "CU",
        "soldtoparty": "CU", "soldToParty": "CU",
        "customer": "CU",
        "product": "PR", "material": "PR",
        "plant": "PL",
        "referencedocument": "BD", "referenceDocument": "BD",
        "clearingaccountingdocument": "PM", "clearingAccountingDocument": "PM",
        "referencesddocument": "DL", "referenceSdDocument": "DL",
    }

    for row in results:
        for col, value in row.items():
            prefix = col_to_prefix.get(col) or col_to_prefix.get(col.lower())
            if prefix and value:
                node_id = f"{prefix}:{value}"
                if node_id not in seen:
                    seen.add(node_id)
                    node_ids.append(node_id)

    return node_ids[:50]
