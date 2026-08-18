import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"


class EvidenceQuality(str, Enum):
    INSUFFICIENT = "insufficient"
    GENERAL = "general"
    MODERATE = "moderate"
    STRONG = "strong"


class ClaimType(str, Enum):
    GENERAL_GUIDANCE = "general_guidance"
    SOWING = "sowing"
    SEED = "seed"
    FERTILIZER = "fertilizer"
    IRRIGATION = "irrigation"
    PESTICIDE = "pesticide"
    DISEASE = "disease"
    VARIETY = "variety"
    RESIDUE = "residue"
    SOIL = "soil"
    OTHER = "other"


def parse_front_matter(content: str) -> tuple[dict[str, str], str]:
    """Parse simple YAML-style front matter from markdown content.

    Returns a (metadata, body) tuple. If no front matter is found, the full input is
    returned unchanged and metadata is empty.
    """
    if not content:
        return {}, ""

    stripped = content.lstrip("\ufeff")
    if not stripped.startswith("---"):
        return {}, stripped

    lines = stripped.splitlines()
    if len(lines) < 3:
        return {}, stripped

    if lines[0].strip() != "---":
        return {}, stripped

    end_index = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break

    if end_index is None:
        return {}, stripped

    metadata: dict[str, str] = {}
    for raw_line in lines[1:end_index]:
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        field_name = key.strip().lower()
        field_value = value.strip().strip('"\'')
        if field_name:
            metadata[field_name] = field_value

    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")
    return metadata, body


@dataclass
class DocumentProvenance:
    source_path: str = ""
    source_name: str = ""
    source_type: str = ""
    document_version: str = ""
    last_updated: str = ""
    published_date: str = ""
    author: str = ""
    organization: str = ""
    document_id: str = ""
    notes: str = ""

    @classmethod
    def from_metadata(cls, metadata: dict[str, str], source_path: str = "") -> "DocumentProvenance":
        source_name = metadata.get("source_name") or metadata.get("title") or source_path.split("/")[-1]
        return cls(
            source_path=source_path or metadata.get("source_path", ""),
            source_name=source_name,
            source_type=metadata.get("source_type", ""),
            document_version=metadata.get("version") or metadata.get("document_version") or "",
            last_updated=metadata.get("last_updated") or "",
            published_date=metadata.get("published_date") or "",
            author=metadata.get("author") or "",
            organization=metadata.get("organization") or "",
            document_id=metadata.get("document_id") or "",
            notes=metadata.get("notes") or "",
        )


@dataclass
class KnowledgeVersionInfo:
    version: str = ""
    last_modified: str = ""
    status: str = "active"
    supersedes: str = ""
    reviewed_by: str = ""
    review_date: str = ""

    @classmethod
    def from_metadata(cls, metadata: dict[str, str]) -> "KnowledgeVersionInfo | None":
        version = metadata.get("version") or metadata.get("document_version") or ""
        last_modified = metadata.get("last_updated") or metadata.get("last_modified") or ""
        status = metadata.get("status") or "active"
        supersedes = metadata.get("supersedes") or ""
        reviewed_by = metadata.get("reviewed_by") or ""
        review_date = metadata.get("review_date") or ""

        if not any([version, last_modified, status, supersedes, reviewed_by, review_date]):
            return None
        return cls(
            version=version,
            last_modified=last_modified,
            status=status,
            supersedes=supersedes,
            reviewed_by=reviewed_by,
            review_date=review_date,
        )


@dataclass
class EvidenceAttribution:
    document_path: str = ""
    section: str | None = None
    claim_text: str = ""
    claim_type: str = ""
    source_quality: str = "general"
    provenance: DocumentProvenance | None = None
    document_version: str = ""
    confidence: str = "unknown"
    is_primary_source: bool = True


@dataclass
class KnowledgeDocument:
    path: str
    title: str
    content: str
    metadata: dict[str, str] = field(default_factory=dict)
    provenance: DocumentProvenance | None = None
    version_info: KnowledgeVersionInfo | None = None



@dataclass
class EvidenceItem:
    source: str
    title: str
    content: str
    document_id: str | None = None
    score: float = 0.0
    quality: EvidenceQuality = EvidenceQuality.GENERAL
    section: str | None = None
    provenance: DocumentProvenance | None = None
    document_version: str | None = None
    source_quality: EvidenceQuality = EvidenceQuality.GENERAL
    attribution: EvidenceAttribution | None = None

    @property
    def path(self) -> str:
        return self.source



