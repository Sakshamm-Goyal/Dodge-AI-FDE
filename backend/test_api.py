"""Integration tests for SAP O2C Graph Explorer backend."""
from __future__ import annotations

import os
import pytest

# Ensure DB exists before tests
os.environ.setdefault("DB_PATH", "o2c.db")


def _ensure_db():
    """Ensure the database exists for tests."""
    db_path = os.environ.get("DB_PATH", "o2c.db")
    if not os.path.exists(db_path):
        from backend.database import ingest_data
        ingest_data()


class TestIngestion:
    """Test data ingestion produces correct tables and rows."""

    def setup_method(self):
        _ensure_db()
        from backend.database import get_connection
        self.conn = get_connection()

    def teardown_method(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def test_all_tables_exist(self):
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        expected = [
            "billing_document_cancellations",
            "billing_document_headers",
            "billing_document_items",
            "business_partner_addresses",
            "business_partners",
            "customer_company_assignments",
            "customer_sales_area_assignments",
            "journal_entry_items_accounts_receivable",
            "outbound_delivery_headers",
            "outbound_delivery_items",
            "payments_accounts_receivable",
            "plants",
            "product_descriptions",
            "product_plants",
            "product_storage_locations",
            "products",
            "sales_order_headers",
            "sales_order_items",
            "sales_order_schedule_lines",
        ]
        for t in expected:
            assert t in tables, f"Table {t} not found in database"

    def test_tables_have_rows(self):
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        for (table_name,) in cursor.fetchall():
            count = self.conn.execute(
                'SELECT COUNT(*) FROM "{}"'.format(table_name)
            ).fetchone()[0]
            assert count > 0, f"Table {table_name} has no rows"


class TestFKRelationships:
    """Test FK relationships produce matches."""

    def setup_method(self):
        _ensure_db()
        from backend.database import get_connection, validate_fk_relationships
        self.conn = get_connection()
        self.results = validate_fk_relationships(self.conn)

    def teardown_method(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def test_all_relationships_have_matches(self):
        for r in self.results:
            assert r["matches"] > 0, (
                f"FK relationship '{r['name']}' has 0 matches (status: {r['status']})"
            )

    def test_no_relationship_errors(self):
        for r in self.results:
            assert r["status"] != "ERROR", (
                f"FK relationship '{r['name']}' errored: {r['status']}"
            )


class TestGuardrails:
    """Test guardrails reject off-topic queries."""

    def test_reject_weather_query(self):
        from backend.guardrails import check_domain_relevance
        is_relevant, _ = check_domain_relevance("What's the weather today?")
        assert not is_relevant

    def test_reject_poetry_query(self):
        from backend.guardrails import check_domain_relevance
        is_relevant, _ = check_domain_relevance("Write me a poem about love")
        assert not is_relevant

    def test_accept_sales_order_query(self):
        from backend.guardrails import check_domain_relevance
        is_relevant, _ = check_domain_relevance("Show me all sales orders")
        assert is_relevant

    def test_accept_billing_query(self):
        from backend.guardrails import check_domain_relevance
        is_relevant, _ = check_domain_relevance(
            "Which products have the most billing documents?"
        )
        assert is_relevant

    def test_sql_validation_rejects_drop(self):
        from backend.guardrails import validate_sql
        is_valid, _ = validate_sql("DROP TABLE sales_order_headers")
        assert not is_valid

    def test_sql_validation_rejects_delete(self):
        from backend.guardrails import validate_sql
        is_valid, _ = validate_sql("DELETE FROM sales_order_headers")
        assert not is_valid

    def test_sql_validation_accepts_select(self):
        from backend.guardrails import validate_sql
        is_valid, _ = validate_sql(
            'SELECT * FROM sales_order_headers LIMIT 10'
        )
        assert is_valid


class TestGraph:
    """Test graph construction and analysis."""

    def setup_method(self):
        _ensure_db()
        from backend.database import get_connection
        from backend.graph import build_graph
        self.conn = get_connection()
        self.graph = build_graph(self.conn)

    def teardown_method(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def test_graph_has_nodes(self):
        assert self.graph.number_of_nodes() > 0

    def test_graph_has_edges(self):
        assert self.graph.number_of_edges() > 0

    def test_graph_to_json(self):
        from backend.graph import graph_to_json
        data = graph_to_json(self.graph, limit=10)
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) <= 10

    def test_broken_flows_detected(self):
        from backend.graph import find_broken_flows
        broken = find_broken_flows(self.graph)
        assert isinstance(broken, list)

    def test_expand_node(self):
        from backend.graph import expand_node
        # Pick a node that exists
        first_node = list(self.graph.nodes())[0]
        result = expand_node(self.graph, first_node)
        assert "nodes" in result
        assert "edges" in result


class TestAPI:
    """Test FastAPI endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        _ensure_db()
        # Set up global state that lifespan normally initializes
        import backend.main as main_module
        from backend.database import get_connection
        from backend.graph import build_graph
        if main_module._conn is None:
            main_module._conn = get_connection()
            main_module._graph = build_graph(main_module._conn)

    @pytest.mark.anyio
    async def test_health_endpoint(self):
        from httpx import AsyncClient, ASGITransport
        from backend.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.get("/health")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ok"

    @pytest.mark.anyio
    async def test_graph_endpoint(self):
        from httpx import AsyncClient, ASGITransport
        from backend.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.get("/api/graph?limit=10")
            assert res.status_code == 200
            data = res.json()
            assert "nodes" in data

    @pytest.mark.anyio
    async def test_schema_endpoint(self):
        from httpx import AsyncClient, ASGITransport
        from backend.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.get("/api/schema")
            assert res.status_code == 200
            data = res.json()
            assert "tables" in data

    @pytest.mark.anyio
    async def test_node_types_endpoint(self):
        from httpx import AsyncClient, ASGITransport
        from backend.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.get("/api/node-types")
            assert res.status_code == 200
