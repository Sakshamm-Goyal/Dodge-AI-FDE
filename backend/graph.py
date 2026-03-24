"""NetworkX graph construction from SQLite data."""
from __future__ import annotations

import sqlite3
import networkx as nx


NODE_TYPES = {
    "SalesOrder": {"prefix": "SO", "color": "#3b82f6"},
    "Delivery": {"prefix": "DL", "color": "#10b981"},
    "BillingDocument": {"prefix": "BD", "color": "#f59e0b"},
    "JournalEntry": {"prefix": "JE", "color": "#8b5cf6"},
    "Payment": {"prefix": "PM", "color": "#ec4899"},
    "Customer": {"prefix": "CU", "color": "#ef4444"},
    "Product": {"prefix": "PR", "color": "#06b6d4"},
    "Plant": {"prefix": "PL", "color": "#84cc16"},
}


def build_graph(conn: sqlite3.Connection) -> nx.DiGraph:
    """Build a NetworkX directed graph from SQLite data."""
    G = nx.DiGraph()

    # Add Sales Order nodes
    cursor = conn.execute("SELECT salesOrder, salesOrderType, soldToParty, totalNetAmount, transactionCurrency, overallDeliveryStatus, creationDate FROM sales_order_headers")
    for row in cursor.fetchall():
        node_id = f"SO:{row[0]}"
        G.add_node(node_id, type="SalesOrder", label=f"SO {row[0]}", id=row[0],
                   salesOrderType=row[1], soldToParty=row[2], totalNetAmount=row[3],
                   currency=row[4], deliveryStatus=row[5], creationDate=row[6])

    # Add Delivery nodes
    cursor = conn.execute("SELECT deliveryDocument, shippingPoint, creationDate, actualGoodsMovementDate FROM outbound_delivery_headers")
    for row in cursor.fetchall():
        node_id = f"DL:{row[0]}"
        G.add_node(node_id, type="Delivery", label=f"DL {row[0]}", id=row[0],
                   shippingPoint=row[1], creationDate=row[2], goodsMovementDate=row[3])

    # Add Billing Document nodes
    cursor = conn.execute("SELECT billingDocument, billingDocumentType, soldToParty, totalNetAmount, transactionCurrency, billingDocumentIsCancelled, accountingDocument, creationDate FROM billing_document_headers")
    for row in cursor.fetchall():
        node_id = f"BD:{row[0]}"
        G.add_node(node_id, type="BillingDocument", label=f"BD {row[0]}", id=row[0],
                   billingDocumentType=row[1], soldToParty=row[2], totalNetAmount=row[3],
                   currency=row[4], isCancelled=row[5], accountingDocument=row[6], creationDate=row[7])

    # Add Journal Entry nodes (grouped by accountingDocument)
    cursor = conn.execute("""
        SELECT DISTINCT accountingDocument, companyCode, fiscalYear, glAccount,
               transactionCurrency, amountInTransactionCurrency, postingDate, accountingDocumentType
        FROM journal_entry_items_accounts_receivable
    """)
    seen_je = set()
    for row in cursor.fetchall():
        doc_id = row[0]
        if doc_id in seen_je:
            continue
        seen_je.add(doc_id)
        node_id = f"JE:{doc_id}"
        G.add_node(node_id, type="JournalEntry", label=f"JE {doc_id}", id=doc_id,
                   companyCode=row[1], fiscalYear=row[2], glAccount=row[3],
                   currency=row[4], amount=row[5], postingDate=row[6], documentType=row[7])

    # Add Payment nodes
    cursor = conn.execute("""
        SELECT DISTINCT accountingDocument, companyCode, fiscalYear,
               amountInTransactionCurrency, transactionCurrency, clearingDate, customer
        FROM payments_accounts_receivable
    """)
    seen_pm = set()
    for row in cursor.fetchall():
        doc_id = row[0]
        if doc_id in seen_pm:
            continue
        seen_pm.add(doc_id)
        node_id = f"PM:{doc_id}"
        G.add_node(node_id, type="Payment", label=f"PM {doc_id}", id=doc_id,
                   companyCode=row[1], fiscalYear=row[2], amount=row[3],
                   currency=row[4], clearingDate=row[5], customer=row[6])

    # Add Customer nodes
    cursor = conn.execute("SELECT businessPartner, businessPartnerName, businessPartnerCategory, creationDate FROM business_partners")
    for row in cursor.fetchall():
        node_id = f"CU:{row[0]}"
        G.add_node(node_id, type="Customer", label=row[1] or f"CU {row[0]}", id=row[0],
                   name=row[1], category=row[2], creationDate=row[3])

    # Add Product nodes
    cursor = conn.execute("""
        SELECT p.product, pd.productDescription, p.productType, p.baseUnit
        FROM products p
        LEFT JOIN product_descriptions pd ON p.product = pd.product AND pd.language = 'EN'
    """)
    for row in cursor.fetchall():
        node_id = f"PR:{row[0]}"
        G.add_node(node_id, type="Product", label=row[1] or f"PR {row[0]}", id=row[0],
                   description=row[1], productType=row[2], baseUnit=row[3])

    # Add Plant nodes
    cursor = conn.execute("SELECT plant, plantName, valuationArea FROM plants")
    for row in cursor.fetchall():
        node_id = f"PL:{row[0]}"
        G.add_node(node_id, type="Plant", label=row[1] or f"PL {row[0]}", id=row[0],
                   plantName=row[1], valuationArea=row[2])

    # --- EDGES ---

    # SalesOrder → Customer (SOLD_TO)
    cursor = conn.execute("SELECT salesOrder, soldToParty FROM sales_order_headers WHERE soldToParty IS NOT NULL")
    for row in cursor.fetchall():
        src, tgt = f"SO:{row[0]}", f"CU:{row[1]}"
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, type="SOLD_TO")

    # SalesOrder → Product (HAS_ITEM)
    cursor = conn.execute("SELECT DISTINCT salesOrder, material FROM sales_order_items WHERE material IS NOT NULL")
    for row in cursor.fetchall():
        src, tgt = f"SO:{row[0]}", f"PR:{row[1]}"
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, type="HAS_ITEM")

    # SalesOrder → Delivery (DELIVERED_BY)
    cursor = conn.execute("""
        SELECT DISTINCT odi.referenceSdDocument, odi.deliveryDocument
        FROM outbound_delivery_items odi
        WHERE odi.referenceSdDocument IS NOT NULL
    """)
    for row in cursor.fetchall():
        src, tgt = f"SO:{row[0]}", f"DL:{row[1]}"
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, type="DELIVERED_BY")

    # Delivery → BillingDocument (BILLED_IN)
    cursor = conn.execute("""
        SELECT DISTINCT bdi.referenceSdDocument, bdi.billingDocument
        FROM billing_document_items bdi
        WHERE bdi.referenceSdDocument IS NOT NULL
    """)
    for row in cursor.fetchall():
        src, tgt = f"DL:{row[0]}", f"BD:{row[1]}"
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, type="BILLED_IN")

    # Delivery → Plant (FROM_PLANT)
    cursor = conn.execute("SELECT DISTINCT deliveryDocument, plant FROM outbound_delivery_items WHERE plant IS NOT NULL")
    for row in cursor.fetchall():
        src, tgt = f"DL:{row[0]}", f"PL:{row[1]}"
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, type="FROM_PLANT")

    # BillingDocument → JournalEntry (POSTED_AS)
    cursor = conn.execute("""
        SELECT bdh.billingDocument, bdh.accountingDocument
        FROM billing_document_headers bdh
        WHERE bdh.accountingDocument IS NOT NULL AND bdh.accountingDocument != ''
    """)
    for row in cursor.fetchall():
        src = f"BD:{row[0]}"
        tgt = f"JE:{row[1]}"
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, type="POSTED_AS")

    # JournalEntry → Payment (CLEARED_BY)
    cursor = conn.execute("""
        SELECT DISTINCT je.accountingDocument, p.accountingDocument
        FROM journal_entry_items_accounts_receivable je
        JOIN payments_accounts_receivable p ON p.clearingAccountingDocument = je.accountingDocument
        WHERE p.clearingAccountingDocument IS NOT NULL AND p.clearingAccountingDocument != ''
    """)
    for row in cursor.fetchall():
        src, tgt = f"JE:{row[0]}", f"PM:{row[1]}"
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, type="CLEARED_BY")

    return G


