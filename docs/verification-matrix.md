# Verification Matrix

| Requirement ID | Stage | Requirement | Verification | Status |
| --- | --- | --- | --- | --- |
| INIT-001 | Init | Backend skeleton exposes a basic health endpoint. | `tests/test_health.py::test_health_endpoint_returns_ok` | Implemented |
| R2-001 | Round 2 | Document schema distinguishes `raw_html` and `cleaned_text`. | `tests/test_html_parser.py::test_parser_preserves_raw_html_and_extracts_cleaned_text` | Implemented |
| R2-002 | Round 2 | HTML parser removes `script`, `style`, and `noscript` content. | `tests/test_html_parser.py::test_parser_removes_script_style_and_noscript_content` | Implemented |
| R2-003 | Round 2 | Title is selected from `<title>`, then `<h1>`, then `doc_id`. | `tests/test_html_parser.py::test_parser_preserves_raw_html_and_extracts_cleaned_text`; `tests/test_html_parser.py::test_parser_uses_h1_title_when_title_tag_is_missing`; `tests/test_html_parser.py::test_parser_falls_back_to_doc_id_when_title_and_h1_are_missing` | Implemented |
| R3-001 | Round 3 | Load all `data/*.html` documents using filename stem as `doc_id`. | `tests/test_documents.py::test_load_documents_uses_html_filename_stem_as_doc_id` | Implemented |
| R3-002 | Round 3 | All loaded HTML documents pass through the parser before storage. | `tests/test_documents.py::test_all_loaded_html_passes_through_parser` | Implemented |
| R3-003 | Round 3 | DocumentStore keeps an in-memory copy and returns copied containers. | `tests/test_documents.py::test_document_store_keeps_loaded_documents_in_memory_copy`; `tests/test_documents.py::test_document_store_returns_copied_containers` | Implemented |
| R4-001 | Round 4 | v1 deterministic keyword search scores title/body matches using 7/3 weights. | `tests/test_key_search.py::test_search_scores_title_matches_with_weight_7_and_body_matches_with_weight_3`; `tests/test_key_search.py::test_search_adds_title_and_body_scores_and_sorts_ties_by_id` | Implemented |
| R4-002 | Round 4 | v1 deterministic search returns short snippets. | `tests/test_key_search.py::test_search_returns_short_snippet_around_body_match` | Implemented |
| R4-003 | Round 4 | v1 deterministic search sorts by score descending, then id ascending. | `tests/test_key_search.py::test_search_adds_title_and_body_scores_and_sorts_ties_by_id`; `tests/test_key_search.py::test_v1_search_endpoint_returns_real_loaded_documents_sorted` | Implemented |
| R4-004 | Round 4 | `/v1/search` exposes deterministic search over loaded documents. | `tests/test_key_search.py::test_v1_search_endpoint_returns_real_loaded_documents_sorted` | Implemented |
| R4-005 | Round 4 Review | `/v1/search?q=&` treats `&` as the intended literal query for upstream compatibility. | `tests/test_key_search.py::test_v1_search_endpoint_treats_literal_q_ampersand_as_ampersand_query` | Implemented |
| R4-006 | Round 4 Review | `OOM` search reflects actual fixture data and does not return `sop-003`. | `tests/test_key_search.py::test_v1_search_oom_matches_actual_data_without_sop_003` | Implemented |
| R4-007 | v1 Integration | `/v1/search` returns the expected response shape through the HTTP layer. | `tests/test_v1_api.py::test_v1_search_returns_expected_response_shape` | Implemented |
| R4-008 | v1 Integration | v1 API validates upstream keyword cases for `OOM`, `故障`, `replication`, `CDN`, and literal `&`. | `tests/test_v1_api.py::test_v1_search_oom_uses_actual_fixture_content`; `tests/test_v1_api.py::test_v1_search_fault_returns_multiple_documents`; `tests/test_v1_api.py::test_v1_search_excludes_script_content`; `tests/test_v1_api.py::test_v1_search_cdn_orders_by_score_then_id`; `tests/test_v1_api.py::test_v1_search_literal_ampersand_boundary` | Implemented |
| R5-001 | Round 5 | v2 Golden Dataset contains 12 cases including required queries: `服务器挂了`, `黑客攻击`, `机器学习模型出问题`. | `tests/test_evaluator.py::test_golden_dataset_contains_required_v2_queries` | Implemented |
| R5-002 | Round 5 | Recall@5 is calculated correctly. | `tests/test_evaluator.py::test_recall_at_5_counts_query_hit_when_any_relevant_doc_is_in_top_5` | Implemented |
| R5-003 | Round 5 | MRR is calculated correctly. | `tests/test_evaluator.py::test_mrr_uses_first_relevant_rank_per_query` | Implemented |
| R5-004 | Round 5 | Evaluator can score a temporary mock retriever without implementing v2 search. | `tests/test_evaluator.py::test_evaluator_uses_temp_mock_retriever_and_reports_metrics` | Implemented |
| R5-005 | Round 5 Review | Golden Dataset covers 5 normal, 3 synonym, 2 boundary, and 2 multi-document cases. | `tests/test_evaluator.py::test_golden_dataset_covers_required_case_categories` | Implemented |
| R6-001 | Round 6 | Semantic expansion loads required domain dictionary entries. | `tests/test_semantic_search.py::test_load_domain_dictionary_contains_required_expansions` | Implemented |
| R6-002 | Round 6 | Semantic expansion expands queries using domain dictionary terms. | `tests/test_semantic_search.py::test_expand_query_uses_domain_dictionary_terms` | Implemented |
| R6-003 | Round 6 | Semantic expansion ranks expected SOPs for server, security, and AI issue queries without modifying v1. | `tests/test_semantic_search.py::test_semantic_search_ranks_backend_and_sre_for_server_down_query`; `tests/test_semantic_search.py::test_semantic_search_ranks_security_for_hacker_attack_query`; `tests/test_semantic_search.py::test_semantic_search_ranks_ai_for_machine_learning_model_issue_query` | Implemented |
| R6-004 | Round 6 | Domain dictionary expansion coverage includes `sop-001` through `sop-010`. | `tests/test_semantic_search.py::test_domain_dictionary_expansion_covers_sop_001_to_sop_010` | Implemented |
| R7-001 | Round 7 | `/v2/search` route connects semantic expansion retrieval through the HTTP layer. | Human test: `服务器挂了`, `黑客攻击`, `机器学习模型出问题` returned expected documents near top. | Implemented |
| R8-001 | Round 8 | BM25 ranks repeated relevant terms higher and sorts by score first, then id. | `tests/test_bm25_retriever.py::test_bm25_rank_scores_repeated_relevant_terms_higher`; `tests/test_bm25_retriever.py::test_bm25_rank_sorts_by_score_first_then_doc_id` | Implemented |
| R8-002 | Round 8 | v2 route uses BM25-improved retrieval for required semantic queries. | `tests/test_v2_api.py::test_v2_search_server_down_ranks_backend_and_sre_near_top`; `tests/test_v2_api.py::test_v2_search_hacker_attack_ranks_security_first`; `tests/test_v2_api.py::test_v2_search_machine_learning_model_issue_ranks_ai_first` | Implemented |
| V1-001 | v1 | Import or load SOP HTML documents. | Pending unit and integration tests. | Pending |
| V1-002 | v1 | Keyword search returns matching SOP documents. | Pending unit, integration, and system tests. | Pending |
| V1-003 | v1 | Search excludes `script` tag content. | Pending regression test for `replication`. | Pending |
| V2-001 | v2 | GoldenDataset covers semantic search expectations. | Pending GoldenDataset tests. | Pending |
| V2-002 | v2 | Semantic expansion improves v1 search. | Pending unit and integration tests. | Pending |
| V2-003 | v2 | Self-implemented BM25 ranks relevant documents. | Pending ranking tests. | Pending |
| V2-004 | v2 | Embedding technical stack and model are user-approved. | Stop-and-ask checkpoint. | Pending |
| V2-005 | v2 | HybridMerge and reranker are evaluated. | Pending Recall@5 and MRR evaluation. | Pending |
| V3-001 | v3 | Agent uses only `readFile(fname)` for SOP access. | Pending after v2 completion and user protocol. | Pending |