@dataclass
class Recommendation:
    text: str
    claim_type: ClaimType = ClaimType.OTHER
    supporting_evidence: list[EvidenceItem] = field(default_factory=list)
    evidence_quality: EvidenceQuality = EvidenceQuality.INSUFFICIENT
    confidence: str = "low"
    needs_verification: bool = True
    warning: str | None = None


def assess_evidence_quality(item: EvidenceItem | None) -> EvidenceQuality:
    if item is None:
        return EvidenceQuality.INSUFFICIENT

    content = (item.content or "").lower()
    if not content:
        return EvidenceQuality.INSUFFICIENT

    if item.score >= 12:
        return EvidenceQuality.STRONG
    if item.score >= 7:
        return EvidenceQuality.MODERATE
    if item.score >= 3:
        return EvidenceQuality.GENERAL
    return EvidenceQuality.INSUFFICIENT


def _coerce_evidence_quality(value: str | None) -> EvidenceQuality:
    if value is None:
        return EvidenceQuality.GENERAL
    normalized = str(value).strip().lower()
    if normalized in {"insufficient", "low"}:
        return EvidenceQuality.INSUFFICIENT
    if normalized in {"moderate", "medium"}:
        return EvidenceQuality.MODERATE
    if normalized in {"strong", "high"}:
        return EvidenceQuality.STRONG
    return EvidenceQuality.GENERAL


def build_document_provenance(metadata: dict[str, str], path: str) -> DocumentProvenance:
    return DocumentProvenance.from_metadata(metadata, path)


def build_version_info(metadata: dict[str, str]) -> KnowledgeVersionInfo | None:
    return KnowledgeVersionInfo.from_metadata(metadata)