def graph_to_json(G: nx.DiGraph, limit: int = 500, entity_type: str = "all") -> dict:
    """Convert graph to JSON for frontend consumption."""
    nodes = []
    for node_id, data in G.nodes(data=True):
        if entity_type != "all" and data.get("type") != entity_type:
            continue
        nodes.append({
            "id": node_id,
            "type": data.get("type", "Unknown"),
            "label": data.get("label", node_id),
            "metadata": {k: v for k, v in data.items() if k not in ("type", "label")},
        })
        if len(nodes) >= limit:
            break

    node_ids = {n["id"] for n in nodes}
    edges = []
    for src, tgt, data in G.edges(data=True):
        if src in node_ids and tgt in node_ids:
            edges.append({
                "source": src,
                "target": tgt,
                "type": data.get("type", "RELATED"),
            })

    return {"nodes": nodes, "edges": edges, "total": G.number_of_nodes()}


def get_node_detail(G: nx.DiGraph, node_id: str) -> dict | None:
    """Get full details for a single node."""
    if not G.has_node(node_id):
        return None
    data = dict(G.nodes[node_id])
    neighbors = list(G.neighbors(node_id)) + list(G.predecessors(node_id))
    return {
        "id": node_id,
        "type": data.get("type", "Unknown"),
        "label": data.get("label", node_id),
        "metadata": {k: v for k, v in data.items() if k not in ("type", "label")},
        "connections": len(set(neighbors)),
    }


