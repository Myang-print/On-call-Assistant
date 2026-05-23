# Project Constraints

This file is the persistent project memory and constraint reference for future work.
Do not overwrite or weaken these constraints without an explicit reason and user approval.

## Role And Engineering Baseline

- Treat ARINC 653 principles as the top-level systems engineering reference.
- Act as the lead agent full-stack engineer, while keeping implementation choices constrained by user approval.
- Prefer partitioned, deterministic, testable components with controlled resource access and clear fault isolation.

## Scope Control

- These constraints apply across the full conversation unless the user explicitly changes them.
- Only modify files or directories explicitly authorized by the user.
- If a needed change touches an unauthorized file, skip it when possible and record the filename in the current response.
- When the implementation appears to diverge from the upstream project requirements, report the divergence before proceeding.
- When a better approach may exist, report the file name, line number, and a short alternative before changing direction.

## Upstream Requirement Source

- Source: https://github.com/oriengy/coding-exam/tree/aa1a4a0b22c02a086aeb2c78f1ef1a0d392e540c/question-1
- Product: On-Call Assistant Web application.
- Required stages:
  - `/v1`: keyword search engine.
  - `/v2`: semantic search.
  - `/v3`: On-Call Assistant Agent.

## Current Technical Stack

- Backend: FastAPI, Uvicorn, BeautifulSoup4, HTTPX.
- Frontend: deferred; current stage is backend only.
- Testing: pytest.
- Pinned dependencies:
  - `fastapi==0.115.0`
  - `uvicorn[standard]==0.30.6`
  - `beautifulsoup4==4.12.3`
  - `pytest==8.3.2`
  - `httpx==0.27.2`

## Version Roadmap

### v1

- Use a simple minimum implementation by default.
- Implement keyword search on top of parsed SOP HTML content.
- Exclude non-body searchable content such as `script` text when required by upstream validation.

### v2

- First build a GoldenDataset for tests.
- Implement semantic expansion on top of v1.
- Strengthen retrieval with a self-implemented BM25 approach.
- Stop and ask the user for technical stack and model selection before starting embedding work.
- After embedding, continue with HybridMerge and reranker.
- Add evaluation using Recall@5 and MRR.

### v3

- Wait until v2 is fully complete.
- The user will provide Kimi 2.6 model API details and the next action protocol.

## Testing And Verification

- Each core node function needs unit tests aligned with DO-178C Level A rigor as a project discipline.
- Each layer and workflow needs integration tests.
- After completing each version, add system tests.
- When new functionality can interfere with earlier versions, add regression tests.
- Tests must live in `tests/`.
- Tests should use logging to expose acceptance evidence.
- Maintain lightweight requirement-test-verification traceability in `docs/verification-matrix.md`.

## Git And Review

- After each version passes user acceptance, remind the user to approve a git commit for that version.
- Do not commit automatically unless the user explicitly asks.
- Initialization may create a skeleton.
- After initialization, development must strictly follow explicit user commands.