def load_knowledge_documents() -> list[KnowledgeDocument]:
    if not KNOWLEDGE_DIR.exists():
        raise FileNotFoundError(f"Knowledge directory not found: {KNOWLEDGE_DIR}")

    documents: list[KnowledgeDocument] = []
    for path in sorted(KNOWLEDGE_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            continue

        metadata, body = parse_front_matter(content)
        if not body.strip():
            body = content

        rel_path = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        title = metadata.get("title") or path.stem.replace("_", " ").title()
        provenance = build_document_provenance(metadata, rel_path)
        version_info = build_version_info(metadata)
        documents.append(
            KnowledgeDocument(
                path=rel_path,
                title=title,
                content=body,
                metadata={key: value for key, value in metadata.items()},
                provenance=provenance,
                version_info=version_info,
            )
        )
    return documents


def _normalise_topic_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {token for token in tokens if len(token) > 2 and token not in LocalKnowledgeRetriever.STOP_WORDS}


def _topic_key_for_evidence_item(item: "EvidenceItem") -> tuple[str, ...]:
    text = f"{item.title} {item.content}".lower()
    tokens = _normalise_topic_tokens(text)
    location_tokens = {"punjab", "pakistan", "sahiwal", "province", "district", "region", "country", "state", "village", "city", "area", "county"}
    key_tokens = sorted(token for token in tokens if token not in location_tokens)
    return tuple(key_tokens[:12])


@dataclass
class ConflictRecord:
    claim_key: str
    conflict_type: str
    severity: str
    description: str
    left_source: str
    right_source: str
    left_version: str | None = None
    right_version: str | None = None
    resolution: str = "Needs verification"


def _compare_versions(version_a: str | None, version_b: str | None) -> int:
    def key(value: str | None) -> tuple[int, ...]:
        if not value:
            return ()
        numbers = tuple(int(part) for part in re.findall(r"\d+", value))
        return numbers if numbers else (-1,)

    left_key = key(version_a)
    right_key = key(version_b)
    if left_key == right_key:
        return 0
    return -1 if left_key < right_key else 1


def _extract_action_polarity(text: str) -> tuple[str | None, bool | None]:
    lowered = (text or "").lower()
    if not lowered:
        return None, None

    action_tokens = {
        "burn": ["burn", "burning", "burned", "burnt"],
        "sow": ["sow", "sowing", "sown", "planting"],
        "apply": ["apply", "application", "applied"],
    }

    for action, tokens in action_tokens.items():
        if any(token in lowered for token in tokens):
            negative_patterns = [
                "should not", "must not", "do not", "avoid", "never", "not burn", "not be burned", "not be burnt", "cannot be burned", "not suitable for burning", "illegal to burn"
            ]
            positive_patterns = [
                "should be burned", "should burn", "can be burned", "acceptable to burn", "may be burned", "can burn", "burning is acceptable", "is acceptable to burn"
            ]
            if any(pattern in lowered for pattern in negative_patterns):
                return action, False
            if any(pattern in lowered for pattern in positive_patterns):
                return action, True
    return None, None


def detect_conflicts(evidence: list["EvidenceItem"]) -> list[ConflictRecord]:
    """Perform conservative, deterministic conflict detection on retrieved evidence.

    This is advisory and non-blocking. It does not create relevance or alter retrieval.
    """
    if len(evidence) < 2:
        return []

    records: list[ConflictRecord] = []
    for idx, left in enumerate(evidence):
        for right in evidence[idx + 1 :]:
            left_key = _topic_key_for_evidence_item(left)
            right_key = _topic_key_for_evidence_item(right)
            if not left_key or not right_key:
                continue
            if left_key != right_key:
                continue

            left_text = (left.content or "").lower()
            right_text = (right.content or "").lower()
            left_meta = (left.provenance.source_type if left.provenance else "")
            right_meta = (right.provenance.source_type if right.provenance else "")

            left_version = left.document_version or (left.provenance.document_version if left.provenance else None)
            right_version = right.document_version or (right.provenance.document_version if right.provenance else None)

            if left_version and right_version and left_version != right_version:
                version_order = _compare_versions(left_version, right_version)
                preferred_version = left_version if version_order >= 0 else right_version
                preferred_source = left.source if version_order >= 0 else right.source
                older_version = right_version if version_order >= 0 else left_version
                records.append(
                    ConflictRecord(
                        claim_key="|".join(left_key),
                        conflict_type="superseded_guidance",
                        severity="moderate",
                        description="The evidence items differ by version and should be reviewed together before finalizing advice.",
                        left_source=left.source,
                        right_source=right.source,
                        left_version=left_version,
                        right_version=right_version,
                        resolution=f"Prefer version {preferred_version} from {preferred_source}; older version {older_version} is superseded.",
                    )
                )

            left_action, left_polarity = _extract_action_polarity(left_text)
            right_action, right_polarity = _extract_action_polarity(right_text)
            if left_action and right_action and left_action == right_action and left_polarity is not None and right_polarity is not None and left_polarity != right_polarity:
                preferred_version = None
                preferred_source = None
                if left_version and right_version:
                    version_order = _compare_versions(left_version, right_version)
                    if version_order >= 0:
                        preferred_version = left_version
                        preferred_source = left.source
                    else:
                        preferred_version = right_version
                        preferred_source = right.source
                resolution = "Retain both items and flag the contradiction for verification before final advice."
                if preferred_version and preferred_source:
                    resolution = f"Prefer version {preferred_version} from {preferred_source}; the older version is superseded and the contradiction should be verified before final advice."
                records.append(
                    ConflictRecord(
                        claim_key="|".join(left_key),
                        conflict_type="direct_contradiction",
                        severity="high",
                        description="The evidence items directly contradict each other on the same action and polarity.",
                        left_source=left.source,
                        right_source=right.source,
                        left_version=left_version,
                        right_version=right_version,
                        resolution=resolution,
                    )
                )
                continue

            left_generic = left_meta in {"agricultural_context", "general_guidance", "reference"}
            right_generic = right_meta in {"agricultural_context", "general_guidance", "reference"}
            if left_generic != right_generic and ("specific" in left_text or "specific" in right_text or "district" in left_text or "district" in right_text or "province" in left_text or "province" in right_text):
                records.append(
                    ConflictRecord(
                        claim_key="|".join(left_key),
                        conflict_type="generic_vs_local_guidance",
                        severity="moderate",
                        description="A generic recommendation and a locally specific recommendation describe the same topic but differ in specificity.",
                        left_source=left.source,
                        right_source=right.source,
                        left_version=left_version,
                        right_version=right_version,
                        resolution="Retain both items and prefer local specificity only when it is explicitly supported.",
                    )
                )
                continue

            if left.provenance and right.provenance and left.provenance.source_type and right.provenance.source_type and left.provenance.source_type != right.provenance.source_type:
                if left.quality != right.quality or left.score != right.score:
                    records.append(
                        ConflictRecord(
                            claim_key="|".join(left_key),
                            conflict_type="source_quality_difference",
                            severity="moderate",
                            description="The documents describe the same topic but differ in source type and quality signals.",
                            left_source=left.source,
                            right_source=right.source,
                            left_version=left_version,
                            right_version=right_version,
                            resolution="Retain both evidence items and expose the need for verification.",
                        )
                    )
                    continue

    deduped: list[ConflictRecord] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        key = (record.claim_key, record.conflict_type, record.left_source, record.right_source)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


class LocalKnowledgeRetriever:
    """Simple, deterministic retrieval suitable for local markdown knowledge bases."""

    STOP_WORDS = {
        "about", "after", "and", "are", "as", "at", "be", "by", "can",
        "for", "from", "in", "into", "is", "it", "its", "of", "on",
        "or", "our", "should", "the", "their", "this", "through", "to",
        "with", "without", "a", "an", "between", "when", "what", "where",
        "who", "why", "how", "not"
    }

    AGRONOMY_TERMS = {
        "wheat", "rice", "residue", "seedbed", "sowing", "irrigation",
        "soil", "nutrient", "management", "rotation", "moisture",
        "crop", "planting", "fertility", "yield", "chemical", "pesticide",
        "fungicide", "herbicide", "field", "agriculture", "farming",
        "fertilizer", "variety", "disease", "weed", "rainfall", "salinity"
    }

    LOCATION_TOKENS = {
        "punjab", "pakistan", "sahiwal", "province", "region", "district",
        "village", "city", "country", "state", "area", "county"
    }

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
        return {token for token in tokens if len(token) > 2 and token not in LocalKnowledgeRetriever.STOP_WORDS}

    def retrieve(self, query: str, top_k: int = 3) -> list[EvidenceItem]:
        if not query or not query.strip():
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scored: list[EvidenceItem] = []
        for document in load_knowledge_documents():
            content = document.content
            content_lower = content.lower()
            title_lower = document.title.lower()
            path_lower = document.path.lower()
            metadata_lower = {str(key).lower(): str(value).lower() for key, value in document.metadata.items()}

            base_score = 0.0
            direct_title_matches = set()
            direct_content_matches = set()
            agricultural_query_terms = set()

            for token in query_tokens:
                if token in self.LOCATION_TOKENS:
                    continue
                if token in title_lower:
                    base_score += 6
                    direct_title_matches.add(token)
                if token in content_lower:
                    base_score += 2
                    direct_content_matches.add(token)
                if token in content_lower and token in self.AGRONOMY_TERMS:
                    base_score += 3
                if token in self.AGRONOMY_TERMS:
                    agricultural_query_terms.add(token)

            matched_agronomy = sum(1 for term in self.AGRONOMY_TERMS if term in query_tokens and term in content_lower)
            if matched_agronomy:
                base_score += matched_agronomy * 4

            if any(token in query_tokens for token in {"wheat", "rice", "maize", "cotton", "ricewheat"}):
                if "/crops/" in path_lower:
                    base_score += 5
                if "/regions/" in path_lower:
                    base_score -= 2

            if "sahiwal" in query_tokens and "sahiwal" in content_lower:
                base_score += 2

            if "/regions/" in path_lower and not any(term in content_lower for term in ["residue", "seedbed", "sowing", "irrigation", "nutrient", "soil"]):
                base_score -= 2

            # M11 Applicability: District > Province > Region
            if metadata_lower.get("district") in query_tokens:
                base_score += 5
            elif metadata_lower.get("province") in query_tokens:
                base_score += 3
            elif metadata_lower.get("region") in query_tokens:
                base_score += 1

            # M11 Applicability: Crop-specific
            if metadata_lower.get("crop") in query_tokens:
                base_score += 3

            # M11 Farming-stage relevance (heuristic)
            stage = metadata_lower.get("farming_stage")
            if stage and any(token in stage.replace("_", " ") for token in query_tokens):
                base_score += 4

            # M12: Hybrid semantic-heuristic retrieval
            try:
                from app.vector_index import VectorIndex
                semantic_index = VectorIndex()
                semantic_results = dict(semantic_index.search(query, top_k=10))
                if document.path in semantic_results:
                    # Boost by up to 5 points based on semantic similarity
                    base_score += semantic_results[document.path] * 5
            except Exception:
                pass # Fail gracefully

            # M11 Placeholder handling
            if metadata_lower.get("content_status") == "placeholder":
                base_score -= 5
                # Gate: placeholder must still reach general threshold to be evidence
                if base_score < 3:
                    continue

            non_location_query_terms = {token for token in query_tokens if token not in self.LOCATION_TOKENS}
            meaningful_content = (
                base_score >= 7
                or len(direct_title_matches | direct_content_matches) >= 2
                or matched_agronomy >= 1
                or bool(agricultural_query_terms & non_location_query_terms)
            )

            if not meaningful_content:
                continue

            metadata_score = 0.0
            for key, value in metadata_lower.items():
                if not value:
                    continue
                metadata_tokens = self._tokenize(value)
                metadata_matches = set(metadata_tokens) & non_location_query_terms
                if metadata_matches:
                    metadata_score += len(metadata_matches) * 2
                if key in {"crop", "province", "region", "district"} and value in content_lower:
                    metadata_score += 1

            if metadata_score:
                metadata_boost = min(metadata_score, 3.0)
                base_score += metadata_boost

            if base_score > 0:
                item = EvidenceItem(
                    source=document.path,
                    title=document.title,
                    content=content,
                    document_id=document.metadata.get("document_id"),
                    score=float(base_score),
                    provenance=document.provenance,
                    document_version=document.version_info.version if document.version_info else (document.provenance.document_version if document.provenance else None),
                    source_quality=_coerce_evidence_quality(document.metadata.get("evidence_quality")),
                )
                item.quality = assess_evidence_quality(item)
                item.attribution = EvidenceAttribution(
                    document_path=document.path,
                    section=None,
                    claim_text=content[:200],
                    claim_type="",
                    source_quality=item.source_quality.value,
                    provenance=document.provenance,
                    document_version=item.document_version or "",
                    confidence="medium" if item.score >= 7 else "low",
                    is_primary_source=True,
                )
                # Filter out superseded status
                if metadata_lower.get("status") in {"superseded", "archived"}:
                    continue

                scored.append(item)

        # M11 Version/supersession handling: keep newer versions of same document_id
        if scored:
            final_scored = []
            doc_id_groups: dict[str, list[EvidenceItem]] = {}
            no_id_items = []
            for item in scored:
                if item.document_id:
                    doc_id_groups.setdefault(item.document_id, []).append(item)
                else:
                    no_id_items.append(item)
            
            for doc_id, group in doc_id_groups.items():
                if len(group) == 1:
                    final_scored.append(group[0])
                else:
                    # Keep newest version
                    newest = group[0]
                    for other in group[1:]:
                        if _compare_versions(other.document_version, newest.document_version) > 0:
                            newest = other
                    final_scored.append(newest)
            
            final_scored.extend(no_id_items)
            scored = final_scored

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]


