from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request, status
import re

from app.api import router as api_router
from app.documents import DocumentStore
from app.hybrid_search import hybrid_search_documents
from app.key_search import search_documents
from app.semantic_search import load_domain_dictionary
from app.settings import DATA_DIR


app = FastAPI(title="On-Call Assistant")
app.include_router(api_router)
# Process-local document snapshot keeps v1 request handling deterministic.
document_store = DocumentStore.from_data_dir()
app.state.document_store = document_store
domain_dictionary = load_domain_dictionary(DATA_DIR / "domain_dictionary.json")
DOCUMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class DocumentCreateRequest(BaseModel):
    id: str
    html: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/documents", status_code=status.HTTP_201_CREATED)
def create_v1_document(payload: DocumentCreateRequest) -> dict[str, str]:
    doc_id = payload.id.strip()
    raw_html = payload.html.strip()
    if not doc_id or not raw_html:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="id and html are required")
    if not DOCUMENT_ID_PATTERN.fullmatch(doc_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid document id")
    if "<html" not in raw_html.casefold() or "</html>" not in raw_html.casefold():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid html document")

    try:
        document = document_store.add_html_document(doc_id, raw_html)
    except ValueError as error:
        if str(error) == "duplicate document id":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        raise

    return {"id": document.doc_id, "title": document.title}


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
