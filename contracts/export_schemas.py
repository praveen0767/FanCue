"""Export canonical JSON Schema definitions from Pydantic models.

Ensures contracts/ has authoritative, versioned JSON Schemas that strictly
match backend/app/schemas/ without drift.
"""

import json
import os
import sys

# Ensure repository root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.schemas.common import MatchDescriptor, RequestCorrelation
from backend.app.schemas.provenance import SourceProvenance
from backend.app.schemas.cricket import (
    CricketCatchUpRequest,
    CricketDeliveryEvent,
    CricketScoreSnapshot,
    CricketStateDelta,
)
from backend.app.schemas.football import (
    FootballCatchUpRequest,
    FootballMatchEvent,
    FootballScoreSnapshot,
    FootballStateDelta,
)
from backend.app.schemas.evidence import EvidenceFact, MatchEvidencePacket
from backend.app.schemas.retrieval import RetrievalQuery, RetrievedPassage, RetrievalResult
from backend.app.schemas.explanation import (
    CricketCatchUpResponse,
    ExplanationPayload,
    StructuredClaim,
)
from backend.app.schemas.errors import ErrorResponse
from backend.app.schemas.knowledge import (
    KnowledgeChunk,
    KnowledgeChunkPayload,
    KnowledgeDocumentFrontmatter,
)

CONTRACTS_DIR = os.path.abspath(os.path.dirname(__file__))

SCHEMA_EXPORTS = {
    "knowledge.schema.json": {
        "title": "FanCue Knowledge and Chunk Metadata Contracts",
        "models": [KnowledgeDocumentFrontmatter, KnowledgeChunkPayload, KnowledgeChunk],
    },
    "common.schema.json": {
        "title": "FanCue Common Contracts",
        "models": [MatchDescriptor, RequestCorrelation],
    },
    "provenance.schema.json": {
        "title": "FanCue Source Provenance",
        "models": [SourceProvenance],
    },
    "cricket_catchup_request.schema.json": {
        "title": "FanCue Cricket Catch-Up Request",
        "models": [CricketCatchUpRequest],
    },
    "cricket_event_state.schema.json": {
        "title": "FanCue Cricket Events and State",
        "models": [CricketScoreSnapshot, CricketStateDelta, CricketDeliveryEvent],
    },
    "evidence_packet.schema.json": {
        "title": "FanCue Match Evidence Packet",
        "models": [EvidenceFact, MatchEvidencePacket],
    },
    "retrieval.schema.json": {
        "title": "FanCue Retrieval Contracts",
        "models": [RetrievalQuery, RetrievedPassage, RetrievalResult],
    },
    "explanation.schema.json": {
        "title": "FanCue Explanation Contracts",
        "models": [StructuredClaim, ExplanationPayload],
    },
    "cricket_catchup_response.schema.json": {
        "title": "FanCue Cricket Catch-Up Response",
        "models": [CricketCatchUpResponse],
    },
    "provisional_football.schema.json": {
        "title": "FanCue Provisional Football Contracts",
        "models": [FootballCatchUpRequest, FootballScoreSnapshot, FootballStateDelta, FootballMatchEvent],
    },
    "error_response.schema.json": {
        "title": "FanCue Structured Error Response",
        "models": [ErrorResponse],
    },
}


def export_schemas() -> None:
    for filename, config in SCHEMA_EXPORTS.items():
        filepath = os.path.join(CONTRACTS_DIR, filename)
        models = config["models"]
        
        if len(models) == 1:
            schema = models[0].model_json_schema()
            schema["$id"] = f"https://fancue.org/schemas/v1/{filename}"
            schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
            schema["version"] = "1.0.0"
        else:
            defs = {}
            for m in models:
                m_schema = m.model_json_schema()
                defs[m.__name__] = m_schema
            schema = {
                "$id": f"https://fancue.org/schemas/v1/{filename}",
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "title": config["title"],
                "version": "1.0.0",
                "$defs": defs,
            }
            
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)
            f.write("\n")
            
        print(f"Exported: {filename}")


if __name__ == "__main__":
    export_schemas()
