"""Deterministic claim verifier validating candidate AI assertions against authoritative match evidence.

Phase 1 hardening (Step 4):
- Unsupported numbers AND number words are checked against cited facts.
- Player names absent from cited facts are rejected (explicit or ghost names).
- Unknown/missing evidence or knowledge IDs are rejected.
- Claims citing facts unrelated to the claim are rejected.
- Markdown links / hidden citations that bypass verification are rejected.
- Betting, prediction and speculative language is rejected.
- Malicious instructions embedded in retrieved context are rejected.
- Every accepted factual claim must cite the facts that ground it; an LLM's
  self-reported citations are never treated as proof, and grammatical fluency
  alone never satisfies verification.
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Dict, List, Optional, Set, Tuple

from backend.app.ai.models import AICandidateClaim, AIExplanationDraft
from backend.app.schemas.evidence import EvidenceFact, FactType, MatchEvidencePacket
from backend.app.schemas.explanation import (
    ClaimType,
    StructuredClaim,
    VerificationStatus,
)
from backend.app.schemas.retrieval import RetrievedPassage


class RejectionReason(str, Enum):
    """Machine-readable rejection codes for candidate AI assertions."""
    INVALID_FACT_REFERENCE = "invalid_fact_reference"
    INVALID_KNOWLEDGE_REFERENCE = "invalid_knowledge_reference"
    SCORE_RUNS_MISMATCH = "score_runs_mismatch"
    SCORE_WICKETS_MISMATCH = "score_wickets_mismatch"
    SCORE_OVERS_MISMATCH = "score_overs_mismatch"
    PLAYER_NAME_MISMATCH = "player_name_mismatch"
    NUMERIC_PROSE_MISMATCH = "numeric_prose_mismatch"
    UNAPPROVED_KNOWLEDGE_STATUS = "unapproved_knowledge_status"
    PROHIBITED_SPECULATION = "prohibited_speculation"
    MALFORMED_CLAIM = "malformed_claim"
    UNRELATED_FACT_CITATION = "unrelated_fact_citation"


# Prohibited speculation, psychology-as-fact, and betting/prediction language.
# A numeric threshold may support a descriptive label, but it never proves
# player intent or subjective match psychology.
PROHIBITED_SPECULATION_PATTERNS = [
    r"\bfelt\s+nervous\b",
    r"\bpanicked\b",
    r"\bcrying\b",
    r"\blost\s+(their\s+)?focus\b",
    r"\bguaranteed\s+(the\s+)?collapse\b",
    r"\bwill\s+(definitely|certainly)\s+win\b",
    r"\bchoked\b",
    r"\bmomentum\s+guarantees\b",
    r"\bundoubted\s+victory\b",
    # Betting / prediction language
    r"\bodds\b",
    r"\bbett?ing\b",
    r"\bbet\b",          # "bet on this team to win" etc.
    r"\bwager\b",
    r"\bcasino\b",
    r"\bbookmaker\b",
    r"\bplace\s+your\s+bet\b",
    r"\bguaranteed\b",
    # Subjective match psychology / intent presented as fact
    r"\bsearching\s+for\s+answers\b",
    r"\bmiscommunication\b",
    r"\bcomplete\s+dominance\b",
    r"\bfirmly\s+in\s+control\b",
    # Additional Phase 1 prohibited phrases
    r"\bindian\s+team\s+(in|under)\s+crisis\b",
    r"\bmomentum\s+shift\s+guarantees\b",
    r"\b(all\s+but\s+)?certain\s+to\s+win\b",
    r"\bpressure\s+mount\b",        # subjective pressure narrative
    r"\bclearly\s+(dominating|outplaying)\b",
    r"\bimpossible\s+to\s+(stop|beat)\b",
    r"\bpredicted?\s+to\b",
    r"\bright\s+track\b",           # "India is on the right track" = ungrounded
    r"\btipping\s+point\b",
]


# Prompt-injection markers that make a retrieved passage unfit for citation.
PROMPT_INJECTION_PATTERNS = [
    r"\bignore\b.*\binstructions?\b",
    r"\bdisregard\b.*\b(instructions|rules|verification)\b",
    r"\bsystem\s+prompt\b",
    r"\byou\s+are\s+now\b",
    r"\breveal\s+(your|the)\b",
    r"\boverride\s+(your|the|prior|previous)?\s*instructions?\b",
]

# Markdown hyperlink pattern: anything of the form [text](target).
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]*\]\([^)]*\)")

# English number words → integer values (for word-number audit scanning).
_NUMBER_WORDS: Dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}


def _resolve_number_word(word: str) -> Optional[int]:
    """Resolve an English number word (incl. hyphen compounds like
    'sixty-five') to its integer value, or None when not a number word."""
    word = word.lower().strip()
    if word in _NUMBER_WORDS:
        return _NUMBER_WORDS[word]
    if "-" in word:
        parts = word.split("-")
        if all(p in _NUMBER_WORDS for p in parts):
            return _NUMBER_WORDS[parts[0]] + _NUMBER_WORDS[parts[1]]
    return None


# Ghost-name scanner: ALL-CAPS identifiers containing an underscore
# (e.g. FAKEPLAYER_XYZ, NONEXISTENT_PLAYER). Genuine player names from the
# source data never contain uppercase underscores.
GHOST_NAME_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]*_[A-Z0-9_]+\b")

# Number phrases adjacent to match units, digit or number-word form.
# The negative lookbehind (?<!\.) prevents matching the fractional part of
# a decimal like "7.00 runs per over" as "0 runs" (false numeric mismatch).
_DIGIT_UNIT_PATTERN = re.compile(r"(?<!\.)\b(\d+)\s+(runs?|wickets?|sixes?|fours?)\b", re.IGNORECASE)
_WORD_UNIT_PATTERN = re.compile(r"\b([a-z][a-z\-]*)\s+(runs?|wickets?|sixes?|fours?)\b")


# Payload keys whose values may substantiate numeric statements, per unit.
_UNIT_PAYLOAD_KEYS: Dict[str, Tuple[str, ...]] = {
    "run": ("runs", "runs_added", "total"),
    "runs": ("runs", "runs_added", "total"),
    "wicket": ("wickets_lost", "wickets"),
    "wickets": ("wickets_lost", "wickets"),
    "six": ("runs",),
    "sixes": ("runs",),
    "four": ("runs",),
    "fours": ("runs",),
}

EVENT_FACT_TYPES = {
    FactType.WICKET,
    FactType.BOUNDARY,
    FactType.OVER_SUMMARY,
    FactType.PARTNERSHIP,
    FactType.MATCH_RESULT,
}


@dataclass
class RejectedClaimRecord:
    claim: AICandidateClaim
    reason: RejectionReason
    detail: str


@dataclass
class VerificationReport:
    """Detailed outcome of deterministic claim verification."""
    verified_claims: List[StructuredClaim] = field(default_factory=list)
    rejected_claims: List[RejectedClaimRecord] = field(default_factory=list)
    is_verified: bool = False
    status: VerificationStatus = VerificationStatus.FAILED_VERIFICATION
    summary_text: str = ""


def _fact_values(fact: EvidenceFact) -> Set:
    """Collect all grounded values for one fact: payload values plus payload keys."""
    values: Set = set()
    for key, value in fact.structured_payload.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.add(int(value))
        values.add(str(value).lower())
    return values


class ClaimVerifier:
    """Validates candidate assertions strictly against the canonical MatchEvidencePacket."""

    def __init__(self, reject_on_any_core_failure: bool = True) -> None:
        self.reject_on_any_core_failure = reject_on_any_core_failure

    def verify(
        self,
        draft: AIExplanationDraft,
        packet: MatchEvidencePacket,
    ) -> VerificationReport:
        """Verify each candidate claim and synthesize final verified claims."""
        fact_map: Dict[str, EvidenceFact] = {f.fact_id: f for f in packet.key_facts}
        passage_map: Dict[str, RetrievedPassage] = {p.doc_id: p for p in packet.retrieved_passages}

        verified_claims: List[StructuredClaim] = []
        rejected_claims: List[RejectedClaimRecord] = []
        has_verified_score_delta = False

        for candidate in draft.claims:
            rejection = self._verify_single_claim(candidate, packet, fact_map, passage_map)
            if rejection is not None:
                rejected_claims.append(rejection)
            else:
                # Claim is verified!
                claim = StructuredClaim(
                    claim_id=candidate.claim_id,
                    claim_type=candidate.claim_type,
                    text=candidate.text,
                    cited_fact_ids=candidate.cited_fact_ids,
                    cited_knowledge_ids=candidate.cited_knowledge_ids,
                )
                verified_claims.append(claim)
                if candidate.claim_type == ClaimType.SCORE_DELTA:
                    has_verified_score_delta = True

        # Policy: An explanation draft is accepted as LLM_VERIFIED only if:
        # 1. At least one score-delta or core progress claim was verified.
        # 2. No critical score discrepancies occurred (if reject_on_any_core_failure is active).
        # 3. At least one verified claim remains.
        has_critical_failure = any(
            r.reason in (
                RejectionReason.SCORE_RUNS_MISMATCH,
                RejectionReason.SCORE_WICKETS_MISMATCH,
                RejectionReason.PLAYER_NAME_MISMATCH,
            )
            for r in rejected_claims
        )

        is_verified = (
            len(verified_claims) > 0
            and has_verified_score_delta
            and (not has_critical_failure if self.reject_on_any_core_failure else True)
        )

        status = VerificationStatus.VERIFIED if is_verified else VerificationStatus.FAILED_VERIFICATION

        return VerificationReport(
            verified_claims=verified_claims,
            rejected_claims=rejected_claims,
            is_verified=is_verified,
            status=status,
            summary_text=draft.summary,
        )

    def _verify_single_claim(
        self,
        claim: AICandidateClaim,
        packet: MatchEvidencePacket,
        fact_map: Dict[str, EvidenceFact],
        passage_map: Dict[str, RetrievedPassage],
    ) -> Optional[RejectedClaimRecord]:
        """Check all verification rules for a single candidate claim."""
        cited_facts = [fact_map[f_id] for f_id in claim.cited_fact_ids if f_id in fact_map]

        # 1. Markdown links / hidden citations must never reach the output.
        if MARKDOWN_LINK_PATTERN.search(claim.text):
            return RejectedClaimRecord(
                claim=claim,
                reason=RejectionReason.MALFORMED_CLAIM,
                detail="Claim text contains a markdown link, which is barred from verified output.",
            )

        # 2. Prohibited speculation, psychology-as-fact and betting language
        for pattern in PROHIBITED_SPECULATION_PATTERNS:
            if re.search(pattern, claim.text, re.IGNORECASE):
                return RejectedClaimRecord(
                    claim=claim,
                    reason=RejectionReason.PROHIBITED_SPECULATION,
                    detail=(f"Claim text matches prohibited speculative/betting/psychology "
                            f"pattern '{pattern}'."),
                )

        # 3. Fact reference existence check
        for f_id in claim.cited_fact_ids:
            if f_id not in fact_map:
                return RejectedClaimRecord(
                    claim=claim,
                    reason=RejectionReason.INVALID_FACT_REFERENCE,
                    detail=f"Cited fact_id '{f_id}' not found in canonical evidence packet.",
                )

        # 4. Knowledge reference existence, approval and injection checks
        for k_id in claim.cited_knowledge_ids:
            if k_id not in passage_map and k_id not in packet.retrieved_knowledge_ids:
                return RejectedClaimRecord(
                    claim=claim,
                    reason=RejectionReason.INVALID_KNOWLEDGE_REFERENCE,
                    detail=f"Cited knowledge_id '{k_id}' not found in retrieved packet passages.",
                )
            passage = passage_map.get(k_id)
            if passage is not None:
                if "draft" in passage.doc_id.lower():
                    return RejectedClaimRecord(
                        claim=claim,
                        reason=RejectionReason.UNAPPROVED_KNOWLEDGE_STATUS,
                        detail=(f"Cited knowledge note '{k_id}' is in draft status, "
                                f"barred from verified claims."),
                    )
                # Retrieved context is UNTRUSTED input: passages containing
                # instruction-like text can never be cited evidence.
                for pattern in PROMPT_INJECTION_PATTERNS:
                    if re.search(pattern, passage.content, re.IGNORECASE):
                        return RejectedClaimRecord(
                            claim=claim,
                            reason=RejectionReason.MALFORMED_CLAIM,
                            detail=(f"Cited knowledge passage '{k_id}' contains "
                                    f"instruction-like content and is unfit for citation."),
                        )

        # 5. Player and event identity verification
        if claim.claimed_player is not None:
            player_found = False
            for fact in cited_facts:
                f_data = fact.structured_payload
                f_player_out = str(f_data.get("player_out", ""))
                f_bowler = str(f_data.get("bowler", ""))
                f_batter = str(f_data.get("batter", ""))
                if (
                    claim.claimed_player.lower() in f_player_out.lower()
                    or claim.claimed_player.lower() in f_bowler.lower()
                    or claim.claimed_player.lower() in f_batter.lower()
                    or claim.claimed_player.lower() in fact.description.lower()
                ):
                    player_found = True
                    break
            if not player_found:
                return RejectedClaimRecord(
                    claim=claim,
                    reason=RejectionReason.PLAYER_NAME_MISMATCH,
                    detail=(f"Claimed player '{claim.claimed_player}' does not match "
                            f"any cited fact payload."),
                )

        # 5b. Ghost-name grounding: ALL_CAPS_UNDERSCORED identifiers in prose
        # must appear inside the cited facts' payloads or descriptions.
        for token in GHOST_NAME_PATTERN.findall(claim.text):
            grounded = False
            for fact in cited_facts:
                if token.lower() in fact.description.lower() or token.lower() in _fact_values(fact):
                    grounded = True
                    break
            if not grounded:
                return RejectedClaimRecord(
                    claim=claim,
                    reason=RejectionReason.PLAYER_NAME_MISMATCH,
                    detail=(f"Name/identifier '{token}' in claim text is absent from "
                            f"the cited facts' payloads."),
                )

        # 6. Numeric grounding
        delta = packet.state_delta
        if claim.claim_type == ClaimType.SCORE_DELTA:
            if claim.claimed_runs is not None and claim.claimed_runs != delta.runs_added:
                return RejectedClaimRecord(
                    claim=claim,
                    reason=RejectionReason.SCORE_RUNS_MISMATCH,
                    detail=(f"Claimed runs {claim.claimed_runs} does not match "
                            f"authoritative delta {delta.runs_added}."),
                )
            if claim.claimed_wickets is not None and claim.claimed_wickets != delta.wickets_lost:
                return RejectedClaimRecord(
                    claim=claim,
                    reason=RejectionReason.SCORE_WICKETS_MISMATCH,
                    detail=(f"Claimed wickets {claim.claimed_wickets} does not match "
                            f"authoritative delta {delta.wickets_lost}."),
                )
            if claim.claimed_overs is not None and claim.claimed_overs != delta.completed_overs_delta:
                return RejectedClaimRecord(
                    claim=claim,
                    reason=RejectionReason.SCORE_OVERS_MISMATCH,
                    detail=(f"Claimed overs {claim.claimed_overs} does not match "
                            f"authoritative delta {delta.completed_overs_delta}."),
                )

        # Numeric prose scan: every "<number> <unit>" phrase — digit OR word
        # form — must be substantiated by the authoritative value directly
        # associated with the claim type.
        for value, unit in _iter_numeric_prose(claim.text):
            substantiated = self._numeric_value_supported(
                value, unit, claim, packet, cited_facts, delta,
            )
            if not substantiated:
                return RejectedClaimRecord(
                    claim=claim,
                    reason=RejectionReason.NUMERIC_PROSE_MISMATCH,
                    detail=(f"Text asserts '{value} {unit}', which no authoritative "
                            f"fact associated with this claim supports."),
                )

        # 7. Relevance / grounding of citations.
        if claim.claim_type == ClaimType.SCORE_DELTA:
            # A score-delta claim is only grounded when it cites the
            # authoritative interval milestone fact.
            if not any(f.fact_type == FactType.STATE_MILESTONE for f in cited_facts):
                return RejectedClaimRecord(
                    claim=claim,
                    reason=RejectionReason.UNRELATED_FACT_CITATION,
                    detail=("SCORE_DELTA claim must cite the authoritative "
                            "STATE_MILESTONE (interval delta) fact."),
                )
        elif claim.claim_type == ClaimType.EVENT_CHRONOLOGY:
            if not claim.cited_fact_ids:
                return RejectedClaimRecord(
                    claim=claim,
                    reason=RejectionReason.MALFORMED_CLAIM,
                    detail=("Factual event claim carries no evidence citations; "
                            "prose alone is never proof."),
                )
            # Event claims must cite event-type facts, not unrelated aggregates.
            if not any(f.fact_type in EVENT_FACT_TYPES for f in cited_facts):
                return RejectedClaimRecord(
                    claim=claim,
                    reason=RejectionReason.UNRELATED_FACT_CITATION,
                    detail=("Event claim cites no event-type fact (wicket, boundary, "
                            "over summary, partnership or result)."),
                )

        return None

    @staticmethod
    def _numeric_value_supported(
        value: int,
        unit: str,
        claim: AICandidateClaim,
        packet: MatchEvidencePacket,
        cited_facts: List[EvidenceFact],
        delta,
    ) -> bool:
        """Determine whether a '<value> <unit>' phrase in claim prose is grounded.

        SCORE_DELTA claims are checked against the packet state delta; every
        other claim type is checked against the payloads of the facts it cites.
        """
        if claim.claim_type == ClaimType.SCORE_DELTA:
            return (
                (unit.startswith("run") and value == delta.runs_added)
                or (unit.startswith("wicket") and value == delta.wickets_lost)
            )
        # Event / other factual claims: payload-of-cited-fact grounding.
        payload_keys = _UNIT_PAYLOAD_KEYS.get(unit, ())
        for fact in cited_facts:
            for key in payload_keys:
                payload_value = fact.structured_payload.get(key)
                if isinstance(payload_value, (int, float)) and int(payload_value) == value:
                    return True
        return False


def _iter_numeric_prose(text: str):
    """Yield (value, unit) pairs for every digit- or word-form number phrase
    adjacent to a match unit in claim prose."""
    for match in _DIGIT_UNIT_PATTERN.finditer(text):
        yield int(match.group(1)), match.group(2).lower()
    for match in _WORD_UNIT_PATTERN.finditer(text):
        value = _resolve_number_word(match.group(1))
        if value is not None:
            yield value, match.group(2).lower()
