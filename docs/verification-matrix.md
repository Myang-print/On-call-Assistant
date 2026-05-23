# Verification Matrix

| Requirement ID | Stage | Requirement | Verification | Status |
| --- | --- | --- | --- | --- |
| INIT-001 | Init | Backend skeleton exposes a basic health endpoint. | `tests/test_health.py::test_health_endpoint_returns_ok` | Implemented |
| V1-001 | v1 | Import or load SOP HTML documents. | Pending unit and integration tests. | Pending |
| V1-002 | v1 | Keyword search returns matching SOP documents. | Pending unit, integration, and system tests. | Pending |
| V1-003 | v1 | Search excludes `script` tag content. | Pending regression test for `replication`. | Pending |
| V2-001 | v2 | GoldenDataset covers semantic search expectations. | Pending GoldenDataset tests. | Pending |
| V2-002 | v2 | Semantic expansion improves v1 search. | Pending unit and integration tests. | Pending |
| V2-003 | v2 | Self-implemented BM25 ranks relevant documents. | Pending ranking tests. | Pending |
| V2-004 | v2 | Embedding technical stack and model are user-approved. | Stop-and-ask checkpoint. | Pending |
| V2-005 | v2 | HybridMerge and reranker are evaluated. | Pending Recall@5 and MRR evaluation. | Pending |
| V3-001 | v3 | Agent uses only `readFile(fname)` for SOP access. | Pending after v2 completion and user protocol. | Pending |
