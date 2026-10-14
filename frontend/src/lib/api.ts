// FanCue API client — all backend calls go through here.
// No API keys or secrets ever appear in this file.
// Base URL is configured via the VITE_API_BASE_URL environment variable.

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types aligned with backend Pydantic schemas
// ---------------------------------------------------------------------------

export interface MatchDescriptor {
  match_id: string;
  sport: "cricket" | "football";
  name: string;
  format: string;
  teams: [string, string];
  date: string; // YYYY-MM-DD
  venue?: string | null;
  mode: "replay" | "live";
  source_id: string;
  source_revision: string;
  supported_innings: number[];
}

export interface MatchListResponse {
  matches: MatchDescriptor[];
  total: number;
}

export interface InningsIntervalOption {
  innings: number;
  start_after_over: number;
  end_after_over: number;
  label: string;
}

export interface IntervalsResponse {
  match_id: string;
  intervals: InningsIntervalOption[];
  total_innings: number;
}

export interface CricketCatchUpRequest {
  match_id: string;
  interval: {
    innings: number;
    start_after_over: number;
    end_after_over: number;
  };
  language?: "en" | "ta";
}

export interface CricketScoreSnapshot {
  runs: number;
  wickets: number;
  overs_completed: number;
  legal_balls_in_over: number;
  extras_total: number;
  run_rate: number;
}

export interface CricketStateDelta {
  runs_added: number;
  wickets_lost: number;
  completed_overs_delta: number;
  legal_balls_added: number;
  extras_added: number;
  interval_run_rate: number;
}

export interface EvidenceFact {
  fact_id: string;
  fact_type: string;
  match_id: string;
  source_revision: string;
  referenced_event_ids: string[];
  description: string;
  structured_payload?: Record<string, unknown>;
}

export interface RetrievedPassage {
  doc_id: string;
  sport: string;
  language: string;
  topic: string;
  content: string;
  source_name: string;
  source_url: string;
  license: string;
  score: number;
}

export interface MatchEvidencePacket {
  packet_id: string;
  match_id: string;
  sport: string;
  interval_summary: string;
  state_before: CricketScoreSnapshot;
  state_after: CricketScoreSnapshot;
  state_delta: CricketStateDelta;
  key_facts: EvidenceFact[];
  retrieved_knowledge_ids: string[];
  retrieved_passages?: RetrievedPassage[];
  provenance: {
    source_name: string;
    source_url: string;
    license_name: string;
    attribution_text: string;
    dataset_revision: string;
  };
}

export interface StructuredClaim {
  claim_id: string;
  claim_type: string;
  text: string;
  cited_fact_ids: string[];
  cited_knowledge_ids: string[];
}

export interface ExplanationPayload {
  summary: string;
  claims: StructuredClaim[];
  generation_mode: "llm_verified" | "deterministic_fallback";
  verification_status: "verified" | "failed_verification" | "unverified_fallback";
  fallback_reason: "none" | "timeout" | "llm_error" | "fact_mismatch" | "unsupported_claims" | "disabled";
  provider?: string;
  model?: string;
}

export interface CricketBallStory {
  delivery_number: number;
  display: string;
  event_label: string;
  batter: string;
  bowler: string;
  runs_off_bat: number;
  total_runs: number;
  extras: number;
  is_legal: boolean;
  wicket_detail?: string | null;
}

export interface CricketOverStory {
  over_number: number;
  runs: number;
  wickets: number;
  extras: number;
  legal_balls: number;
  score_after_runs: number;
  score_after_wickets: number;
  run_rate_after: number;
  recap: string;
  highlights: string[];
  balls: CricketBallStory[];
}

export interface CricketCatchUpResponse {
  match: MatchDescriptor;
  interval: { innings: number; start_after_over: number; end_after_over: number };
  state_before: CricketScoreSnapshot;
  state_after: CricketScoreSnapshot;
  state_delta: CricketStateDelta;
  over_by_over: CricketOverStory[];
  evidence_packet: MatchEvidencePacket;
  explanation: ExplanationPayload;
  language: string;
  mode: "replay" | "live";
  generated_at: string;
  warnings: string[];
}

// ---------------------------------------------------------------------------
// API client functions
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
  timeoutMs = 30_000,
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const resp = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(options?.headers ?? {}),
      },
    });

    if (!resp.ok) {
      let message = `API error ${resp.status}`;
      try {
        const data = await resp.json();
        message = data?.error?.message ?? data?.detail ?? message;
      } catch {
        // Ignore a non-JSON error body; retain the HTTP status.
      }
      throw new ApiError(resp.status, message);
    }

    return await resp.json() as T;
  } catch (error) {
    if (controller.signal.aborted) {
      throw new ApiError(0, `Request timed out after ${Math.ceil(timeoutMs / 1000)} seconds.`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export interface NearLiveInningsScore {
  r: number;
  w: number;
  o: number;
  inning: string;
}

export interface NearLiveTeamInfo {
  name: string;
  shortname?: string | null;
  img?: string | null;
}

export interface NearLiveMatchItem {
  id: string;
  name: string;
  match_type: string;
  status: string;
  venue?: string | null;
  date: string;
  date_time_gmt?: string | null;
  teams: string[];
  team_info: NearLiveTeamInfo[];
  score: NearLiveInningsScore[];
  series_id?: string | null;
  match_started: boolean;
  match_ended: boolean;
  source: string;
  source_url: string;
  freshness: string;
  license: string;
  retrieved_at: string;
}

export interface NearLiveMatchesResponse {
  status: "success" | "unconfigured" | "rate_limited" | "error";
  configured: boolean;
  matches: NearLiveMatchItem[];
  total: number;
  cached: boolean;
  cached_at?: string | null;
  hits_today?: number | null;
  hits_left?: number | null;
  message?: string | null;
}

export interface NearLiveScorecardResponse {
  status: "success" | "unconfigured" | "rate_limited" | "error" | "not_found";
  configured: boolean;
  match?: NearLiveMatchItem | null;
  scorecard?: Record<string, unknown> | null;
  can_reconstruct_interval: boolean;
  limitation_reason: string;
  cached: boolean;
  cached_at?: string | null;
  message?: string | null;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export async function fetchHealth(timeoutMs = 65_000): Promise<HealthResponse> {
  // Render's free service may need time to wake. The UI retries once on failure.
  return apiFetch<HealthResponse>("/healthz", undefined, timeoutMs);
}

export async function fetchMatches(timeoutMs = 20_000): Promise<MatchListResponse> {
  return apiFetch<MatchListResponse>("/matches", undefined, timeoutMs);
}

export async function fetchNearLiveMatches(refresh = false): Promise<NearLiveMatchesResponse> {
  const query = refresh ? "?refresh=true" : "";
  return apiFetch<NearLiveMatchesResponse>(`/matches/near-live${query}`);
}

export async function fetchNearLiveScorecard(matchId: string, refresh = false): Promise<NearLiveScorecardResponse> {
  const query = refresh ? "?refresh=true" : "";
  return apiFetch<NearLiveScorecardResponse>(`/matches/near-live/${encodeURIComponent(matchId)}/scorecard${query}`);
}

export async function fetchIntervals(matchId: string): Promise<IntervalsResponse> {
  return apiFetch<IntervalsResponse>(`/matches/${encodeURIComponent(matchId)}/intervals`);
}

export async function fetchCatchUp(
  request: CricketCatchUpRequest
): Promise<CricketCatchUpResponse> {
  return apiFetch<CricketCatchUpResponse>(
    "/catchup",
    {
      method: "POST",
      body: JSON.stringify(request),
    },
    45_000,
  );
}

