import sys
import os
from pathlib import Path

# Add backend to path so we can import app if needed
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from falkordb import FalkorDB
from app.config import settings


def main():
    print("=== FALKORDB SMOKE TEST & PROBE ===")
    kwargs = {"host": settings.FALKORDB_HOST, "port": settings.FALKORDB_PORT}
    if settings.FALKORDB_USERNAME:
        kwargs["username"] = settings.FALKORDB_USERNAME
    if settings.FALKORDB_PASSWORD:
        kwargs["password"] = settings.FALKORDB_PASSWORD

    try:
        db = FalkorDB(**kwargs)
    except Exception as e:
        print(f"FAIL: Could not connect to FalkorDB at {settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}: {e}")
        sys.exit(1)

    graph_name = "probe"
    g = db.select_graph(graph_name)

    all_passed = True

    try:
        # a) Parameterized create and match
        try:
            g.query("CREATE (n:TestNode {id: $id, name: $name})", {"id": "n1", "name": "Node One"})
            res = g.query("MATCH (n:TestNode {id: $id}) RETURN n.name", {"id": "n1"})
            assert res.result_set and res.result_set[0][0] == "Node One"
            print("a) Parameterized CREATE and MATCH: PASS")
        except Exception as e:
            print(f"a) Parameterized CREATE and MATCH: FAIL ({e})")
            all_passed = False

        # b) Variable-length path [:DEPENDS_ON*1..3] over a 3-node chain
        try:
            g.query(
                "CREATE (a:Service {id: 's1', name: 'S1'})-[:DEPENDS_ON]->"
                "(b:Service {id: 's2', name: 'S2'})-[:DEPENDS_ON]->"
                "(c:Service {id: 's3', name: 'S3'})"
            )
            res = g.query("MATCH p = (a:Service {id: 's1'})-[:DEPENDS_ON*1..3]->(c:Service {id: 's3'}) RETURN length(p)")
            assert res.result_set and res.result_set[0][0] == 2
            print("b) Variable-length path [:DEPENDS_ON*1..3]: PASS")
        except Exception as e:
            print(f"b) Variable-length path [:DEPENDS_ON*1..3]: FAIL ({e})")
            all_passed = False

        # c) ShortestPath between two bound nodes
        try:
            res = g.query(
                "MATCH (a:Service {id: 's1'}), (c:Service {id: 's3'}) "
                "WITH shortestPath((a)-[:DEPENDS_ON*]->(c)) AS p RETURN length(p)"
            )
            assert res.result_set and res.result_set[0][0] == 2
            print("c) shortestPath between bound nodes: PASS")
        except Exception as e:
            print(f"c) shortestPath between bound nodes: FAIL ({e})")
            all_passed = False

        # d) List comprehension over nodes(p)
        try:
            res = g.query(
                "MATCH (a:Service {id: 's1'}), (c:Service {id: 's3'}) "
                "WITH shortestPath((a)-[:DEPENDS_ON*]->(c)) AS p "
                "RETURN [n IN nodes(p) | n.id] AS ids"
            )
            assert res.result_set and res.result_set[0][0] == ["s1", "s2", "s3"]
            print("d) List comprehension over nodes(p): PASS")
        except Exception as e:
            print(f"d) List comprehension over nodes(p): FAIL ({e})")
            all_passed = False

        # e) LIMIT with a parameter ($k)
        try:
            res = g.query("MATCH (s:Service) RETURN s.id ORDER BY s.id LIMIT $k", {"k": 2})
            assert res.result_set and len(res.result_set) == 2
            print("e) LIMIT with parameter ($k): PASS")
        except Exception as e:
            print(f"e) LIMIT with parameter ($k): FAIL ({e})")
            all_passed = False

        # f) MERGE ... ON CREATE SET ... ON MATCH SET
        try:
            res1 = g.query(
                "MERGE (m:Item {id: $id}) "
                "ON CREATE SET m.created = 1 "
                "ON MATCH SET m.updated = 1 "
                "RETURN m.created, m.updated",
                {"id": "item1"}
            )
            created_val = res1.result_set[0][0]

            res2 = g.query(
                "MERGE (m:Item {id: $id}) "
                "ON CREATE SET m.created = 1 "
                "ON MATCH SET m.updated = 1 "
                "RETURN m.created, m.updated",
                {"id": "item1"}
            )
            updated_val = res2.result_set[0][1]

            assert created_val == 1 and updated_val == 1
            print("f) MERGE ON CREATE / ON MATCH SET: PASS")
        except Exception as e:
            print(f"f) MERGE ON CREATE / ON MATCH SET: FAIL ({e})")
            all_passed = False

        # g) algo.pageRank and algo.betweenness
        try:
            pr_res = g.query("CALL algo.pageRank('Service', 'DEPENDS_ON') YIELD node, score")
            assert len(pr_res.result_set) > 0

            bw_res = g.query("CALL algo.betweenness({nodeLabels: ['Service'], relationshipTypes: ['DEPENDS_ON']}) YIELD node, score")
            assert len(bw_res.result_set) > 0
            print("g) algo.pageRank and algo.betweenness: PASS")
        except Exception as e:
            print(f"g) algo.pageRank and algo.betweenness: FAIL ({e})")
            all_passed = False

        # h) Vector index of dimension 4 with cosine, three stored vectors via vecf32, and db.idx.vector.queryNodes
        try:
            # Create index
            try:
                g.query("CREATE VECTOR INDEX FOR (v:VecItem) ON (v.vec) OPTIONS {dimension: 4, similarityFunction: 'cosine'}")
            except Exception as ie:
                if "already indexed" not in str(ie).lower():
                    raise ie

            v1 = [1.0, 0.0, 0.0, 0.0]
            v2 = [0.0, 1.0, 0.0, 0.0]
            v3 = [0.7071, 0.7071, 0.0, 0.0]

            g.query("CREATE (v:VecItem {id: 'v1', vec: vecf32($vec)})", {"vec": v1})
            g.query("CREATE (v:VecItem {id: 'v2', vec: vecf32($vec)})", {"vec": v2})
            g.query("CREATE (v:VecItem {id: 'v3', vec: vecf32($vec)})", {"vec": v3})

            query_vec = [1.0, 0.0, 0.0, 0.0]
            vec_res = g.query(
                "CALL db.idx.vector.queryNodes('VecItem', 'vec', $k, vecf32($query)) YIELD node, score RETURN node.id, score",
                {"k": 3, "query": query_vec}
            )

            print("   Vector query results for target [1, 0, 0, 0]:")
            scores = {}
            for row in vec_res.result_set:
                node_id, score = row[0], row[1]
                scores[node_id] = score
                is_exact = "(EXACT MATCH)" if node_id == "v1" else ""
                print(f"   Node: {node_id}, Score: {score} {is_exact}")

            # Determine semantics
            exact_score = scores.get("v1", 0.0)
            orthogonal_score = scores.get("v2", 0.0)
            if exact_score < orthogonal_score:
                semantics = "DISTANCE (smaller score means closer)"
            else:
                semantics = "SIMILARITY (larger score means closer)"
            print(f"   Vector Score Semantics: {semantics}")
            print("h) Vector index and db.idx.vector.queryNodes: PASS")
        except Exception as e:
            print(f"h) Vector index and db.idx.vector.queryNodes: FAIL ({e})")
            all_passed = False

        # i) Conditional claim query
        try:
            g.query("CREATE (t:Task {id: $id, status: 'open'})", {"id": "task_claim_test"})
            claim_cypher = (
                "MATCH (t:Task {id: $id}) WHERE t.status = 'open' "
                "SET t.status = 'claimed' "
                "RETURN t.id"
            )
            run1 = g.query(claim_cypher, {"id": "task_claim_test"})
            assert len(run1.result_set) == 1 and run1.result_set[0][0] == "task_claim_test"

            run2 = g.query(claim_cypher, {"id": "task_claim_test"})
            assert len(run2.result_set) == 0
            print("i) Conditional claim query (atomic CAS): PASS")
        except Exception as e:
            print(f"i) Conditional claim query (atomic CAS): FAIL ({e})")
            all_passed = False

    finally:
        try:
            g.delete()
            print("Probe graph cleaned up successfully.")
        except Exception as e:
            print(f"Warning: could not delete probe graph: {e}")

    if all_passed:
        print("\nAll FalkorDB checks PASSED.")
    else:
        print("\nSome FalkorDB checks FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
