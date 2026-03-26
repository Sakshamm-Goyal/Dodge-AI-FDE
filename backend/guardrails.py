"""Multi-layer guardrails for query validation.

Layer 0: Input sanitization (Unicode normalization, length limits)
Layer 1: Fast blocklist (prompt injection + clearly off-topic, no LLM cost)
Layer 2: LLM system prompt restriction (built into llm.py)
Layer 3: SQL output validation (safety, correctness, anti-exfiltration)
"""
from __future__ import annotations

import re
import unicodedata
import sqlparse

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

MAX_QUERY_LENGTH = 2000

# --- Layer 0: Input sanitization ---

def sanitize_input(query: str) -> str:
    """Normalize input to prevent Unicode bypass attacks.

    Strips zero-width characters, normalizes homoglyphs (e.g. Cyrillic 'а' → Latin 'a'),
    and enforces length limits. Without this, regex blocklists can be trivially bypassed.
    """
    # Strip zero-width and invisible Unicode characters
    query = re.sub(r'[\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff\u00ad]', '', query)
    # Normalize Unicode homoglyphs (NFKC maps look-alikes to canonical forms)
    query = unicodedata.normalize('NFKC', query)
    # Collapse excessive whitespace
    query = re.sub(r'\s+', ' ', query).strip()
    # Length limit
    if len(query) > MAX_QUERY_LENGTH:
        query = query[:MAX_QUERY_LENGTH]
    return query


# --- Layer 1: Blocklist-based fast rejection ---

# Prompt injection / role override attempts
_INJECTION_PATTERNS = [
    # Classic role override
    r"ignore\s+(all\s+)?(previous|prior|above|your)",
    r"forget\s+(all\s+)?(previous|prior|above|your)",
    r"disregard\s+(all\s+)?(previous|prior|above|your)",
    r"you\s+are\s+now\b",
    r"act\s+as\b",
    r"pretend\s+(to\s+be|you)",
    r"new\s+role",
    r"override\s+(instruction|rule|mode)",
    r"admin\s+(mode|access|command)",
    r"developer\s+mode",
    r"jailbreak",
    r"do\s+anything\s+now",
    r"DAN\b",
    # 2025-era injection patterns
    r"repeat\s+after\s+me",
    r"roleplay\s+as",
    r"from\s+now\s+on",
    r"IMPORTANT\s*:",
    r"<\s*system\s*>",
    r"\[INST\]",
    r"###\s*(system|instruction|human|assistant)",
    r"respond\s+(only\s+)?in\s+(json|xml|html)\b",
    # System prompt extraction
    r"system\s*prompt",
    r"show\s+(me\s+)?(your|the)\s+(instruction|prompt|rules)",
    r"what\s+are\s+your\s+(instruction|rules|guidelines)",
    r"reveal\s+(your\s+)?(instruction|prompt|system)",
]

# Clearly off-topic requests (no ambiguity — these are never O2C)
_OFFTOPIC_PATTERNS = [
    r"\b(weather|forecast|temperature)\s+(in|for|today|tomorrow)\b",
    r"\bwrite\s+(me\s+)?(a\s+)?(poem|story|essay|song|code|script|letter|email)\b",
    r"\b(compose|generate)\s+(a\s+)?(poem|story|essay|song|lyrics)\b",
    r"\btranslate\s+.+\s+(to|into)\s+\w+",
    r"\b(recipe|cook|bake|ingredient)\b.*\b(for|how)\b",
    r"\b(who\s+is|tell\s+me\s+about)\s+(elon|trump|biden|modi|taylor|obama)\b",
    r"\b(capital|president|population)\s+of\s+\w+",
    r"\bhello\s+world\b",
    r"\b(play|sing|hum)\s+(me\s+)?(a\s+)?song\b",
    r"\b(what\s+is\s+the\s+meaning\s+of\s+life)\b",
    r"\btell\s+(me\s+)?a\s+joke\b",
    r"\b(tic\s*tac\s*toe|chess|game)\b",
]

# Compiled for performance
_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]
_OFFTOPIC_RE = [re.compile(p, re.IGNORECASE) for p in _OFFTOPIC_PATTERNS]


def check_domain_relevance(query: str, has_history: bool = False) -> tuple[bool, str | None]:
    """Layer 1: Blocklist-based fast rejection.

    Strategy: block what's clearly wrong, let everything else through to the LLM.
    The LLM system prompt (Layer 2) handles nuanced domain filtering — it's far
    better at understanding intent, typos, and abbreviations than regex.

    This avoids false rejections while still catching:
    - Prompt injection attempts (security)
    - Obviously off-topic requests (saves API cost)
    """
    # Layer 0: sanitize first
    query_clean = sanitize_input(query)

    # Empty or single-char queries
    if len(query_clean) < 2:
        return False, REJECTION_MESSAGE

    # Block prompt injection attempts — always, regardless of history
    for pattern in _INJECTION_RE:
        if pattern.search(query_clean):
            return False, REJECTION_MESSAGE

    # Block clearly off-topic requests
    for pattern in _OFFTOPIC_RE:
        if pattern.search(query_clean):
            return False, REJECTION_MESSAGE

    # Everything else goes to Layer 2 (LLM with domain-restricted system prompt)
    return True, None


# --- Layer 3: SQL output validation ---

def validate_sql(sql: str) -> tuple[bool, str | None]:
    """Validate generated SQL for safety, correctness, and anti-exfiltration."""
    if not sql or not sql.strip():
        return False, "No SQL generated"

    sql_upper = sql.strip().upper()

    # Only allow SELECT statements
    if not sql_upper.lstrip().startswith("SELECT"):
        return False, "Only SELECT queries are allowed"

    # Dangerous write/DDL operations
    dangerous_patterns = [
        r'\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE|REPLACE)\b',
        r'\b(ATTACH|DETACH)\b',
        r'\b(PRAGMA)\b',
        r';\s*(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE)',
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, sql_upper):
            return False, "Only SELECT queries are allowed for safety"

    # SQLite exfiltration / introspection protection
    exfiltration_patterns = [
        r'\bsqlite_master\b',
        r'\bsqlite_version\b',
        r'\bsqlite_temp_master\b',
        r'\bLOAD_EXTENSION\b',
        r'\bfts[345]\b',
        r'\bRANDOMBLOB\b',
        r'\bZEROBLOB\b',
        r'\breadfile\b',
        r'\bwritefile\b',
    ]
    for pattern in exfiltration_patterns:
        if re.search(pattern, sql, re.IGNORECASE):
            return False, "Access to system tables is not allowed"

    # Parse SQL for basic validity
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return False, "Could not parse SQL"
    except Exception:
        return False, "SQL parsing failed"

    # Validate table references against known schema
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