def expand_node(G: nx.DiGraph, node_id: str) -> dict:
    """Get neighbors of a node for graph expansion."""
    if not G.has_node(node_id):
        return {"nodes": [], "edges": []}

    neighbor_ids = set(G.neighbors(node_id)) | set(G.predecessors(node_id))
    nodes = []
    for nid in neighbor_ids:
        data = dict(G.nodes[nid])
        nodes.append({
            "id": nid,
            "type": data.get("type", "Unknown"),
            "label": data.get("label", nid),
            "metadata": {k: v for k, v in data.items() if k not in ("type", "label")},
        })

    edges = []
    all_ids = neighbor_ids | {node_id}
    for src, tgt, data in G.edges(data=True):
        if src in all_ids and tgt in all_ids:
            edges.append({"source": src, "target": tgt, "type": data.get("type", "RELATED")})

    return {"nodes": nodes, "edges": edges}


def find_broken_flows(G: nx.DiGraph) -> list[dict]:
    """Find sales orders with incomplete O2C flows."""
    broken = []
    for node_id, data in G.nodes(data=True):
        if data.get("type") != "SalesOrder":
            continue

        so_id = data.get("id", node_id)
        has_delivery = False
        has_billing = False
        has_journal = False
        delivery_ids = []
        billing_ids = []

        # Check successors
        for neighbor in G.neighbors(node_id):
            ndata = G.nodes[neighbor]
            ntype = ndata.get("type")
            if ntype == "Delivery":
                has_delivery = True
                delivery_ids.append(neighbor)
            elif ntype == "Customer":
                pass  # expected
            elif ntype == "Product":
                pass  # expected

        # Check delivery successors
        for dl_id in delivery_ids:
            for neighbor in G.neighbors(dl_id):
                ndata = G.nodes[neighbor]
                if ndata.get("type") == "BillingDocument":
                    has_billing = True
                    billing_ids.append(neighbor)

        # Check billing successors
        for bd_id in billing_ids:
            for neighbor in G.neighbors(bd_id):
                ndata = G.nodes[neighbor]
                if ndata.get("type") == "JournalEntry":
                    has_journal = True

        if not has_delivery or not has_billing or not has_journal:
            issues = []
            if not has_delivery:
                issues.append("no delivery")
            if has_delivery and not has_billing:
                issues.append("delivered but not billed")
            if has_billing and not has_journal:
                issues.append("billed but no journal entry")
            broken.append({
                "salesOrder": so_id,
                "nodeId": node_id,
                "issues": issues,
            })

    return broken
