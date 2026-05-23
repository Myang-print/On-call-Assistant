from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    doc_id: str
    raw_html: str
    title: str
    cleaned_text: str
