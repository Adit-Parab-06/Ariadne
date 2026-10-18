"""
Ariadne: Demo Seed Statistics & Graph Inspector
Verifies and displays knowledge graph entity and relationship counts for all tenants.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db import graph_for
from app.seed.load import load_tenant


def inspect_tenant(tenant: str):
    g = graph_for(tenant)
    print(f"\n==========================================")
    print(f"TENANT: {tenant.upper()}")
    print(f"==========================================")

    # Node counts by label
    node_res = g.ro_query(
        "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC"
    )
    print("Node Entities:")
    total_nodes = 0
    for row in node_res.result_set:
        print(f"  - {row[0]}: {row[1]}")
        total_nodes += row[1]
    print(f"  Total Nodes: {total_nodes}")

    # Relationship counts by type
    rel_res = g.ro_query(
        "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count ORDER BY count DESC"
    )
    print("\nRelationship Edges:")
    total_edges = 0
    for row in rel_res.result_set:
        print(f"  - [:{row[0]}]: {row[1]}")
        total_edges += row[1]
    print(f"  Total Edges: {total_edges}")

    # Vector index check
    idx_res = g.ro_query("CALL db.indexes()")
    print("\nIndexes in Graph:")
    for row in (idx_res.result_set or []):
        print(f"  - {row}")


def main():
    print("Seeding all tenants (Northwind + Acme)...")
    load_tenant("northwind", reset=True)
    load_tenant("acme", reset=True)
    print("Seed complete.")

    inspect_tenant("northwind")
    inspect_tenant("acme")


if __name__ == "__main__":
    main()
