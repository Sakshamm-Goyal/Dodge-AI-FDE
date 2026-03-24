"""3-layer guardrails for query validation."""
from __future__ import annotations

import re
import sqlparse

# O2C domain keywords for Layer 1 check
O2C_KEYWORDS = {
    "order", "sales", "delivery", "billing", "invoice", "payment", "journal",
    "customer", "product", "plant", "material", "document", "amount", "currency",
    "shipped", "delivered", "billed", "posted", "cleared", "cancelled",
    "o2c", "order to cash", "sap", "erp", "flow", "trace", "broken",
    "incomplete", "status", "total", "net", "gross", "quantity", "date",
    "fiscal", "company", "account", "receivable", "credit", "debit",
    "partner", "business", "address", "storage", "warehouse",
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


def check_domain_relevance(query: str) -> tuple[bool, str | None]:
    """Layer 1: Check if query is related to O2C domain using keywords.
    Returns (is_relevant, rejection_message_or_none).
    """
    query_lower = query.lower()
    for keyword in O2C_KEYWORDS:
        if keyword in query_lower:
            return True, None

    # Check for document numbers (numeric patterns that might be IDs)
    if re.search(r'\b\d{6,}\b', query):
        return True, None

    return False, REJECTION_MESSAGE


def validate_sql(sql: str) -> tuple[bool, str | None]:
    """Layer 3: Validate generated SQL for safety and correctness.
    Returns (is_valid, error_message_or_none).
    """
    if not sql or not sql.strip():
        return False, "No SQL generated"

    sql_upper = sql.strip().upper()

    # Only allow SELECT statements
    dangerous_patterns = [
        r'\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE|REPLACE)\b',
        r'\b(ATTACH|DETACH)\b',
        r'\b(PRAGMA)\b',
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, sql_upper):
            return False, "Only SELECT queries are allowed for safety"

    if not sql_upper.lstrip().startswith("SELECT"):
        return False, "Only SELECT queries are allowed"

    # Parse and validate table references
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return False, "Could not parse SQL"
    except Exception:
        return False, "SQL parsing failed"

    # Extract table names from SQL and validate against known tables
    # Simple extraction: find words after FROM and JOIN
    table_pattern = r'(?:FROM|JOIN)\s+"?(\w+)"?'
    referenced_tables = set(re.findall(table_pattern, sql, re.IGNORECASE))

    unknown_tables = referenced_tables - KNOWN_TABLES
    if unknown_tables:
        return False, f"Unknown tables referenced: {', '.join(unknown_tables)}"

    return True, None


def extract_sql_from_response(text: str) -> str | None:
    """Extract SQL query from LLM response text."""
    # Try to find SQL in code blocks
    sql_block = re.search(r'```(?:sql)?\s*\n(.*?)\n```', text, re.DOTALL | re.IGNORECASE)
    if sql_block:
        return sql_block.group(1).strip()

    # Try to find SELECT statement directly
    select_match = re.search(r'(SELECT\s+.*?;)', text, re.DOTALL | re.IGNORECASE)
    if select_match:
        return select_match.group(1).strip()

    # Try without semicolon
    select_match = re.search(r'(SELECT\s+.+?)(?:\n\n|\Z)', text, re.DOTALL | re.IGNORECASE)
    if select_match:
        return select_match.group(1).strip()

    return None