def classify_claim_type(text: str) -> ClaimType:
    lowered = text.lower()
    if any(word in lowered for word in ["fertilizer", "dap", "urea", "nitrogen", "phosphorus", "potassium", "bag per acre", "bags per acre"]):
        return ClaimType.FERTILIZER
    if any(word in lowered for word in ["pesticide", "herbicide", "fungicide", "spray", "dose", "ml/acre", "application rate", "tank mix"]):
        return ClaimType.PESTICIDE
    if any(word in lowered for word in ["variety", "cultivar", "seed variety", "hybrid"]):
        return ClaimType.VARIETY
    if any(word in lowered for word in ["disease", "yellowing", "rust", "blast", "leaf spot", "powdery mildew"]):
        return ClaimType.DISEASE
    if any(word in lowered for word in ["sowing", "seedbed", "planting date", "seeding"]):
        return ClaimType.SOWING
    if any(word in lowered for word in ["irrigation", "water", "moisture"]):
        return ClaimType.IRRIGATION
    if any(word in lowered for word in ["residue", "straw", "burning"]):
        return ClaimType.RESIDUE
    if any(word in lowered for word in ["soil", "texture", "loam", "salinity"]):
        return ClaimType.SOIL
    if any(word in lowered for word in ["seed", "seeds", "germination"]):
        return ClaimType.SEED
    return ClaimType.OTHER


