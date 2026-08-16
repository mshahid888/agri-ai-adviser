# Milestone 11 — Knowledge Base Productionization

## Objectives

Milestone 11 transforms the local knowledge layer from an MVP research
artefact into a production-ready, schema-validated, provenance-traceable
knowledge base. The implementation is strictly additive: no existing
module, test, or safety mechanism is weakened or removed.

---

## 1  Knowledge Schema & Validation

**New module:** `app/knowledge_schema.py`

The schema validator performs conditional validation based on the
`content_status` field and never fabricates missing provenance.

### Fields always required (all content statuses)

| Field | Notes |
|---|---|
| `title` | Must be non-empty. |
| `content_status` | Must be `placeholder`, `extracted`, or `curated`. |

### Fields required for `extracted` and `curated` documents

| Field | Notes |
|---|---|
| `source_id` | Lowercase-hyphenated; must exist in the M9 source registry. |
| `document_id` | Stable, opaque identifier. |
| `source_type` | One of the registered enum values. |
| `version` | Semver or plain string. |
| `status` | `active`, `superseded`, `archived`, or `ingested`. |
| `evidence_quality` | `insufficient`, `general`, `moderate`, or `strong`. |
| `organization` | Non-empty for traceability. |
| `original_pdf_path` **or** `last_updated` **or** `published_date` | At least one must be present for provenance traceability. |

### Additional requirements for `curated` documents

| Field | Notes |
|---|---|
| `reviewed_by` | Name of the reviewer. |
| `review_date` | `YYYY-MM-DD` format. |

### Placeholder documents (`content_status: placeholder`)

No source, review, or provenance fields are required. Missing fields are
emitted as **warnings**, never fabricated or turned into errors.

### Enum validation

| Field | Allowed values |
|---|---|
| `source_type` | `official_extension`, `official_research_institute`, `official_laboratory`, `agricultural_guidance`, `agricultural_context`, `reference` |
| `evidence_quality` | `insufficient`, `general`, `moderate`, `strong` |
| `status` | `active`, `superseded`, `archived`, `ingested` |
| `content_status` | `placeholder`, `extracted`, `curated` |

### `supersedes` semantics

`supersedes` means **this document replaces an older version**. Warnings
are emitted when `status=superseded` or `status=archived` while
`supersedes` is set.

---

## 2  Metadata / Provenance Changes

### `app/document_metadata.py`

- Added the `organization` field to `DocumentMetadata`.
- `build_document_metadata()` now populates `organization` from the
  source registry, defaulting to the registry's `organization` value.
- `version` now defaults to `"1.0"` when the registry record has an
  empty version string.

### `app/knowledge.py` — `EvidenceItem`

- Added `document_id: str | None = None` to the `EvidenceItem` dataclass
  for downstream supersession filtering.

### Knowledge documents

Two existing documents received the new `content_status` field:

| Document | Added field |
|---|---|
| `knowledge/crops/wheat.md` | `content_status: placeholder` |
| `knowledge/regions/punjab_pakistan.md` | `content_status: placeholder` |

No source IDs, document IDs, or other provenance fields were invented.

---

## 3  Retrieval Improvements (`app/knowledge.py`)

All changes are inside `LocalKnowledgeRetriever.retrieve()` and
`validate_recommendation()`. The existing M3–M9 scoring and filtering
behaviour is preserved; new logic is additive.

### 3.1 Farming-stage relevance

Documents whose `farming_stage` metadata token appears in the query
receive a **+4 score boost**. This makes stage-specific advice surface
for stage-specific queries (e.g., "sowing wheat" favours
`farming_stage: sowing_preparation`).

### 3.2 Geographic applicability ranking

| Match type | Boost |
|---|---|
| `district` in query tokens | +5 |
| `province` in query tokens | +3 |
| `region` in query tokens | +1 |

District-specific evidence therefore ranks above province-level, which
ranks above generic evidence — reflecting real-world applicability.

### 3.3 Crop-specific preference

A document whose `crop` metadata matches a query token receives a **+3
boost**, preferencing crop-specific over multi-crop or general advice.

### 3.4 Placeholder handling

- Documents with `content_status: placeholder` receive a **−5 penalty**.
- A **gate** prevents placeholders with total score below 3 from entering
  the result set (i.e., they cannot become substantive evidence merely by
  matching keywords).

### 3.5 Superseded/archived filtering

Documents with `status: superseded` or `status: archived` are excluded
during the scoring loop and never appear in results.

### 3.6 Version/supersession filtering

After scoring, documents are grouped by `document_id`. If multiple
versions of the same `document_id` exist, only the **newest version**
(is determined by the existing `_compare_versions()` helper) is retained.
The `document_id` value is taken from front-matter metadata; no IDs are
invented.

---

## 4  Ingestion Improvements

### 4.1 Schema validation on output (`app/knowledge_converter.py`)

`convert_to_knowledge_markdown()` now validates the generated front
matter against `app/knowledge_schema.py` **before** returning. Invalid
metadata raises a `ValueError` — no invalid knowledge document is ever
written to disk.

The `organization` field is now emitted in the generated front matter.

### 4.2 Deduplication (`app/ingestion.py`)

