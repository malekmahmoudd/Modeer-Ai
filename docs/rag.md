# Documents (RAG)

Since 2026-09-25. People give files to an agent. The agent answers from them,
cites file and page, and says so when the answer isn't in them.

## What happens to a file

1. **Upload** (`POST /api/documents`: multipart `file`, `agent_id`, `shared`).
   - The upload counts against the per-minute request limit.
   - Limits: 10 MB, and 5 documents per account (`DOCUMENTS_PER_USER`).
   - Oversized requests are refused before they are read.
   - The type comes from the bytes: PDF, DOCX, TXT or MD. Images, zips and
     binaries get `415` with a reason.
2. **Read in the background** (status `processing` → `ready` or `failed`; poll
   `GET /api/documents/{id}`).
   - **Parsing is sandboxed.** It runs in a child process
     (`app/documents/parse.py`) with CPU, memory and wall-clock limits.
   - **PDF** is read with pypdf.
   - **DOCX** is read with the standard library (zip plus XML). Entity
     declarations are refused, and the zip-bomb limits are 2,000 entries,
     100 MB unpacked, and a 100:1 ratio.
   - **Scanned files fail.** A file with no text (a scanned PDF or a photo)
     fails with a message saying so. There is no OCR.
3. **Kept as text only.**
   - The uploaded bytes are discarded after parsing. No file is stored, backed
     up or served.
   - What remains is the extracted text, split into ~1,400-character chunks.
     Each chunk has its page and heading, plus an optional embedding.
   - Everything lives in the database (migration 0007), so it is in the normal
     backups, the data export, and account deletion.

## Who can read it

- The agent it was uploaded to, only.
- `shared: true` (settable with `PATCH /api/documents/{id}`, reversibly) makes
  it readable by the whole team.
- Leo retrieves from shared documents only. He sees an index of all file names
  and which teammate holds each, with sensitive-looking names replaced by
  "(a private file)".
- Ask My Team turns see shared documents only.
- This is enforced in the retrieval SQL (`retrieval.visible_documents`).

## Retrieval (`app/documents/retrieval.py`)

- **Two rankings, fused by reciprocal rank.**
  - BM25 keyword scores. Arabic is folded (alef forms, taa marbuta) and lower-cased.
  - Cosine similarity from a local embedding model.
- **Gated.** Passages are added only when:
  - the top similarity is ≥ 0.84, or
  - it is ≥ 0.79 and stands out from the median by ≥ 0.05, or
  - the message shares ≥ 2 content words with a chunk, or
  - the person refers to their files ("my CV", "the document", "الملف").

  Most turns get nothing and cost nothing.
- **Budget:** up to 4 passages, about 4,000 characters (~1k tokens,
  `RAG_CONTEXT_CHARS`).
- **Whole documents:** when the person points at a file under 3,000
  characters, it is given whole. Summaries need all of it.
- **The previous user message joins the query**, so "and section 3?" still
  finds its topic.

## Where passages go

- **In the user's turn, not the system prompt**, between `<<DOCUMENTS>>`
  markers, labelled `[D1]…` with file, page and heading. Every passage passes
  through `as_data`, so a document containing `<</DOCUMENTS>>` cannot close
  the block.
- **The system prompt lists the files** the agent can read and tells it to:
  - cite as `[D1, file p.2]`
  - say when the passages don't answer
  - quote only words that are there
  - never total figures across passages
- **Nothing downstream sees passages.** The saved message is what the person
  typed, so passages never reach history, the running summary, or memory
  analysis. A document can never create facts, goals, follow-ups or notes.
- **Diagnostics:** the turn's `context.documents` lists what was used (label,
  file, page, score) for a "sources" display.

## The embedding model

- **Model:** `intfloat/multilingual-e5-small` (MIT), int8 ONNX, 118 MB,
  384-dimensional, English and Arabic. It runs on onnxruntime with 2 threads,
  off the event loop.
- **Pinned and verified.** It is pinned to a revision and checked against
  SHA-256 in `app/documents/fetch_model.py`. The Dockerfile runs that at build,
  and a mismatch fails the build. The server never downloads anything.
- **Local development:** `python -m app.documents.fetch_model`.
- **Without the model**, search is keyword-only. Health detail reports
  `document_search`.
- **Every document records its `embed_model`**, so vectors from two models are
  never compared.

## Quality

`python -m app.documents.evaluate [--sweep] [-v]` runs 31 labelled questions
(English and Arabic) and 10 that must retrieve nothing, over the fixtures in
`app/documents/evalset`. It uses no LLM tokens. Results on 2026-09-25:

| Mode | Recall | MRR | Off-topic questions that retrieved |
|---|---|---|---|
| keywords only | 0.65 | 0.65 | 0 / 10 |
| keywords + model | 0.87 | 0.82 | 0 / 10 |

The misses are mostly English questions about an Arabic document. The
thresholds were tuned on this set; 41 questions is small, so treat them as a
starting point. Tests enforce a floor: keyword recall ≥ 0.6, model recall ≥ 0.85
and MRR ≥ 0.75, and no leaks either way.

## Not in v1

No OCR, images, spreadsheets, `.eml`, web pages, Google Drive or Gmail import;
no reranker or query rewriting; no pgvector (not needed at 5 files × a few
hundred chunks). The upload and document-list screens are for the owner to
design; the API and a typed `uploadDocument` helper (with progress and cancel)
exist in `frontend/src/lib/api.ts`.