def validate_recommendation(recommendation: Recommendation) -> Recommendation:
    if not recommendation.text.strip():
        recommendation.warning = "Recommendation text is empty."
        recommendation.needs_verification = True
        recommendation.confidence = "low"
        recommendation.evidence_quality = EvidenceQuality.INSUFFICIENT
        return recommendation

    if not recommendation.supporting_evidence:
        recommendation.warning = "This recommendation is not supported by retrieved evidence."
        recommendation.needs_verification = True
        recommendation.confidence = "low"
        recommendation.evidence_quality = EvidenceQuality.INSUFFICIENT
        return recommendation

    # Normalize evidence for consistent processing
    normalized_evidence = []
    for item in recommendation.supporting_evidence:
        if isinstance(item, dict):
            normalized_evidence.append({
                "content": item.get("content", ""),
                "quality": _coerce_evidence_quality(item.get("quality"))
            })
        else:
            normalized_evidence.append({
                "content": item.content,
                "quality": assess_evidence_quality(item)
            })

    text = recommendation.text.lower()
    source_text = "\n".join(e["content"].lower() for e in normalized_evidence)

    if recommendation.claim_type in {ClaimType.FERTILIZER, ClaimType.PESTICIDE, ClaimType.VARIETY, ClaimType.DISEASE}:
        if any(pattern in text for pattern in ["exactly", "per acre", "bags of", "ml/acre", "dose", "variety", "diagnose", "this is disease"]):
            if not any(
                pattern in source_text
                for pattern in ["verified local agricultural evidence", "locally applicable agricultural recommendations", "soil-test", "registered product label"]
            ):
                recommendation.warning = "Specific agricultural recommendations require verified local evidence; the current retrieved evidence is insufficient."
                recommendation.needs_verification = True
                recommendation.confidence = "low"
                recommendation.evidence_quality = EvidenceQuality.INSUFFICIENT
                return recommendation

    if recommendation.claim_type == ClaimType.FERTILIZER and "exact" in text:
        recommendation.warning = "Exact fertilizer rates require verified local evidence. Do not present an exact fertilizer rate without supporting soil-test or local recommendation evidence."
        recommendation.needs_verification = True
        recommendation.confidence = "low"
        recommendation.evidence_quality = EvidenceQuality.INSUFFICIENT
        return recommendation

    if recommendation.claim_type == ClaimType.PESTICIDE and any(word in text for word in ["spray", "dose", "ml", "litre", "rate", "product name"]):
        recommendation.warning = "Pesticide recommendations require verified local label and regulatory evidence; do not invent a product, dose, or spray schedule."
        recommendation.needs_verification = True
        recommendation.confidence = "low"
        recommendation.evidence_quality = EvidenceQuality.INSUFFICIENT
        return recommendation

    if recommendation.claim_type == ClaimType.DISEASE and any(word in text for word in ["this is", "definitely", "diagnosis", "disease x", "disease is"]):
        recommendation.warning = "Disease diagnosis is not reliable without field observations and local expert confirmation."
        recommendation.needs_verification = True
        recommendation.confidence = "low"
        recommendation.evidence_quality = EvidenceQuality.INSUFFICIENT
        return recommendation

    # Use normalized_evidence for consistent quality assessment
    recommendation.evidence_quality = max(
        [e["quality"] for e in normalized_evidence],
        key=lambda q: [
            EvidenceQuality.INSUFFICIENT,
            EvidenceQuality.GENERAL,
            EvidenceQuality.MODERATE,
            EvidenceQuality.STRONG,
        ].index(q),
    )
    recommendation.needs_verification = recommendation.evidence_quality in {EvidenceQuality.INSUFFICIENT, EvidenceQuality.GENERAL}
    recommendation.confidence = "medium" if recommendation.evidence_quality in {EvidenceQuality.GENERAL, EvidenceQuality.MODERATE} else "low"

    return recommendation


def retrieve(query: str, top_k: int = 3) -> list[EvidenceItem]:
    return LocalKnowledgeRetriever().retrieve(query, top_k=top_k)