Before conversion, `ingest_pdf()` calls `_document_id_exists()` to
check whether a knowledge document with the same `document_id` already
exists in the target directory. Duplicate document IDs are rejected with
a clear error message. Deduplication uses only verified `document_id`
identifiers — never similar text.

### 4.3 Batch ingestion (`app/ingestion.py`)

A new `ingest_pdfs()` function accepts a list of PDF descriptors and
ingests each one independently. One failed document does not prevent
others from succeeding. A `BatchIngestionResult` reports per-document
success/failure, total, succeeded, and failed counts.

---

## 5  `validate_recommendation()` Compatibility Fix

`validate_recommendation()` now normalises `supporting_evidence` at the
top of the function so that both `EvidenceItem` objects **and** plain
`dict` evidence records (used by existing M4 tests) are handled
consistently throughout all downstream processing — content matching,
quality assessment, and needs-verification determination.

---

## 6  M11 Tests

**New file:** `tests/test_milestone11.py` — 25 deterministic tests.

| Category | Tests |
|---|---|
| Schema validation | 10 |
| Content status (real KB) | 2 |
| Conflict detection | 1 |
| Farming-stage ranking | 1 |
| Geographic applicability | 2 |
| Version / supersession | 1 |
| Placeholder handling | 2 |
| Ingestion + schema | 4 |
| Safety regression | 2 |
| **Total** | **25** |

---

## 7  Final Regression Result

```
143 tests passed, 0 failed
```

| Suite | Tests | Result |
|---|---|---|
| test_milestone3.py | 8 | ✅ 8 passed |
| test_milestone4.py | 12 | ✅ 12 passed |
| test_milestone5.py | 7 | ✅ 7 passed |
| test_milestone6.py | 15 | ✅ 15 passed |
| test_milestone7.py | 20 | ✅ 20 passed |
| test_milestone8.py | 7 | ✅ 7 passed |
| test_milestone9.py | 10 | ✅ 10 passed |
| test_milestone10.py | 15 | ✅ 15 passed |
| test_milestone11.py | 25 | ✅ 25 passed |
| test_safety.py | 9 | ✅ 9 passed |
| test_llm.py | 1 | ✅ 1 passed |
| test_orchestration.py | 14 | ✅ 14 passed |
| **Total** | **143** | **✅ All passed** |

---

## 8  Files Changed / Created

### New files

| File | Purpose |
|---|---|
| `app/knowledge_schema.py` | Production schema validator |
| `tests/test_milestone11.py` | M11 test suite (25 tests) |
| `MILESTONE_11_IMPLEMENTATION.md` | This document |
| `requirements.txt` | Declared project dependencies |

### Modified files

| File | Nature of change |
|---|---|
| `app/knowledge.py` | Added `document_id` to `EvidenceItem`; farming-stage boost, geographic applicability, crop-specific preference, placeholder penalty/gate, superseded/archived filtering, version/supersession filtering; normalised dict/EvidenceItem handling in `validate_recommendation()` |
| `app/document_metadata.py` | Added `organization` field; `build_document_metadata()` populates `organization` and defaults `version` |
| `app/knowledge_converter.py` | Added `organization` to front-matter; schema validation before return; `metadata` dict carried in `KnowledgeMarkdownOutput` |
| `app/ingestion.py` | Added `_document_id_exists()`, `BatchIngestionResult`, `ingest_pdfs()`; schema validation and dedup in `ingest_pdf()` |
| `knowledge/crops/wheat.md` | Added `content_status: placeholder` |
| `knowledge/regions/punjab_pakistan.md` | Added `content_status: placeholder` |

---

## 9  Known Limitations & Recommended Future Work

### Known limitations

1. **Farming-stage matching is heuristic.** It does a simple substring
   check of query tokens against the `farming_stage` value. It does not
   use a full intent classifier or NLP.

2. **No semantic similarity.** Retrieval is purely keyword/token-based.
   Queries using natural-language paraphrases may miss relevant documents.

3. **Placeholder gate threshold (3) is conservative.** Placeholders with
   genuinely strong keyword and applicability matches may still appear
   in results, though penalised. A higher threshold would risk excluding
   relevant contextual information for emerging crops.

4. **Version comparison is string-based.** The existing
   `_compare_versions()` helper splits on `.` and compares integer
   segments. Non-semver version strings (e.g., "latest", "draft") may
   not compare correctly.

5. **Deduplication scans the full knowledge directory** on every
   `ingest_pdf()` call. For very large knowledge bases this could be
   slow.

### Recommended future work

1. **Embedding-based retrieval** (vector search) for semantic matching
   alongside keyword scoring.

2. **Intent classifier** to map natural-language queries to canonical
   `farming_stage` values rather than relying on token overlap.

3. **Knowledge versioning with a manifest** — a single index file
   tracking all document versions, avoiding full-directory scans for
   dedup.

4. **Automatic supersession linking** — when a new version of a document
   is ingested, automatically set `supersedes` on the new document and
   `status: superseded` on the old one.

5. **Validation CI gate** — run `validate_knowledge_metadata()` against
   all `knowledge/**/*.md` files in CI to catch schema drift early.

6. **Incremental ingestion** — track which PDFs have been ingested via a
   lightweight manifest rather than scanning the output directory.
