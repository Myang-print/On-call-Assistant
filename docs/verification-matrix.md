# Verification Matrix

| Requirement ID | Stage | Requirement | Verification | Status |
| --- | --- | --- | --- | --- |
| INIT-001 | Init | Backend skeleton exposes a basic health endpoint. | `tests/test_health.py::test_health_endpoint_returns_ok` | Implemented |
| R2-001 | Round 2 | Document schema distinguishes `raw_html` and `cleaned_text`. | `tests/test_html_parser.py::test_parser_preserves_raw_html_and_extracts_cleaned_text` | Implemented |
| R2-002 | Round 2 | HTML parser removes `script`, `style`, and `noscript` content. | `tests/test_html_parser.py::test_parser_removes_script_style_and_noscript_content` | Implemented |
| R2-003 | Round 2 | Title is selected from `<title>`, then `<h1>`, then `doc_id`. | `tests/test_html_parser.py::test_parser_preserves_raw_html_and_extracts_cleaned_text`; `tests/test_html_parser.py::test_parser_uses_h1_title_when_title_tag_is_missing`; `tests/test_html_parser.py::test_parser_falls_back_to_doc_id_when_title_and_h1_are_missing` | Implemented |
| V1-001 | v1 | Import or load SOP HTML documents. | Pending unit and integration tests. | Pending |
| V1-002 | v1 | Keyword search returns matching SOP documents. | Pending unit, integration, and system tests. | Pending |
| V1-003 | v1 | Search excludes `script` tag content. | Pending regression test for `replication`. | Pending |
| V2-001 | v2 | GoldenDataset covers semantic search expectations. | Pending GoldenDataset tests. | Pending |
| V2-002 | v2 | Semantic expansion improves v1 search. | Pending unit and integration tests. | Pending |
| V2-003 | v2 | Self-implemented BM25 ranks relevant documents. | Pending ranking tests. | Pending |
| V2-004 | v2 | Embedding technical stack and model are user-approved. | Stop-and-ask checkpoint. | Pending |
| V2-005 | v2 | HybridMerge and reranker are evaluated. | Pending Recall@5 and MRR evaluation. | Pending |
| V3-001 | v3 | Agent uses only `readFile(fname)` for SOP access. | Pending after v2 completion and user protocol. | Pending |
