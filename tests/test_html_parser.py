import logging

from app.html_parser import parse_html_document
from app.models import Document


logger = logging.getLogger(__name__)


def test_parser_preserves_raw_html_and_extracts_cleaned_text() -> None:
    html = """
    <html>
      <head><title>Backend SOP</title></head>
      <body>
        <h1>Ignored When Title Exists</h1>
        <p>Service OOM response steps.</p>
      </body>
    </html>
    """

    document = parse_html_document(doc_id="sop-001", raw_html=html)

    logger.info(
        "doc_id=%s title=%s cleaned_text=%s",
        document.doc_id,
        document.title,
        document.cleaned_text,
    )
    assert isinstance(document, Document)
    assert document.doc_id == "sop-001"
    assert document.raw_html == html
    assert document.title == "Backend SOP"
    assert "Service OOM response steps." in document.cleaned_text
    assert "<p>" not in document.cleaned_text


def test_parser_removes_script_style_and_noscript_content() -> None:
    html = """
    <html>
      <head>
        <title>DBA SOP</title>
        <style>.hidden { color: red; } style-only-token</style>
        <script>const hidden = "replication";</script>
      </head>
      <body>
        <noscript>noscript-only-token</noscript>
        <p>数据库主从延迟处理步骤。</p>
      </body>
    </html>
    """

    document = parse_html_document(doc_id="sop-002", raw_html=html)

    logger.info("cleaned_text=%s", document.cleaned_text)
    assert "数据库主从延迟处理步骤。" in document.cleaned_text
    assert "replication" not in document.cleaned_text
    assert "style-only-token" not in document.cleaned_text
    assert "noscript-only-token" not in document.cleaned_text


def test_parser_uses_h1_title_when_title_tag_is_missing() -> None:
    html = """
    <html>
      <body>
        <h1>Frontend On-Call SOP</h1>
        <p>CDN failure response.</p>
      </body>
    </html>
    """

    document = parse_html_document(doc_id="sop-003", raw_html=html)

    logger.info("title=%s", document.title)
    assert document.title == "Frontend On-Call SOP"


def test_parser_falls_back_to_doc_id_when_title_and_h1_are_missing() -> None:
    html = "<html><body><p>Untitled SOP body.</p></body></html>"

    document = parse_html_document(doc_id="sop-unknown", raw_html=html)

    logger.info("title=%s", document.title)
    assert document.title == "sop-unknown"
