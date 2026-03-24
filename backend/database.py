"""SQLite database setup and JSONL data ingestion."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", "o2c.db")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "sap-o2c-data"))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _infer_type(value) -> str:
    if value is None:
        return "TEXT"
    if isinstance(value, bool):
        return "INTEGER"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    if isinstance(value, (dict, list)):
        return "TEXT"  # store as JSON string
    return "TEXT"


def _serialize_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if isinstance(value, bool):
        return 1 if value else 0
    return value


def ingest_data(data_dir: str = DATA_DIR, db_path: str = DB_PATH) -> dict:
    """Ingest all JSONL files from data_dir into SQLite tables. Returns row counts."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    data_path = Path(data_dir)
    row_counts = {}

    for entity_dir in sorted(data_path.iterdir()):
        if not entity_dir.is_dir() or entity_dir.name.startswith("."):
            continue

        table_name = entity_dir.name
        jsonl_files = sorted(entity_dir.glob("*.jsonl"))
        if not jsonl_files:
            continue

        # Read all records
        records = []
        for jf in jsonl_files:
            with open(jf, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

        if not records:
            continue

        # Infer schema from first 100 records
        all_columns = {}
        for rec in records[:100]:
            for key, value in rec.items():
                if key not in all_columns:
                    all_columns[key] = _infer_type(value)
                elif value is not None and all_columns[key] == "TEXT":
                    inferred = _infer_type(value)
                    if inferred != "TEXT":
                        all_columns[key] = inferred

        columns = list(all_columns.keys())
        col_types = [all_columns[c] for c in columns]

        # Create table
        col_defs = ", ".join(
            f'"{c}" {t}' for c, t in zip(columns, col_types)
        )
        conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        conn.execute(f'CREATE TABLE "{table_name}" ({col_defs})')

        # Insert records
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join('"{}"'.format(c) for c in columns)
        insert_sql = 'INSERT INTO "{}" ({}) VALUES ({})'.format(table_name, col_names, placeholders)

        batch = []
        for rec in records:
            row = tuple(_serialize_value(rec.get(c)) for c in columns)
            batch.append(row)

        conn.executemany(insert_sql, batch)
        conn.commit()
        row_counts[table_name] = len(batch)

    conn.close()
    return row_counts


def get_schema(conn: sqlite3.Connection) -> dict:
    """Get database schema info for LLM context."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = []
    for (table_name,) in cursor.fetchall():
        col_cursor = conn.execute(f'PRAGMA table_info("{table_name}")')
        columns = [
            {"name": row[1], "type": row[2]} for row in col_cursor.fetchall()
        ]
        count_cursor = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        row_count = count_cursor.fetchone()[0]
        tables.append({
            "name": table_name,
            "columns": columns,
            "rowCount": row_count,
        })
    return {"tables": tables}


def get_sample_rows(conn: sqlite3.Connection, table_name: str, limit: int = 3) -> list[dict]:
    """Get sample rows from a table for LLM context."""
    cursor = conn.execute(f'SELECT * FROM "{table_name}" LIMIT ?', (limit,))
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def validate_fk_relationships(conn: sqlite3.Connection) -> list[dict]:
    """Validate all FK relationships and return match counts."""
    relationships = [
        {
            "name": "SalesOrder → Delivery",
            "sql": """
                SELECT COUNT(*) as matches FROM outbound_delivery_items odi
                JOIN sales_order_headers soh ON odi.referenceSdDocument = soh.salesOrder
            """,
        },
        {
            "name": "Delivery → BillingDocument",
            "sql": """
                SELECT COUNT(*) as matches FROM billing_document_items bdi
                JOIN outbound_delivery_headers odh ON bdi.referenceSdDocument = odh.deliveryDocument
            """,
        },
        {
            "name": "BillingDocument → JournalEntry",
            "sql": """
                SELECT COUNT(*) as matches FROM billing_document_headers bdh
                JOIN journal_entry_items_accounts_receivable je ON bdh.accountingDocument = je.accountingDocument
            """,
        },
        {
            "name": "SalesOrder → Customer",
            "sql": """
                SELECT COUNT(*) as matches FROM sales_order_headers soh
                JOIN business_partners bp ON soh.soldToParty = bp.businessPartner
            """,
        },
        {
            "name": "SalesOrder → Product (via items)",
            "sql": """
                SELECT COUNT(*) as matches FROM sales_order_items soi
                JOIN products p ON soi.material = p.product
            """,
        },
        {
            "name": "Delivery → Plant",
            "sql": """
                SELECT COUNT(*) as matches FROM outbound_delivery_items odi
                JOIN plants pl ON odi.plant = pl.plant
            """,
        },
    ]

    results = []
    for rel in relationships:
        try:
            cursor = conn.execute(rel["sql"])
            matches = cursor.fetchone()[0]
            results.append({"name": rel["name"], "matches": matches, "status": "OK" if matches > 0 else "NO_MATCHES"})
        except Exception as e:
            results.append({"name": rel["name"], "matches": 0, "status": f"ERROR: {e}"})

    return results


if __name__ == "__main__":
    print("Ingesting data...")
    counts = ingest_data()
    print("\nRow counts:")
    for table, count in sorted(counts.items()):
        print(f"  {table}: {count}")

    print("\nValidating FK relationships...")
    conn = get_connection()
    results = validate_fk_relationships(conn)
    for r in results:
        status = "OK" if r["status"] == "OK" else r["status"]
        print(f"  {r['name']}: {r['matches']} matches [{status}]")
    conn.close()
