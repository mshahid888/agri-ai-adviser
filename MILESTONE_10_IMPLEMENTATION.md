# Milestone 10 Implementation: PDF & Agricultural Document Ingestion

## Overview
Milestone 10 establishes the pipeline for converting official agricultural PDFs
and documents into the existing local knowledge architecture. It introduces a
strictly additive ingestion layer that preserves the original PDF as an
immutable source, links every ingested document to the M9 source registry, and
produces curated knowledge Markdown that the existing knowledge layer can load.

The pipeline is:

    Original PDF
    -> text extraction (M10.1)
    -> source/document metadata (M10.2)
    -> conversion to knowledge Markdown (M10.3)
    -> extraction-quality validation (M10.4)
    -> curated knowledge Markdown written to the knowledge layer

## Design Decisions

### 1. Verbatim extraction
PDF text is extracted verbatim using `pypdf`. No paraphrasing, rewriting, or
invention of agricultural facts occurs. The extracted text is preserved as-is.

### 2. Page preservation
Each PDF page is extracted into a `PdfPage` object. The converter preserves
page boundaries as Markdown comments (`<!-- Page N -->`) in the body.

### 3. Heading/section preservation (heuristic)
Markdown-style heading lines already present in the extracted text are
preserved as-is. No structure is fabricated.

### 4. Registry linkage
Every generated knowledge Markdown file carries `source_id`, `document_id`,
and `original_pdf_path` in its front matter. A new additive helper
`register_document_path()` updates the M9 source registry record's
`document_path` to point at the original PDF.

### 5. Raw PDFs never retrieved
The existing knowledge loader only scans `.md` and `.txt` files, so raw PDFs
stored in `knowledge/sources/originals/` are never loaded as retrieval
documents.

### 6. No bulk ingestion
M10 proves the pipeline on a small hand-crafted fixture PDF. No real
agricultural documents are ingested.

## Files Created

### New modules (strictly additive)
- `app/pdf_extractor.py` — `PdfPage`, `PdfExtractionResult`, `extract_pdf_text()`.
- `app/document_metadata.py` — `DocumentMetadata`, `build_document_metadata()`, `validate_document_metadata()`.
- `app/knowledge_converter.py` — `KnowledgeMarkdownOutput`, `convert_to_knowledge_markdown()`, `write_knowledge_markdown()`.
- `app/extraction_quality.py` — `ExtractionQualityReport`, `assess_extraction_quality()`, `validate_extraction()`.
- `app/ingestion.py` — `IngestionResult`, `ingest_pdf()` (orchestrates M10.1–M10.4).

### Modified module (one additive function)
- `app/source_registry.py` — added `register_document_path()`.

### Fixture
- `tests/fixtures/sample_official.pdf` — small text-based PDF with known content.
- `scripts/generate_fixture_pdf.py` — script that generates the fixture.

### Tests & documentation
- `tests/test_milestone10.py` — deterministic tests.
- `MILESTONE_10_IMPLEMENTATION.md` — this documentation.

## Dependencies
- **`pypdf`** (installed in the project venv) — pure Python PDF text extraction.
- No other new dependencies. No vector DB, no embeddings, no LangChain/LangGraph,
  no OCR, no web scraping.

## Data Flow

1. `ingest_pdf(pdf_path, source_id, document_id, title, target_dir, ...)`:
   - `extract_pdf_text(pdf_path)` -> `PdfExtractionResult` (per-page text).
   - `assess_extraction_quality(result)` -> abort if poor (e.g., empty pages).
   - `build_document_metadata(source_id, ...)` -> validates `source_id` exists
     in the M9 registry; returns `DocumentMetadata`.
   - `convert_to_knowledge_markdown(result, metadata)` -> front matter + body.
   - `write_knowledge_markdown(output, target_dir, filename)` -> writes `.md`.
   - `register_document_path(source_id, original_pdf_path)` -> updates registry.
   - Returns `IngestionResult`.
2. The generated `.md` is loadable by the existing `load_knowledge_documents()`
   and retrievable by `LocalKnowledgeRetriever` — no changes to those.

## Tests

`tests/test_milestone10.py` verifies:
1. PDF text extraction preserves pages.
2. Extraction preserves known verbatim text.
3. Missing PDF files report errors.
4. Document metadata links to the M9 source registry.
5. Metadata validation rejects unknown sources.
6. Metadata validation passes for valid metadata.
7. Conversion produces front matter and body.
8. Converted Markdown loads in the knowledge layer.
9. Extraction-quality validation flags empty pages.
10. Extraction-quality validation passes for good extractions.
11. End-to-end ingestion pipeline succeeds.
12. Ingestion rejects unknown sources.
13. Ingestion rejects missing PDFs.
14. `register_document_path()` updates the registry.
15. `register_document_path()` refuses to overwrite an existing path.

## Risks

1. **Scanned/image PDFs yield no text** — `pypdf` extracts embedded text only.
   Mitigation: quality validation flags empty pages; OCR is out of scope.
2. **Heading/section preservation is heuristic** — PDFs don't expose reliable
   structure. Mitigation: preserve page boundaries reliably; detect headings
   heuristically; never fabricate structure.
3. **New dependency** — `pypdf` must be installed. Low risk (pure Python).
4. **Polluting the live knowledge base** — Mitigation: M10 writes to temp dirs
   in tests; no real ingestion.
5. **Not inventing facts** — Mitigation: verbatim extraction, no paraphrasing.
6. **Registry modification** — Mitigation: `register_document_path()` refuses
   to overwrite an existing `document_path`; tested against a temp registry dir.

## Acceptance Criteria

- `pypdf` installed in the venv.
- All 5 new modules + ingestion orchestrator created; one additive function
  added to `source_registry.py`.
- Fixture PDF extracts with correct page count and known verbatim text.
- Metadata links to the M9 registry via `source_id`; unknown sources rejected.
- Converted Markdown has valid front matter + body and loads as a
  `KnowledgeDocument`.
- Raw PDF is never a retrieval document.
- Extraction-quality validation flags poor extractions.
- End-to-end `ingest_pdf()` succeeds on the fixture (temp dir output).
- All existing tests + new M10 tests pass.
- No existing logic modified; nothing committed.

## Constraints Honored
- No retrieval, orchestration, safety, or existing provenance logic modified.
- No existing tests modified.
- No real agricultural PDFs ingested.
- No web scraping, no OCR, no vector DB, no embeddings, no LangChain/LangGraph,
  no autonomous agents, no bulk ingestion.
- Nothing committed.