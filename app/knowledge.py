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
class KnowledgeDocument:
    path: str
    title: str
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class EvidenceItem:
    source: str
    title: str
    content: str
    score: float = 0.0
    quality: EvidenceQuality = EvidenceQuality.GENERAL
    section: str | None = None

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

        title = metadata.get("title") or path.stem.replace("_", " ").title()
        documents.append(
            KnowledgeDocument(
                path=str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                title=title,
                content=body,
                metadata={key: value for key, value in metadata.items()},
            )
        )
    return documents


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
                    score=float(base_score),
                )
                item.quality = assess_evidence_quality(item)
                scored.append(item)

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

    text = recommendation.text.lower()
    source_text = "\n".join(item.content.lower() for item in recommendation.supporting_evidence)

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

    if recommendation.supporting_evidence:
        recommendation.evidence_quality = max(
            [assess_evidence_quality(item) for item in recommendation.supporting_evidence],
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
