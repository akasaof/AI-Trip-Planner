
from langchain_core.tools import tool

from app.rag.retriever import get_rag


@tool
def rag_search(query: str) -> list[dict]:
    """Retrieve curated destination knowledge (transport tips, culture,
    weather patterns, neighborhoods, airport info) relevant to `query`
    (e.g. 'Dubai transport and best time to visit'). This is cached
    curated content, not a live API call."""
    return get_rag().retrieve(query, top_k=3)
