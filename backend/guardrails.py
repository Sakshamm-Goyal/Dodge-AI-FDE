"""3-layer guardrails for query validation.

Layer 1: Domain relevance check (keyword + pattern matching, fast, no LLM)
Layer 2: System prompt restriction (built into llm.py system prompt)
Layer 3: SQL output validation (safety + correctness)
"""
from __future__ import annotations

import re
import sqlparse

# Strong O2C domain keywords — terms that almost always indicate O2C context
# Avoids common English words like "date", "total", "status" that cause false positives
STRONG_KEYWORDS = {
    "order", "sales order", "purchase order", "delivery", "billing", "invoice",
    "payment", "journal", "journal entry", "customer", "product", "plant",
    "material", "document", "shipped", "delivered", "billed", "posted",
    "cleared", "cancelled", "o2c", "order to cash", "sap", "erp",
    "receivable", "fiscal", "warehouse", "storage", "supplier",
    "sales", "outbound", "inbound", "accounting", "ledger", "debit", "credit",
    "billing document", "delivery document", "sales order", "journal entry",
    "business partner", "company code",
}

# Weaker domain signals — only match if combined with other context
WEAK_KEYWORDS = {
    "flow", "trace", "broken", "incomplete", "amount", "currency",
    "quantity", "net", "gross", "status", "total", "date",
}

KNOWN_TABLES = {
    "sales_order_headers", "sales_order_items", "sales_order_schedule_lines",
    "outbound_delivery_headers", "outbound_delivery_items",
    "billing_document_headers", "billing_document_items", "billing_document_cancellations",
    "journal_entry_items_accounts_receivable", "payments_accounts_receivable",
    "business_partners", "business_partner_addresses",
    "customer_company_assignments", "customer_sales_area_assignments",
    "products", "product_descriptions", "product_plants", "product_storage_locations",
    "plants",
}

REJECTION_MESSAGE = (
    "This system is designed to answer questions related to the SAP Order-to-Cash "
    "dataset only. Please ask about sales orders, deliveries, billing documents, "
    "payments, customers, products, or related business processes."
)


def check_domain_relevance(query: str, has_history: bool = False) -> tuple[bool, str | None]:
    """Layer 1: Check if query is related to O2C domain.

    Uses a tiered keyword approach:
    - Strong keywords: any single match = relevant
    - Weak keywords: need 2+ matches to be relevant
    - Document number patterns: relevant (user referencing specific IDs)
    - Short follow-ups with conversation history: let LLM (Layer 2) decide
    """
    query_lower = query.lower()

    # Check for strong O2C keywords
    for keyword in STRONG_KEYWORDS:
        if keyword in query_lower:
            return True, None

    # Check for document number patterns (6+ digit IDs)
    if re.search(r'\b\d{6,}\b', query):
        return True, None

    # Check weak keywords — need at least 2 matches for relevance
    weak_count = sum(1 for kw in WEAK_KEYWORDS if kw in query_lower)
    if weak_count >= 2:
        return True, None

    # Check for table name references
    for table in KNOWN_TABLES:
        if table in query_lower or table.replace("_", " ") in query_lower:
            return True, None

    # If there's conversation history and query is short/conversational,
    # let it through to Layer 2 (LLM system prompt) — it could be a follow-up
    # like "tell me more", "show top 5", "what about cancelled ones?"
    if has_history and len(query.strip()) < 100:
        # Still block clearly off-topic attempts (prompt injection, etc.)
        off_topic_signals = [
            "write me", "compose", "poem", "story", "weather",
            "recipe", "joke", "sing", "translate", "code me",
            "hello world", "ignore", "forget", "pretend",
            "you are now", "act as", "admin", "system prompt",
        ]
        for signal in off_topic_signals:
            if signal in query_lower:
                return False, REJECTION_MESSAGE
        # Let Layer 2 handle ambiguous follow-ups
        return True, None

    return False, REJECTION_MESSAGE


def validate_sql(sql: str) -> tuple[bool, str | None]:
    """Layer 3: Validate generated SQL for safety and correctness."""
    if not sql or not sql.strip():
        return False, "No SQL generated"

    sql_upper = sql.strip().upper()

    # Only allow SELECT statements
    if not sql_upper.lstrip().startswith("SELECT"):
        return False, "Only SELECT queries are allowed"

    # Check for dangerous operations (even in subqueries)
    dangerous_patterns = [
        r'\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE|REPLACE)\b',
        r'\b(ATTACH|DETACH)\b',
        r'\b(PRAGMA)\b',
        r';\s*(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE)',  # piggyback statements
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, sql_upper):
            return False, "Only SELECT queries are allowed for safety"

    # Parse SQL for basic validity
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return False, "Could not parse SQL"
    except Exception:
        return False, "SQL parsing failed"

    # Extract and validate table references
    table_pattern = r'(?:FROM|JOIN)\s+"?(\w+)"?'
    referenced_tables = set(re.findall(table_pattern, sql, re.IGNORECASE))

    unknown_tables = referenced_tables - KNOWN_TABLES
    if unknown_tables:
        return False, f"Unknown tables referenced: {', '.join(unknown_tables)}"

    return True, None


def extract_sql_from_response(text: str) -> str | None:
    """Extract SQL query from LLM response text."""
    if not text:
        return None

    # Try to find SQL in ```sql code blocks
    sql_block = re.search(r'```(?:sql)?\s*\n(.*?)\n```', text, re.DOTALL | re.IGNORECASE)
    if sql_block:
        sql = sql_block.group(1).strip()
        if sql.upper().startswith("SELECT"):
            return sql

    # Try to find SELECT statement with semicolon
    select_match = re.search(r'(SELECT\s+.*?;)', text, re.DOTALL | re.IGNORECASE)
    if select_match:
        return select_match.group(1).strip().rstrip(';')

    # Try without semicolon — match until double newline or end
    select_match = re.search(r'(SELECT\s+.+?)(?:\n\n|\Z)', text, re.DOTALL | re.IGNORECASE)
    if select_match:
        return select_match.group(1).strip()

    return None
