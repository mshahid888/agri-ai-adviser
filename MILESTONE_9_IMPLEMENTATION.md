# Milestone 9 Implementation: Official Agricultural Knowledge Base & Source Registry

## Overview
Milestone 9 establishes the architecture for an **Official Agricultural Knowledge
Base & Source Registry**. It introduces a deterministic, local registry of official
agricultural sources and a small, high-quality initial Sahiwal/Punjab dataset that
proves source registration, provenance linkage, Markdown retrieval, local/district
metadata, unrelated-query rejection, and registry validation.

The guiding principle is:

    OFFICIAL SOURCE -> CURATED/EXTRACTED KNOWLEDGE -> PROVENANCE -> EXISTING RETRIEVER

## Design Decisions

### 1. Registry stored as JSON (no retrieval impact)
The existing knowledge loader (`load_knowledge_documents`) scans `knowledge/`
recursively for **`.md` and `.txt` files only**. The source registry is therefore
stored as **JSON** under `knowledge/sources/registry/`. JSON records are never
loaded as knowledge documents, so retrieval, scoring, orchestration, safety, and
provenance logic remain completely unchanged.

### 2. Additive module only
A new module `app/source_registry.py` reads the registry. It is a new file and
does not modify any existing module.

### 3. Non-substantive placeholder knowledge
All new knowledge Markdown files are explicitly marked `content_status: placeholder`.
They describe what future official material will contain and do **not** author or
invent agricultural recommendations. Every knowledge file carries a `source_id`
linking to a registry record.

### 4. URL verification policy
Only verified official Punjab government URLs are recorded. Sources whose exact
URL cannot be verified are left with an empty `official_url` and marked
`url_status: pending_verification`. No URLs are invented.

## Directory Structure

```
knowledge/
    crops/          # extracted/curated crop knowledge (.md) — RETRIEVED
    regions/        # regional/district knowledge (.md) — RETRIEVED
    topics/         # thematic knowledge (.md) — RETRIEVED
    sources/
        registry/   # source registry records (.json) — NOT retrieved
        originals/  # original PDFs/publications — stored here, NOT retrieved
```

### Original PDFs vs extracted Markdown (future-proofing)
- **Original PDFs** are stored in `knowledge/sources/originals/`. The loader only
  scans `.md`/`.txt`, so PDFs there are never retrieved.
- **Extracted/curated knowledge** lives in `crops/`, `regions/`, `topics/` as `.md`.
- The registry's `document_path` field will point to the original PDF in
  `originals/`, while the knowledge `.md` carries the `source_id` linking back to
  the registry record.

## Source Registry Schema

Each official source is one JSON file in `knowledge/sources/registry/`:

| Field | Description |
|-------|-------------|
| `source_id` | Unique identifier for the source |
| `title` | Source title |
| `organization` | Owning organization |
| `source_type` | e.g. `official_extension`, `official_laboratory`, `official_research_institute` |
| `official_url` | Verified official URL (empty if pending) |
| `url_status` | `verified` or `pending_verification` |
| `document_path` | Path to original document (empty until ingestion) |
| `crop` | Related crop (if any) |
| `region` | Region |
| `province` | Province |
| `district` | District |
| `topic` | Topic |
| `publication_date` | Publication date |
| `last_updated` | Last updated date |
| `version` | Version |
| `evidence_quality` | Evidence quality |
| `status` | `registered`, `ingested`, `pending`, or `archived` |
| `notes` | Free-form notes |

## Files Created

### Registry module
- `app/source_registry.py` — `SourceRecord`, `load_source_registry()`,
  `get_source()`, `list_sources()`, `find_sources()`, `validate_source_record()`.

### Official source metadata (registry JSON)
- `knowledge/sources/registry/sahiwal_agriculture_extension.json`
- `knowledge/sources/registry/punjab_agriculture_extension.json`
- `knowledge/sources/registry/sahiwal_soil_water_testing_lab.json`
- `knowledge/sources/registry/potato_research_institute_sahiwal.json`
- `knowledge/sources/registry/maize_millets_research_institute_yusafwala.json`

### Initial placeholder knowledge documents
- `knowledge/regions/sahiwal_punjab.md`
- `knowledge/crops/rice.md`
- `knowledge/topics/production_technology_guides.md`

### Original PDF storage placeholder
- `knowledge/sources/originals/.gitkeep`

### Tests
- `tests/test_milestone9.py`

## Tests

`tests/test_milestone9.py` verifies:
1. Source registry loads the expected official sources.
2. Each source record has required fields.
3. Verified sources have an official URL; pending sources are marked.
4. Registry JSON files are not loaded as knowledge documents.
5. Knowledge documents link to a registry record via `source_id`.
6. Knowledge placeholders are marked non-substantive.
7. New knowledge documents load with provenance.
8. A relevant query retrieves the new Sahiwal knowledge.
9. An unrelated query returns nothing.
10. Registry validation flags missing required fields and passes for valid records.

## Future Work (not in M9)
- PDF ingestion/parsing (original PDFs stored in `knowledge/sources/originals/`).
- Web scraping of official sources (only after URL verification).
- Large-scale ingestion of official production technology documents and
  crop recommendations.
- Replacing placeholder knowledge with curated content derived from official
  sources.

## Constraints Honored
- No existing M3–M8 logic modified.
- No retrieval, orchestration, safety, or provenance code modified.
- No web scraping.
- No PDF parsing.
- No invented agricultural content.
- Only the files listed above were created.