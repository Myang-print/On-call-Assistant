from pathlib import Path

from app.html_parser import parse_html_document
from app.models import Document
from app.settings import DATA_DIR


def load_documents_from_data_dir(data_dir: Path = DATA_DIR) -> list[Document]:
    documents: list[Document] = []

    # Stable filename ordering keeps deterministic load and search behavior.
    for html_file in sorted(Path(data_dir).glob("*.html")):
        raw_html = html_file.read_text(encoding="utf-8")
        documents.append(parse_html_document(doc_id=html_file.stem, raw_html=raw_html))

    return documents


class DocumentStore:
    def __init__(self, documents: list[Document]) -> None:
        # Store an in-memory snapshot so later file changes cannot affect active queries.
        self._documents_by_id = {document.doc_id: document for document in documents}

    @classmethod
    def from_data_dir(cls, data_dir: Path = DATA_DIR) -> "DocumentStore":
        return cls(load_documents_from_data_dir(data_dir))

    def get(self, doc_id: str) -> Document | None:
        return self._documents_by_id.get(doc_id)

    def all(self) -> list[Document]:
        # Return a container copy to prevent callers from mutating store internals.
        return list(self._documents_by_id.values())
