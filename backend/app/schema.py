import logging
from app.db import graph_for
from app.config import settings

logger = logging.getLogger(__name__)

ID_INDEX_LABELS = [
    "Service",
    "Person",
    "Team",
    "Customer",
    "Incident",
    "Doc",
    "Decision",
    "Ticket",
    "Thread",
    "Episode",
    "Fact",
    "Procedure",
    "Run",
    "Task",
    "Action",
    "Answer",
    "Conversation",
    "Msg",
]

EXTRA_RANGE_INDEXES = [
    ("Task", "status"),
    ("Task", "run_id"),
    ("Fact", "subject_id"),
]

VECTOR_INDEXES = [
    ("Incident", "embedding"),
    ("Doc", "embedding"),
    ("Episode", "embedding"),
    ("Fact", "embedding"),
    ("Procedure", "embedding"),
]


def ensure_schema(tenant: str) -> None:
    """
    Idempotently sets up range and vector indexes for the tenant graph.
    Catches 'already indexed' errors cleanly.
    """
    g = graph_for(tenant)

    # 1. Range indexes on id
    for label in ID_INDEX_LABELS:
        cypher = f"CREATE INDEX FOR (n:{label}) ON (n.id)"
        try:
            g.query(cypher)
        except Exception as e:
            if "already indexed" not in str(e).lower():
                raise e

    # 2. Extra range indexes
    for label, prop in EXTRA_RANGE_INDEXES:
        cypher = f"CREATE INDEX FOR (n:{label}) ON (n.{prop})"
        try:
            g.query(cypher)
        except Exception as e:
            if "already indexed" not in str(e).lower():
                raise e

    # 3. Vector indexes (768-dim, cosine similarity)
    dim = settings.EMBED_DIM
    for label, prop in VECTOR_INDEXES:
        cypher = (
            f"CREATE VECTOR INDEX FOR (n:{label}) ON (n.{prop}) "
            f"OPTIONS {{dimension: {dim}, similarityFunction: 'cosine'}}"
        )
        try:
            g.query(cypher)
        except Exception as e:
            if "already indexed" not in str(e).lower():
                raise e
