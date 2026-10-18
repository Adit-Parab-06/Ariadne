from typing import Optional, List, Any
from falkordb import FalkorDB
from app.config import settings

_db: Optional[FalkorDB] = None
VALID_TENANTS = {"northwind", "acme"}


def get_db() -> FalkorDB:
    """Returns a cached FalkorDB client connection."""
    global _db
    if _db is None:
        kwargs: dict[str, Any] = {
            "host": settings.FALKORDB_HOST,
            "port": settings.FALKORDB_PORT,
        }
        if settings.FALKORDB_USERNAME:
            kwargs["username"] = settings.FALKORDB_USERNAME
        if settings.FALKORDB_PASSWORD:
            kwargs["password"] = settings.FALKORDB_PASSWORD
        _db = FalkorDB(**kwargs)
    return _db


def graph_for(tenant: str):
    """Returns graph for the given tenant ('northwind' or 'acme'). Raises ValueError otherwise."""
    if tenant not in VALID_TENANTS:
        raise ValueError(f"Invalid tenant '{tenant}'. Allowed tenants are: {', '.join(sorted(VALID_TENANTS))}")
    db = get_db()
    return db.select_graph(f"ariadne_{tenant}")


def q(tenant: str, cypher: str, params: Optional[dict] = None, readonly: bool = False) -> list[list]:
    """
    Executes a parameterized Cypher query against the specified tenant's graph.
    Uses g.ro_query when readonly=True, otherwise g.query.
    Returns result_set (list of rows). Never format values into Cypher strings.
    """
    g = graph_for(tenant)
    p = params if params is not None else {}
    if readonly:
        res = g.ro_query(cypher, p)
    else:
        res = g.query(cypher, p)
    return res.result_set if res.result_set is not None else []
