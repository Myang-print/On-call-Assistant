import json
import re
from pathlib import Path

from app.documents import load_documents_from_data_dir
from app.models import Document
from app.settings import DATA_DIR


MANIFEST_FILENAME = "manifest.json"
KEYWORD_LIMIT = 8
KNOWN_KEYWORDS = [
    "OOM",
    "DDoS",
    "CDN",
    "DNS",
    "K8s",
    "GPU",
    "ETL",
    "Spark",
    "主从延迟",
    "慢查询",
    "页面白屏",
    "入侵检测",
    "自动化测试",
]


def update_manifest(
    data_dir: Path = DATA_DIR,
    manifest_path: Path | None = None,
) -> str:
    root = Path(data_dir)
    target = manifest_path or root / MANIFEST_FILENAME
    manifest = [
        {
            "doc_id": document.doc_id,
            "filename": f"{document.doc_id}.html",
            "title": document.title,
            "keywords": build_keywords(document),
        }
        for document in sorted(load_documents_from_data_dir(root), key=lambda item: item.doc_id)
    ]
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
    target.write_text(manifest_json, encoding="utf-8")
    return manifest_json


def build_keywords(document: Document) -> list[str]:
    keywords: list[str] = []
    source = f"{document.title} {document.cleaned_text}"

    for keyword in KNOWN_KEYWORDS:
        _append_keyword(keywords, keyword, source)

    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*|[\u4e00-\u9fff]{2,}", source):
        if len(token) > 12 and re.fullmatch(r"[\u4e00-\u9fff]+", token):
            for chunk in re.findall(r"[\u4e00-\u9fff]{2,4}", token):
                _append_keyword(keywords, chunk, source)
                if len(keywords) == KEYWORD_LIMIT:
                    return keywords
            continue
        _append_keyword(keywords, token, source)
        if len(keywords) == KEYWORD_LIMIT:
            return keywords

    return keywords


def _append_keyword(keywords: list[str], keyword: str, source: str) -> None:
    if keyword in source and keyword not in keywords and len(keywords) < KEYWORD_LIMIT:
        keywords.append(keyword)
