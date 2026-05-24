from bs4 import BeautifulSoup

from app.models import Document


def parse_html_document(doc_id: str, raw_html: str) -> Document:
    soup = BeautifulSoup(raw_html, "html.parser")

    # Searchable text must exclude executable and fallback-only content.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = _extract_title(soup, doc_id)
    cleaned_text = soup.get_text(separator=" ", strip=True)

    return Document(
        doc_id=doc_id,
        raw_html=raw_html,
        title=title,
        cleaned_text=cleaned_text,
    )


def _extract_title(soup: BeautifulSoup, doc_id: str) -> str:
    # Title fallback order is part of the document identity contract.
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
        if title:
            return title

    h1_tag = soup.find("h1")
    if h1_tag:
        title = h1_tag.get_text(strip=True)
        if title:
            return title

    return doc_id
