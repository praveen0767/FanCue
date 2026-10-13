"""FanCue canonical contract models and schemas package."""

from backend.app.schemas.common import (
    ExplanationDepth,
    LanguageCode,
    MatchDescriptor,
    MatchMode,
    PerspectiveLens,
    RequestCorrelation,
    SportType,
)
from backend.app.schemas.cricket import (
    CricketCatchUpRequest,
    CricketDeliveryEvent,
    CricketDeliveryExtras,
    CricketDeliveryRuns,
    CricketInterval,
    CricketScoreSnapshot,
    CricketStateDelta,
    CricketWicket,
)
from backend.app.schemas.errors import (
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
)
from backend.app.schemas.evidence import (
    EvidenceFact,
    FactType,
    MatchEvidencePacket,
)
from backend.app.schemas.explanation import (
    ClaimType,
    CricketCatchUpResponse,
    ExplanationPayload,
    FallbackReason,
    GenerationMode,
    StructuredClaim,
    VerificationStatus,
)
from backend.app.schemas.football import (
    FootballCatchUpRequest,
    FootballInterval,
    FootballMatchEvent,
    FootballPeriod,
    FootballScoreSnapshot,
    FootballStateDelta,
)
from backend.app.schemas.provenance import (
    PermittedUse,
    SourceProvenance,
)
from backend.app.schemas.knowledge import (
    KnowledgeChunk,
    KnowledgeChunkPayload,
    KnowledgeDocumentFrontmatter,
    KnowledgeSourceType,
    KnowledgeType,
    ReviewStatus,
    SourceCheckStatus,
)

__all__ = [
    # Common
    "SportType",
    "LanguageCode",
    "PerspectiveLens",
    "ExplanationDepth",
    "MatchMode",
    "MatchDescriptor",
    "RequestCorrelation",
    # Provenance
    "PermittedUse",
    "SourceProvenance",
    # Knowledge
    "ReviewStatus",
    "SourceCheckStatus",
    "KnowledgeType",
    "KnowledgeSourceType",
    "KnowledgeDocumentFrontmatter",
    "KnowledgeChunkPayload",
    "KnowledgeChunk",
    # Cricket
    "CricketInterval",
    "CricketCatchUpRequest",
    "CricketScoreSnapshot",
    "CricketStateDelta",
    "CricketDeliveryRuns",
    "CricketDeliveryExtras",
    "CricketWicket",
    "CricketDeliveryEvent",
    # Football
    "FootballPeriod",
    "FootballInterval",
    "FootballCatchUpRequest",
    "FootballScoreSnapshot",
    "FootballStateDelta",
    "FootballMatchEvent",
    # Evidence
    "FactType",
    "EvidenceFact",
    "MatchEvidencePacket",
    # Explanation
    "ClaimType",
    "StructuredClaim",
    "GenerationMode",
    "VerificationStatus",
    "FallbackReason",
    "ExplanationPayload",
    "CricketCatchUpResponse",
    # Errors
    "ErrorCode",
    "ErrorDetail",
    "ErrorResponse",
]
