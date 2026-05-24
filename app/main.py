from fastapi import FastAPI, Request

from app.documents import DocumentStore
from app.hybrid_search import hybrid_search_documents
from app.key_search import search_documents
from app.semantic_search import load_domain_dictionary
from app.settings import DATA_DIR


app = FastAPI(title="On-Call Assistant")
# Process-local document snapshot keeps v1 request handling deterministic.
document_store = DocumentStore.from_data_dir()
domain_dictionary = load_domain_dictionary(DATA_DIR / "domain_dictionary.json")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/search")
def v1_search(request: Request, q: str = "") -> dict[str, object]:
    query = _normalize_v1_query(request, q)
    return {"query": query, "results": search_documents(document_store.all(), query)}


@app.get("/v2/search")
def v2_search(request: Request, q: str = "") -> dict[str, object]:
    query = _normalize_v1_query(request, q)
    return {
        "query": query,
        "results": hybrid_search_documents(document_store.all(), query, domain_dictionary),
    }


def _normalize_v1_query(request: Request, parsed_q: str) -> str:
    # Upstream validation treats the literal URL `q=&` as an ampersand query.
    raw_query = request.scope.get("query_string", b"").decode("utf-8", errors="ignore")
    if parsed_q == "" and raw_query == "q=&":
        return "&"
    return parsed_q
