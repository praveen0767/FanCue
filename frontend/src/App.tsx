import { useState, useCallback, useEffect, useRef } from "react";
import "./index.css";
import {
  fetchMatches,
  fetchIntervals,
  fetchCatchUp,
  fetchHealth,
  fetchNearLiveMatches,
  fetchNearLiveScorecard,
  type MatchDescriptor,
  type InningsIntervalOption,
  type CricketCatchUpResponse,
  type EvidenceFact,
  type NearLiveMatchItem,
  type NearLiveScorecardResponse,
} from "./lib/api";


/** Keep provider diagnostics useful to operators without exposing raw errors to fans. */
function friendlyProviderMessage(
  message: string | null | undefined,
  context: "near-live" | "scorecard" = "near-live",
): string {
  const detail = (message ?? "").toLowerCase();
  if (
    detail.includes("cricketdata.org rejected") ||
    detail.includes("invalid api key") ||
    detail.includes("invalid_api_key") ||
    detail.includes("authentication failed") ||
    detail.includes("http 401") ||
    detail.includes("unauthorized")
  ) {
    return "CricketData.org rejected the key stored in Render. Open Render → fancue-api → Environment, replace CRICKET_DATA_API_KEY with a valid key from your CricketData.org account, save the change, then redeploy. Return here and tap Refresh. Historical Replay remains available.";
  }
  if (detail.includes("not configured") || detail.includes("api key is not configured")) {
    return "Near-live cricket is not configured yet. Add CRICKET_DATA_API_KEY in Render → fancue-api → Environment using a valid key from your CricketData.org account, then redeploy.";
  }
  if (
    detail.includes("quota") ||
    detail.includes("rate limit") ||
    detail.includes("daily limit") ||
    detail.includes("hits left") ||
    detail.includes("allowance")
  ) {
    return "CricketData.org's request allowance is exhausted. Try again after it resets; Historical Replay remains available.";
  }
  if (context === "scorecard") {
    return "This scorecard could not be refreshed from CricketData.org. Return to Historical Replay for the full ball-by-ball catch-up.";
  }
  return "The near-live feed is temporarily unavailable. Historical Replay remains available.";
}

/** Translate infrastructure warnings into calm, product-level language. */
function friendlyStoryWarning(message: string): string {
  const detail = message.toLowerCase();
  if (
    detail.includes("ai explanation unavailable") ||
    detail.includes("llm call timed out") ||
    detail.includes("llm generation skipped") ||
    detail.includes("ai claims failed")
  ) {
    return "FanCue's AI storyteller is temporarily unavailable, so this recap is built directly from the verified match record.";
  }
  if (detail.includes("ai explanation generated via")) {
    return "The AI story was checked against the recorded match facts.";
  }
  return message;
}

/** Remove machine-style event prefixes while preserving the recorded fact itself. */
function humanizeFactDescription(description: string): string {
  return description
    .replace(/^(WICKET|SIX|FOUR|BOUNDARY|HIGH-SCORING OVER):\s*/i, "")
    .trim();
}


// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

function formatBadgeClass(format: string): string {
  const f = format.toLowerCase();
  if (f.includes("t20") || f.includes("twenty")) return "badge badge--t20";
  if (f === "odi") return "badge badge--odi";
  if (f === "test") return "badge badge--test";
  return "badge badge--default";
}

function formatScore(runs: number, wickets: number): string {
  return `${runs}/${wickets}`;
}

function formatOvers(overs: number): string {
  return `(${overs.toFixed(1)} ov)`;
}

/** Map an innings IntervalOption list to "natural phase" chips for T20/ODI/Test */
function buildPhaseChips(
  intervals: InningsIntervalOption[],
  format: string,
): Array<{ label: string; range: string; interval: InningsIntervalOption; tag?: string }> {
  const f = format.toLowerCase();
  const isT20 = f.includes("t20") || f.includes("twenty");
  const isODI = f === "odi";

  // Boundary definitions (0-indexed after-over convention)
  const phases: Array<{ name: string; start: number; end: number; tag?: string }> = isT20
    ? [
        { name: "Powerplay",       start: 0,  end: 6  },
        { name: "Middle Overs",    start: 6,  end: 15 },
        { name: "Death & Finish",  start: 15, end: 20, tag: "Crucial" },
      ]
    : isODI
    ? [
        { name: "Powerplay",       start: 0,  end: 10 },
        { name: "Middle Overs",    start: 10, end: 40 },
        { name: "Death Overs",     start: 40, end: 50, tag: "Crucial" },
      ]
    : [
        // Test — use actual innings boundaries
        { name: "Opening Phase",   start: 0,  end: 20 },
        { name: "Middle Session",  start: 20, end: 60 },
        { name: "Late Session",    start: 60, end: 90 },
      ];

  return phases.map((p) => {
    // Find the best matching interval from the real list
    const match = findBestInterval(intervals, p.start, p.end);
    return {
      label: p.name,
      range: `Overs ${p.start + 1} – ${p.end}`,
      interval: match,
      tag: p.tag,
    };
  });
}

function buildWindowChips(
  intervals: InningsIntervalOption[],
  totalOvers: number,
): Array<{ label: string; interval: InningsIntervalOption }> {
  const windows = [3, 5, 6, 10, 12];
  const results: Array<{ label: string; interval: InningsIntervalOption }> = [];

  for (const n of windows) {
    const end = totalOvers;
    const start = Math.max(0, end - n);
    if (start >= end) continue;
    const iv = findBestInterval(intervals, start, end);
    if (iv) {
      results.push({ label: `Last ${n} Overs`, interval: iv });
    }
  }

  // Full innings
  if (intervals.length > 0) {
    const sorted = [...intervals].sort((a, b) => a.start_after_over - b.start_after_over);
    const firstIv = sorted[0];
    const lastIv = sorted[sorted.length - 1];
    const fullIv: InningsIntervalOption = {
      innings: firstIv.innings,
      start_after_over: firstIv.start_after_over,
      end_after_over: lastIv.end_after_over,
      label: "Full Innings",
    };
    results.push({ label: "Full Innings", interval: fullIv });
  }

  return results;
}

/** Pick the interval whose boundaries are closest to the requested start/end. */
function findBestInterval(
  intervals: InningsIntervalOption[],
  wantStart: number,
  wantEnd: number,
): InningsIntervalOption {
  if (intervals.length === 0) {
    return { innings: 0, start_after_over: wantStart, end_after_over: wantEnd, label: "" };
  }
  let best = intervals[0];
  let bestScore = Infinity;
  for (const iv of intervals) {
    const score =
      Math.abs(iv.start_after_over - wantStart) +
      Math.abs(iv.end_after_over - wantEnd);
    if (score < bestScore) {
      bestScore = score;
      best = iv;
    }
  }
  return best;
}

function totalOversForFormat(format: string): number {
  const f = format.toLowerCase();
  if (f.includes("t20") || f.includes("twenty")) return 20;
  if (f === "odi") return 50;
  return 90; // Test approximation
}

// ---------------------------------------------------------------------------
// Shared sub-components
// ---------------------------------------------------------------------------

function Spinner() {
  return (
    <div className="state-loading" role="status" aria-label="Loading">
      <div className="spinner" />
      <p>Loading…</p>
    </div>
  );
}

function ErrorMsg({ message }: { message: string }) {
  return (
    <div className="state-error" role="alert">
      <span aria-hidden>⚠</span> {message}
    </div>
  );
}

function TopNav({
  onLogoClick,
  showBack,
  onBack,
  sessionLabel,
}: {
  onLogoClick: () => void;
  showBack?: boolean;
  onBack?: () => void;
  sessionLabel?: string;
}) {
  return (
    <header className="topnav">
      <div className="topnav__brand">
        <button
          onClick={onLogoClick}
          style={{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex", alignItems: "center" }}
          aria-label="FanCue home"
        >
          <img
            src="/assets/Logo.png"
            alt="FanCue"
            className="topnav__logo"
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        </button>
        <span className="topnav__badge">Historical Replay · Cricsheet Archive</span>
      </div>

      {sessionLabel && (
        <div className="topnav__replay-pill">
          <span className="topnav__replay-dot" />
          {sessionLabel}
        </div>
      )}

      <div className="topnav__right">
        {showBack && onBack && (
          <button className="icon-btn" onClick={onBack} aria-label="Back">
            ← Back
          </button>
        )}
        <div className="topnav__replay-pill" style={{ background: "none" }}>
          <span className="topnav__tagline">Catch the moment. Understand the game.</span>
        </div>
      </div>
    </header>
  );
}

// Toast hook
function useToast() {
  const [visible, setVisible] = useState(false);
  const [msg, setMsg] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback((message: string) => {
    setMsg(message);
    setVisible(true);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setVisible(false), 3000);
  }, []);

  return { visible, msg, show };
}

// Prefers reduced motion hook
function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => {
    if (typeof window === "undefined" || !window.matchMedia) return false;
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  });

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  return reduced;
}

// Authoritative Score Count-Up Hook (600-800ms)
function useCountUp(target: number, duration: number = 700, enabled: boolean = true): number {
  const [displayValue, setDisplayValue] = useState(target);
  const prevTargetRef = useRef(target);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled) {
      setDisplayValue(target);
      prevTargetRef.current = target;
      return;
    }

    const startVal = prevTargetRef.current;
    prevTargetRef.current = target;

    if (startVal === target) {
      setDisplayValue(target);
      return;
    }

    const startTime = performance.now();

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(1, elapsed / duration);
      // Quadratic deceleration curve
      const eased = 1 - (1 - progress) * (1 - progress);
      const current = Math.round(startVal + (target - startVal) * eased);
      setDisplayValue(current);

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      } else {
        setDisplayValue(target);
      }
    };

    frameRef.current = requestAnimationFrame(animate);

    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [target, duration, enabled]);

  return displayValue;
}

// ---------------------------------------------------------------------------
// SCREEN 1 — Match Discovery
// ---------------------------------------------------------------------------

function MatchDiscovery({
  onMatchSelected,
}: {
  onMatchSelected: (match: MatchDescriptor) => void;
}) {
  const [sourceTab, setSourceTab] = useState<"historical" | "nearlive">("historical");
  const [matches, setMatches] = useState<MatchDescriptor[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [formatFilter, setFormatFilter] = useState("all");
  const [apiStatus, setApiStatus] = useState<string>("Checking…");

  // Near-live state
  const [nearLiveMatches, setNearLiveMatches] = useState<NearLiveMatchItem[] | null>(null);
  const [nearLiveLoading, setNearLiveLoading] = useState(false);
  const [nearLiveError, setNearLiveError] = useState<string | null>(null);
  const [nearLiveNotice, setNearLiveNotice] = useState<string | null>(null);
  const [nearLiveHits, setNearLiveHits] = useState<{ hitsToday?: number | null; hitsLeft?: number | null }>({});
  const [selectedNearLive, setSelectedNearLive] = useState<NearLiveMatchItem | null>(null);
  const [scorecardData, setScorecardData] = useState<NearLiveScorecardResponse | null>(null);
  const [scorecardLoading, setScorecardLoading] = useState(false);
  const [scorecardError, setScorecardError] = useState<string | null>(null);
  const scorecardDrawerRef = useRef<HTMLElement | null>(null);
  const scorecardRequestIdRef = useRef(0);

  // Health check on mount for real API status
  useEffect(() => {
    fetchHealth()
      .then((h) => setApiStatus(h.status === "ok" ? "Operational" : h.status))
      .catch(() => setApiStatus("Offline"));
  }, []);

  // Load historical matches
  useEffect(() => {
    setLoading(true);
    fetchMatches()
      .then((data) => setMatches(data.matches))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load matches"))
      .finally(() => setLoading(false));
  }, []);

  // Fetch near-live matches when tab is clicked
  const loadNearLive = useCallback((refresh = false) => {
    setNearLiveLoading(true);
    setNearLiveError(null);
    setNearLiveNotice(null);
    fetchNearLiveMatches(refresh)
      .then((data) => {
        if (data.status === "unconfigured") {
          setNearLiveNotice("Near-live cricket requires a valid CricketData.org API key. Add CRICKET_DATA_API_KEY in Render → fancue-api → Environment, save it, then redeploy.");
          setNearLiveMatches([]);
        } else if (data.status === "error" || data.status === "rate_limited") {
          setNearLiveError(friendlyProviderMessage(data.message || "Unable to fetch near-live matches."));
          setNearLiveMatches(data.matches || []);
        } else {
          setNearLiveMatches(data.matches);
          setNearLiveNotice(data.message || null);
        }
        setNearLiveHits({ hitsToday: data.hits_today, hitsLeft: data.hits_left });
      })
      .catch((err) => {
        setNearLiveError(friendlyProviderMessage(err instanceof Error ? err.message : "Failed to load near-live matches"));
      })
      .finally(() => setNearLiveLoading(false));
  }, []);

  useEffect(() => {
    if (sourceTab === "nearlive" && nearLiveMatches === null && !nearLiveLoading) {
      loadNearLive(false);
    }
  }, [sourceTab, nearLiveMatches, nearLiveLoading, loadNearLive]);

  // Fetch the selected scorecard independently from match-list loading.
  // The provider may return HTTP 200 with an application-level error status.
  function loadNearLiveScorecard(m: NearLiveMatchItem, refresh = false) {
    const requestId = ++scorecardRequestIdRef.current;
    setScorecardData(null);
    setScorecardError(null);
    setScorecardLoading(true);

    fetchNearLiveScorecard(m.id, refresh)
      .then((resp) => {
        if (requestId !== scorecardRequestIdRef.current) return;
        setScorecardData(resp);
        if (resp.status !== "success") {
          setScorecardError(
            friendlyProviderMessage(
              resp.message || resp.limitation_reason || "Scorecard unavailable",
              "scorecard",
            ),
          );
        }
      })
      .catch((error) => {
        if (requestId !== scorecardRequestIdRef.current) return;
        setScorecardData(null);
        setScorecardError(
          friendlyProviderMessage(
            error instanceof Error ? error.message : "Scorecard request failed",
            "scorecard",
          ),
        );
      })
      .finally(() => {
        if (requestId === scorecardRequestIdRef.current) {
          setScorecardLoading(false);
        }
      });
  }

  function handleSelectNearLive(m: NearLiveMatchItem) {
    setSelectedNearLive(m);
    loadNearLiveScorecard(m);
  }

  function closeNearLiveScorecard() {
    scorecardRequestIdRef.current += 1;
    setSelectedNearLive(null);
    setScorecardData(null);
    setScorecardError(null);
    setScorecardLoading(false);
  }

  // The scorecard panel used to render after the entire match list. Scroll it
  // into view after the request finishes so selecting a card never looks inert.
  useEffect(() => {
    if (!selectedNearLive || !scorecardDrawerRef.current) return;
    // Scroll once immediately to reveal the loading state, then again after the
    // scorecard request settles so the panel never appears inert below the list.
    const timer = window.setTimeout(() => {
      scorecardDrawerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, scorecardLoading ? 10 : 80);
    return () => window.clearTimeout(timer);
  }, [selectedNearLive?.id, scorecardLoading]);


  const filteredHistorical = (matches ?? []).filter((m) => {
    const q = search.toLowerCase();
    const matchesSearch =
      !q ||
      m.name.toLowerCase().includes(q) ||
      (m.venue ?? "").toLowerCase().includes(q) ||
      m.date.includes(q) ||
      m.teams.some((t) => t.toLowerCase().includes(q));

    const matchesFormat =
      formatFilter === "all" ||
      m.format.toLowerCase().includes(formatFilter.toLowerCase());

    return matchesSearch && matchesFormat;
  });

  const filteredNearLive = (nearLiveMatches ?? []).filter((m) => {
    const q = search.toLowerCase();
    const matchesSearch =
      !q ||
      m.name.toLowerCase().includes(q) ||
      (m.venue ?? "").toLowerCase().includes(q) ||
      m.date.includes(q) ||
      m.teams.some((t) => t.toLowerCase().includes(q));

    const matchesFormat =
      formatFilter === "all" ||
      m.match_type.toLowerCase().includes(formatFilter.toLowerCase());

    return matchesSearch && matchesFormat;
  });

  const availableFormats = sourceTab === "historical"
    ? (matches ? [...new Set(matches.map((m) => m.format))] : [])
    : (nearLiveMatches ? [...new Set(nearLiveMatches.map((m) => m.match_type.toUpperCase()))] : []);

  const activeScorecardMatch = scorecardData?.match ?? selectedNearLive;
  const activeScoreRows =
    activeScorecardMatch?.score?.length
      ? activeScorecardMatch.score
      : selectedNearLive?.score ?? [];
  const scorecardDetailFields = Object.entries(scorecardData?.scorecard ?? {})
    .filter(([key, value]) =>
      !/^(id|name|teams|teaminfo|series_id|date|venue|matchtype|score|scorecard)$/i.test(key) &&
      (typeof value === "string" || typeof value === "number" || typeof value === "boolean") &&
      String(value).trim().length > 0
    )
    .slice(0, 8);
  const livePulseText = (() => {
    if (!activeScorecardMatch) return "Select a match to see its live snapshot.";
    const latest = activeScoreRows[activeScoreRows.length - 1];
    if (latest) {
      return `${latest.inning || "Current innings"}: ${latest.r}/${latest.w} after ${latest.o} overs. ${activeScorecardMatch.status}`;
    }
    return activeScorecardMatch.status || "The provider has not reported an innings score yet.";
  })();

  // Stadium images cycle for visual variety
  const STADIUM_IMGS = [
    "/assets/stadium-card-1.webp",
    "/assets/stadium-card-2.webp",
  ];

  return (
    <div className="page">
      {/* Stadium Hero Banner */}
      <div className="discovery-hero-banner">
        <div className="discovery-hero-banner__content">
          <section className="discovery-hero">
            <div>
              <div className="discovery-hero__eyebrow">
                <span className="chip chip--outline">
                  Verified Sports Engine
                </span>
                <span className="chip chip--magenta">Evidence-Grounded</span>
              </div>
              <h1 className="discovery-hero__h1">
                Missed part of the match?{" "}
                <span>Get the story.</span>
              </h1>
              <p className="discovery-hero__sub">
                Reconstruct missed intervals with verified ball-by-ball evidence or explore
                near-live fixtures. Grounded in inspectable facts — no hallucinated statistics.
              </p>
            </div>

            <div className="telemetry-widget">
              <div className="telemetry-widget__label">
                <span>⟳</span> FanCue Engine Telemetry
              </div>
              <div className="telemetry-widget__stats">
                <div className="telemetry-stat">
                  <div className="telemetry-stat__value">
                    {sourceTab === "historical" ? (matches ? matches.length : "—") : (nearLiveMatches ? nearLiveMatches.length : "—")}
                  </div>
                  <div className="telemetry-stat__label">Matches Loaded</div>
                </div>
                <div className="telemetry-stat">
                  <div className="telemetry-stat__value" style={{ color: "var(--secondary-fixed-dim)" }}>
                    Audited
                  </div>
                  <div className="telemetry-stat__label">Ball Ledger</div>
                </div>
                <div className="telemetry-stat">
                  <div className="telemetry-stat__value" style={{ color: "var(--primary-fixed-dim)" }}>
                    {apiStatus}
                  </div>
                  <div className="telemetry-stat__label">API Status</div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>

      {/* Source Selector Tabs */}
      <div className="source-selector" role="tablist" aria-label="Match source">
        <button
          id="source-tab-historical"
          className={`source-tab${sourceTab === "historical" ? " source-tab--active" : ""}`}
          role="tab"
          aria-selected={sourceTab === "historical"}
          onClick={() => { closeNearLiveScorecard(); setSourceTab("historical"); }}
        >
          <span>Historical Replay</span>
          <span className="source-tab__badge">Full Catch-Up & Evidence</span>
        </button>
        <button
          id="source-tab-nearlive"
          className={`source-tab${sourceTab === "nearlive" ? " source-tab--active" : ""}`}
          role="tab"
          aria-selected={sourceTab === "nearlive"}
          onClick={() => setSourceTab("nearlive")}
        >
          <span className="pulse-dot" aria-hidden />
          <span>Near-live Cricket</span>
          <span className="source-tab__badge source-tab__badge--live">~5m delay</span>
        </button>
      </div>

      {/* Filter bar */}
      <div className="filter-bar">
        <div className="filter-search">
          <span className="filter-search__icon">🔍</span>
          <input
            id="archive-search-input"
            className="filter-search__input"
            type="text"
            placeholder="Filter by team, venue or date…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search matches"
          />
        </div>

        <div className="filter-tabs" role="group" aria-label="Format filter">
          <button
            className={`filter-tab${formatFilter === "all" ? " filter-tab--active" : ""}`}
            onClick={() => setFormatFilter("all")}
          >
            All Formats
          </button>
          {availableFormats.map((f) => (
            <button
              key={f}
              className={`filter-tab${formatFilter.toLowerCase() === f.toLowerCase() ? " filter-tab--active" : ""}`}
              onClick={() => setFormatFilter(f.toLowerCase())}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* SECTION 1: HISTORICAL REPLAYS */}
      {sourceTab === "historical" && (
        <>
          {loading && (
            <ul className="match-grid" aria-label="Loading matches">
              {[1, 2, 3].map((i) => (
                <li key={i}>
                  <div className="skeleton skeleton-card" style={{ height: 82 }} />
                </li>
              ))}
            </ul>
          )}

          {error && <ErrorMsg message={error} />}

          {!loading && matches && filteredHistorical.length === 0 && (
            <div className="state-empty">
              {search
                ? `No historical matches found for "${search}".`
                : "No historical matches available."}
            </div>
          )}

          {!loading && filteredHistorical.length > 0 && (
            <ul className="match-grid" role="listbox" aria-label="Available matches">
              {filteredHistorical.map((m, idx) => (
                <li key={m.match_id} role="option" aria-selected={false}>
                  <button
                    id={`match-${m.match_id}`}
                    className="match-card match-card--stadium match-card--animate-in"
                    style={{ animationDelay: `${idx * 60}ms` }}
                    onClick={() => onMatchSelected(m)}
                    aria-label={`Select match: ${m.name}`}
                  >
                    <div className="match-card__body">
                      <div className="match-card__eyebrow">
                        <span className={formatBadgeClass(m.format)}>{m.format}</span>
                        <span className="chip chip--outline" style={{ fontSize: "0.58rem" }}>
                          Historical Replay · Cricsheet
                        </span>
                      </div>
                      <div className="match-card__name">{m.name}</div>
                      <div className="match-card__meta">
                        <span>{m.date}</span>
                        {m.venue && (
                          <>
                            <span className="match-card__meta-dot">·</span>
                            <span>{m.venue}</span>
                          </>
                        )}
                        <span className="match-card__meta-dot">·</span>
                        <span>{m.supported_innings.length} innings</span>
                      </div>
                      <div className="match-card__cta" aria-hidden>
                        Catch up →
                      </div>
                    </div>
                    <div className="match-card__stadium-img" aria-hidden>
                      <img
                        src={STADIUM_IMGS[idx % STADIUM_IMGS.length]}
                        alt=""
                        loading="lazy"
                      />
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {/* SECTION 2: NEAR-LIVE CRICKET */}
      {sourceTab === "nearlive" && (
        <>
          <div className="near-live-notice">
            <div className="near-live-notice__text">
              <span>📡</span>
              <span>
                <strong>CricketData.org Near-Live Feed:</strong> Updates may lag by up to ~5 minutes.
                FanCue caches responses to reduce unnecessary provider requests.
                {nearLiveHits.hitsLeft !== undefined && nearLiveHits.hitsLeft !== null && (
                  <> · Remaining Hits Today: <strong>{nearLiveHits.hitsLeft}</strong></>
                )}
              </span>
            </div>
            <button
              id="refresh-nearlive-btn"
              className="icon-btn"
              onClick={() => loadNearLive(true)}
              disabled={nearLiveLoading}
              aria-label="Refresh near-live matches"
            >
              {nearLiveLoading ? "Refreshing…" : "⟳ Refresh"}
            </button>
          </div>

          {nearLiveNotice && (
            <div className="state-empty" style={{ marginBottom: 16 }}>
              ℹ {nearLiveNotice}
            </div>
          )}

          {nearLiveLoading && (
            <ul className="match-grid" aria-label="Loading near-live matches">
              {[1, 2, 3].map((i) => (
                <li key={i}>
                  <div className="skeleton skeleton-card" style={{ height: 100 }} />
                </li>
              ))}
            </ul>
          )}

          {nearLiveError && <ErrorMsg message={nearLiveError} />}

          {!nearLiveLoading && !nearLiveError && !nearLiveNotice && nearLiveMatches && filteredNearLive.length === 0 && (
            <div className="state-empty">
              {search
                ? `No near-live matches found for "${search}".`
                : "No active near-live matches currently reported by the provider."}
            </div>
          )}

          {!nearLiveLoading && filteredNearLive.length > 0 && (
            <ul className="match-grid" role="listbox" aria-label="Near-live matches">
              {filteredNearLive.map((m, idx) => {
                const isSelected = selectedNearLive?.id === m.id;
                return (
                  <li key={m.id} role="option" aria-selected={isSelected}>
                    <button
                      id={`nearlive-${m.id}`}
                      className={`match-card match-card--stadium match-card--animate-in${isSelected ? " match-card--selected" : ""}`}
                      style={{ animationDelay: `${idx * 60}ms` }}
                      onClick={() => handleSelectNearLive(m)}
                      aria-label={`View scorecard for: ${m.name}`}
                    >
                      <div className="match-card__body" style={{ width: "100%" }}>
                        <div className="match-card__eyebrow">
                          <span className={formatBadgeClass(m.match_type)}>{m.match_type.toUpperCase()}</span>
                          <span className="chip chip--magenta" style={{ fontSize: "0.58rem", display: "inline-flex", alignItems: "center", gap: 4 }}>
                            <span className="pulse-dot" style={{ width: 4, height: 4 }} />
                            Near-live
                          </span>
                        </div>
                        <div className="match-card__name">{m.name}</div>
                        <div className="match-card__meta">
                          <span>{m.date}</span>
                          {m.venue && (
                            <>
                              <span className="match-card__meta-dot">·</span>
                              <span>{m.venue}</span>
                            </>
                          )}
                          <span className="match-card__meta-dot">·</span>
                          <span style={{ color: "var(--primary-container)" }}>{m.status}</span>
                        </div>

                        {/* Scores summary */}
                        {m.score && m.score.length > 0 && (
                          <div className="near-live-card__scores">
                            {m.score.map((sc, scIdx) => (
                              <div key={scIdx} className="near-live-score-row">
                                <span className="near-live-score-row__label">{sc.inning}:</span>
                                <span>{sc.r}/{sc.w} ({sc.o} ov)</span>
                              </div>
                            ))}
                          </div>
                        )}

                        <div className="match-card__cta" aria-hidden>
                          {isSelected ? "Insights open ↓" : "View live insights →"}
                        </div>
                      </div>
                      <div className="match-card__stadium-img" aria-hidden>
                        <img
                          src={STADIUM_IMGS[idx % STADIUM_IMGS.length]}
                          alt=""
                          loading="lazy"
                        />
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          {/* Near-live Scorecard Inspection Drawer */}
          {selectedNearLive && (
            <section id="scorecard-drawer" ref={scorecardDrawerRef} className="scorecard-drawer" aria-label="Near-live match insights" aria-busy={scorecardLoading}>
              <div className="scorecard-drawer__header">
                <div>
                  <div className="chip chip--magenta" style={{ marginBottom: 6, display: "inline-flex", alignItems: "center", gap: 4 }}>
                    <span className="pulse-dot" style={{ width: 4, height: 4 }} />
                    Near-live Scorecard · CricketData.org
                  </div>
                  <h2 style={{ fontSize: "1.25rem", margin: "4px 0", fontFamily: "var(--font-display)" }}>
                    {selectedNearLive.name}
                  </h2>
                  <div style={{ fontSize: "0.82rem", color: "var(--on-surface-variant)" }}>
                    {selectedNearLive.date} · {selectedNearLive.venue || "Venue not specified"} · Status: <strong>{selectedNearLive.status}</strong>
                  </div>
                </div>
                <button
                  className="icon-btn"
                  onClick={closeNearLiveScorecard}
                  aria-label="Close scorecard"
                >
                  ✕ Close
                </button>
              </div>

              {scorecardLoading ? (
                <Spinner />
              ) : (
                <>
                  {scorecardError ? (
                    <div className="scorecard-disclaimer" role="status">
                      <strong>Live scorecard detail unavailable.</strong>{" "}
                      {scorecardError}
                      <div style={{ marginTop: 6 }}>
                        The latest match-list score remains visible below when the provider has supplied one.
                      </div>
                    </div>
                  ) : (
                    <div className="scorecard-disclaimer" role="status">
                      <strong>Live match pulse.</strong>{" "}
                      {livePulseText}
                      {scorecardData?.cached && (
                        <div style={{ marginTop: 6 }}>Showing a cached provider snapshot.</div>
                      )}
                    </div>
                  )}

                  {activeScoreRows.length > 0 ? (
                    <div style={{ marginTop: 16 }}>
                      <h3 style={{ fontSize: "0.95rem", marginBottom: 8 }}>Innings breakdown</h3>
                      <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
                        {activeScoreRows.map((sc, i) => (
                          <div key={`${sc.inning}-${i}`} className="telemetry-stat" style={{ textAlign: "left", padding: "12px 16px" }}>
                            <div style={{ fontSize: "0.8rem", color: "var(--on-surface-variant)" }}>{sc.inning || `Innings ${i + 1}`}</div>
                            <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--primary-container)", fontFamily: "var(--font-data)" }}>
                              {sc.r}/{sc.w}
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "var(--outline)" }}>{sc.o} overs</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="state-empty">The provider has not published an innings score for this match yet.</div>
                  )}

                  {scorecardDetailFields.length > 0 && (
                    <section style={{ marginTop: 18 }} aria-label="Additional scorecard details">
                      <h3 style={{ fontSize: "0.95rem", marginBottom: 8 }}>More scorecard details</h3>
                      <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
                        {scorecardDetailFields.map(([key, value]) => (
                          <div key={key} className="telemetry-stat" style={{ textAlign: "left", padding: "10px 14px" }}>
                            <div style={{ fontSize: "0.76rem", color: "var(--on-surface-variant)" }}>
                              {key.replace(/_/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2")}
                            </div>
                            <div style={{ marginTop: 4, overflowWrap: "anywhere" }}>{String(value)}</div>
                          </div>
                        ))}
                      </div>
                    </section>
                  )}

                  <div className="scorecard-disclaimer" style={{ marginTop: 20 }}>
                    <strong>About live catch-up.</strong>{" "}
                    This feed provides live match and aggregate scorecard data, not the verified ball-by-ball delivery ledger needed to reconstruct missed overs. FanCue won’t invent deliveries or claim a live story it cannot verify. Use the historical archive for full ball-by-ball catch-up stories.
                  </div>

                  <div className="cta-bar" style={{ marginTop: 24, justifyContent: "flex-start", gap: 10, flexWrap: "wrap" }}>
                    <button
                      className="catchup-btn"
                      style={{ maxWidth: 320 }}
                      onClick={() => {
                        closeNearLiveScorecard();
                        setSourceTab("historical");
                        setSearch("");
                        setFormatFilter("all");
                        window.scrollTo({ top: 0, behavior: "smooth" });
                      }}
                    >
                      Explore historical replay →
                    </button>
                    <button
                      className="icon-btn"
                      disabled={scorecardLoading}
                      onClick={() => selectedNearLive && loadNearLiveScorecard(selectedNearLive, true)}
                    >
                      ⟳ Refresh scorecard
                    </button>
                  </div>
                </>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// SCREEN 2 — Interval Selector
// ---------------------------------------------------------------------------

function IntervalSelector({
  match,
  onIntervalSelected,
  onBack,
  isSubmitting = false,
}: {
  match: MatchDescriptor;
  onIntervalSelected: (interval: InningsIntervalOption) => void;
  onBack: () => void;
  isSubmitting?: boolean;
}) {
  const [intervals, setIntervals] = useState<InningsIntervalOption[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeInnings, setActiveInnings] = useState(0);
  const [selected, setSelected] = useState<InningsIntervalOption | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchIntervals(match.match_id)
      .then((data) => {
        setIntervals(data.intervals);
        if (data.intervals.length > 0) {
          setActiveInnings(data.intervals[0].innings);
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load intervals"))
      .finally(() => setLoading(false));
  }, [match.match_id]);

  const inningsSet = intervals
    ? [...new Set(intervals.map((iv) => iv.innings))].sort()
    : [];

  const inningsIntervals = (intervals ?? []).filter(
    (iv) => iv.innings === activeInnings,
  );

  const totalOvers = totalOversForFormat(match.format);
  const phaseChips = intervals
    ? buildPhaseChips(inningsIntervals, match.format)
    : [];
  const windowChips = intervals
    ? buildWindowChips(inningsIntervals, totalOvers)
    : [];

  function selectInterval(iv: InningsIntervalOption) {
    setSelected(iv);
  }

  function isChipSelected(iv: InningsIntervalOption): boolean {
    return (
      selected !== null &&
      selected.innings === iv.innings &&
      selected.start_after_over === iv.start_after_over &&
      selected.end_after_over === iv.end_after_over
    );
  }

  const inningsSuffix = (idx: number) =>
    idx === 0 ? "1st Innings" : idx === 1 ? "2nd Innings" : `Innings ${idx + 1}`;

  return (
    <div className="page interval-page">
      {/* Back */}
      <button className="back-nav" onClick={onBack} aria-label="Back to match selection">
        <span className="back-nav__arrow">←</span>
        Back to Match Selection
      </button>

      {/* Active match brief */}
      <section className="match-brief" aria-label="Selected match">
        <div className="match-brief__glow match-brief__glow--cyan" />
        <div className="match-brief__glow match-brief__glow--magenta" />
        <div className="match-brief__inner">
          <div>
            <div className="match-brief__meta">
              <span className="chip chip--outline">Historical Replay · Cricsheet</span>
              <span className={formatBadgeClass(match.format)}>{match.format}</span>
            </div>
            <div className="match-brief__name">{match.name}</div>
            <div className="match-brief__sub">
              {match.date}
              {match.venue ? ` · ${match.venue}` : ""}
              {" · "}
              {match.supported_innings.length} innings recorded
            </div>
          </div>
          <div className="match-brief__scoreboard">
            <div className="match-brief__scoreboard-label">Match</div>
            <div className="match-brief__teams">{match.teams.join(" vs ")}</div>
          </div>
        </div>
      </section>

      {/* Headline */}
      <header className="selector-headline">
        <div className="selector-headline__eyebrow">
          ⊞ Instant Catch-Up Synthesizer
        </div>
        <h1 className="selector-headline__h1">How much of the match did you miss?</h1>
        <p className="selector-headline__sub">
          Select a natural match phase or recent over window. FanCue builds your
          story strictly from verified Cricsheet ground-truth ball events — no
          fabricated statistics.
        </p>
      </header>

      {loading && <Spinner />}
      {error && <ErrorMsg message={error} />}

      {intervals && (
        <>
          {/* Innings tabs */}
          {inningsSet.length > 1 && (
            <div className="innings-tabs" role="tablist" aria-label="Innings">
              {inningsSet.map((idx) => (
                <button
                  key={idx}
                  role="tab"
                  id={`innings-tab-${idx}`}
                  aria-selected={activeInnings === idx}
                  className={`innings-tab${activeInnings === idx ? " innings-tab--active" : ""}`}
                  onClick={() => {
                    setActiveInnings(idx);
                    setSelected(null);
                  }}
                >
                  {inningsSuffix(idx)}
                </button>
              ))}
            </div>
          )}

          {inningsIntervals.length === 0 ? (
            <div className="state-empty">No intervals available for this innings.</div>
          ) : (
            <>
              {/* Phase chips */}
              <div className="group-label">
                <span className="group-label__icon">🏏</span>
                1. Tactical Match Phases
              </div>
              <div className="phase-grid" role="listbox" aria-label="Match phase intervals">
                {phaseChips.map((chip, i) => {
                  const isSelected = isChipSelected(chip.interval);
                  return (
                    <button
                      key={i}
                      className={`interval-chip interval-option${isSelected ? " interval-chip--selected" : ""}`}
                      role="option"
                      aria-selected={isSelected}
                      id={`phase-chip-${i}`}
                      onClick={() => selectInterval(chip.interval)}
                    >
                      {chip.tag && (
                        <span className="interval-chip__crucial">{chip.tag}</span>
                      )}
                      {isSelected && (
                        <span className="interval-chip__selected-check" aria-hidden>✓</span>
                      )}
                      <div>
                        <div className="interval-chip__phase">Phase {["I","II","III","IV"][i] ?? i + 1}</div>
                        <div className="interval-chip__name">{chip.label}</div>
                        <div className="interval-chip__range">{chip.range}</div>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Window chips */}
              <div className="group-label">
                <span className="group-label__icon">⏱</span>
                2. Catch-Up Window (Last N Overs)
              </div>
              <div className="window-grid" role="listbox" aria-label="Recent over windows">
                {windowChips.map((chip, i) => {
                  const isSelected = isChipSelected(chip.interval);
                  return (
                    <button
                      key={i}
                      className={`window-chip interval-option${isSelected ? " window-chip--selected" : ""}`}
                      role="option"
                      aria-selected={isSelected}
                      id={`window-chip-${i}`}
                      onClick={() => selectInterval(chip.interval)}
                    >
                      {chip.label}
                    </button>
                  );
                })}
              </div>

              {/* All individual intervals fallback */}
              {phaseChips.length === 0 && (
                <>
                  <div className="group-label">All Intervals</div>
                  <div className="window-grid" role="listbox" aria-label="All intervals">
                    {inningsIntervals.map((iv) => {
                      const key = `${iv.innings}-${iv.start_after_over}-${iv.end_after_over}`;
                      const isSelected = isChipSelected(iv);
                      return (
                        <button
                          key={key}
                          className={`window-chip interval-option${isSelected ? " window-chip--selected" : ""}`}
                          role="option"
                          aria-selected={isSelected}
                          id={`iv-${key}`}
                          onClick={() => selectInterval(iv)}
                        >
                          {iv.label}
                        </button>
                      );
                    })}
                  </div>
                </>
              )}

              {/* CTA */}
              <div className="cta-bar">
                <button
                  id="catchup-btn"
                  className="catchup-btn"
                  onClick={() => selected && !isSubmitting && onIntervalSelected(selected)}
                  disabled={!selected || isSubmitting}
                  aria-busy={Boolean(isSubmitting)}
                >
                  {isSubmitting
                    ? "Building your catch-up…"
                    : selected
                    ? `Catch me up — ${selected.label || `Over ${selected.start_after_over}→${selected.end_after_over}`}`
                    : "Select an interval above"}
                </button>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SCREEN 3 — Catch-up Story
// ---------------------------------------------------------------------------

function StoryView({
  match,
  interval,
  response,
  onChangeInterval,
  onChangeMatch,
}: {
  match: MatchDescriptor;
  interval: InningsIntervalOption;
  response: CricketCatchUpResponse;
  onChangeInterval: () => void;
  onChangeMatch: () => void;
}) {
  const { state_before, state_after, state_delta, explanation, warnings } = response;
  const isFallback = explanation.generation_mode === "deterministic_fallback";
  const toast = useToast();
  const reducedMotion = usePrefersReducedMotion();

  // Authoritative count-up score animations (600-800ms)
  const runsAddedDisplay = useCountUp(state_delta.runs_added, 700, !reducedMotion);
  const endRunsDisplay = useCountUp(state_after.runs, 700, !reducedMotion);

  // Moment selection state & evidence drawer expansion
  const [selectedFactId, setSelectedFactId] = useState<string | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  function handleSelectMoment(factId: string) {
    if (selectedFactId === factId) {
      setSelectedFactId(null);
    } else {
      setSelectedFactId(factId);
      setEvidenceOpen(true);
      setTimeout(() => {
        const el = document.getElementById(`evidence-${factId}`);
        if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }, 100);
    }
  }

  // Filter turning moments (wickets, boundaries, high scoring overs)
  const momentFacts = response.evidence_packet.key_facts
    .filter(
      (f) =>
        f.fact_type === "wicket" ||
        f.fact_type === "boundary" ||
        f.fact_type === "over_summary",
    )
    .slice(0, 8);

  // Filter over summary facts for runs-per-over barometer
  const overSummaryFacts = response.evidence_packet.key_facts.filter(
    (f) => f.fact_type === "over_summary" && typeof f.structured_payload?.over === "number",
  );

  const inningsLabel =
    interval.innings === 0
      ? "1st Innings"
      : interval.innings === 1
      ? "2nd Innings"
      : `Innings ${interval.innings + 1}`;

  const intervalLabel =
    interval.label ||
    `Overs ${interval.start_after_over}.0 → ${interval.end_after_over}.0`;

  function handleShare() {
    const text = [
      `FanCue Catch-Up — ${match.name}`,
      `${inningsLabel} · ${intervalLabel}`,
      `Score: ${formatScore(state_before.runs, state_before.wickets)} ${formatOvers(state_before.overs_completed)} → ${formatScore(state_after.runs, state_after.wickets)} ${formatOvers(state_after.overs_completed)}`,
      `Delta: +${state_delta.runs_added} runs · ${state_delta.wickets_lost} wickets · ${state_delta.interval_run_rate.toFixed(2)} RPO`,
      ``,
      explanation.summary,
      ``,
      `Source: ${response.evidence_packet.provenance.source_name} (${response.evidence_packet.provenance.license_name})`,
      `Not a live feed.`,
    ].join("\n");

    if (navigator?.clipboard?.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(() => toast.show("Recap copied to clipboard!"))
        .catch(() => toast.show("Copy failed — paste manually"));
    } else {
      toast.show("Copy failed — clipboard unavailable");
    }
  }

  // Verified summary headline
  const summaryHeadline = (() => {
    const d = state_delta;
    const rr = d.interval_run_rate.toFixed(2);
    if (d.wickets_lost > 0) {
      return (
        <>
          <span className="highlight--cyan">+{d.runs_added} runs</span> scored
          {" and "}
          <span className="highlight--magenta">{d.wickets_lost} wicket{d.wickets_lost !== 1 ? "s" : ""} fell</span>
          {" — interval run rate: "}
          {rr} RPO
        </>
      );
    }
    return (
      <>
        <span className="highlight--cyan">+{d.runs_added} runs</span> scored across{" "}
        {d.completed_overs_delta} overs at {rr} RPO — no wickets lost
      </>
    );
  })();

  return (
    <div className="page story-page">
      {/* Toast */}
      <div
        className={`toast${toast.visible ? " toast--visible" : ""}`}
        role="status"
        aria-live="polite"
      >
        <span className="toast__icon">✓</span>
        {toast.msg}
      </div>

      {/* Context header */}
      <section className="context-header" aria-label="Match context">
        <div className="context-header__info">
          <div className="context-header__crumbs">
            <span className="chip chip--outline">Historical Replay · Cricsheet</span>
            <span style={{ color: "var(--outline-variant)" }}>·</span>
            <span style={{ fontSize: "0.82rem", color: "var(--on-surface-variant)", fontWeight: 500 }}>
              {inningsLabel}
            </span>
          </div>
          <div className="context-header__match-name">{match.name}</div>
          <div className="context-header__interval">
            <span>⏱</span>
            <span>Selected Phase: {intervalLabel}</span>
          </div>
        </div>

        <div className="context-header__actions">
          <span
            className={`mode-badge generation-badge ${isFallback ? "mode-badge--fallback" : "mode-badge--verified"}`}
          >
            {isFallback ? (
              <>BALL-BY-BALL RECAP</>
            ) : (
              <>AI EXPLANATION · VERIFIED</>
            )}
          </span>

          <button className="icon-btn" onClick={handleShare} aria-label="Share recap">
            ↗ Share Recap
          </button>

          <button className="icon-btn" onClick={onChangeInterval} aria-label="Change interval">
            ⊞ Change Interval
          </button>

          <button className="icon-btn" onClick={onChangeMatch} aria-label="Change match">
            ← Matches
          </button>
        </div>
      </section>

      {/* Verified headline */}
      <section className="headline-section" aria-label="Match interval summary">
        <div className="headline-section__bg-glow headline-section__bg-glow--top" />
        <div className="headline-section__bg-glow headline-section__bg-glow--bot" />

        <div className="headline-section__label">
          <span>📊</span>
          What changed in this stretch · Score verified
        </div>

        <h1 className="headline-section__h1">{summaryHeadline}</h1>

        <div className="headline-section__facts">
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span className="fact-dot fact-dot--cyan" />
            <span>
              Delta:{" "}
              <strong style={{ color: "var(--on-surface)" }}>
                +{state_delta.runs_added} runs
              </strong>{" "}
              across {state_delta.legal_balls_added} legal deliveries
            </span>
          </div>
          <span>•</span>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span className="fact-dot fact-dot--magenta" />
            <span>
              Dismissals:{" "}
              <strong style={{ color: "var(--on-surface)" }}>
                {state_delta.wickets_lost} wicket{state_delta.wickets_lost !== 1 ? "s" : ""}
              </strong>
            </span>
          </div>
          <span>•</span>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span>
              Interval Rate:{" "}
              <strong style={{ color: "var(--primary-fixed)", fontFamily: "var(--font-data)" }}>
                {state_delta.interval_run_rate.toFixed(2)} RPO
              </strong>
            </span>
          </div>
        </div>
      </section>

      {/* Score Arc */}
      <section className="score-arc" aria-label="Score arc">
        {/* When you left */}
        <div className="score-node">
          <div>
            <div className="score-node__header">
              <span className="score-node__label">Interval Start</span>
              <span className="score-node__tag">WHEN YOU LEFT</span>
            </div>
            <div className="score-node__title" style={{ marginTop: 8 }}>
              End of Over {state_before.overs_completed.toFixed(1)}
            </div>
          </div>
          <div className="score-node__runs state-box__score">
            <span className="score-node__runs-main">{state_before.runs}</span>
            <span className="score-node__runs-wkts">/ {state_before.wickets}</span>
            <span className="score-node__overs">
              ({state_before.overs_completed.toFixed(1)} ov)
            </span>
          </div>
          <div className="score-node__meta">
            <div>
              <div className="score-node__stat-label">Run Rate</div>
              <div className="score-node__stat-value">
                {state_before.run_rate.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="score-node__stat-label">Extras</div>
              <div className="score-node__stat-value">{state_before.extras_total}</div>
            </div>
          </div>
        </div>

        {/* Delta node */}
        <div className="delta-node delta-row" aria-label="Score change during interval">
          <div className="delta-node__label">INTERVAL</div>
          <div className="delta-stat-item">
            <span className="delta-stat-item__value delta-stat__value delta-stat-item__value--runs">
              +{runsAddedDisplay}
            </span>
            <span className="delta-stat-item__label">Runs</span>
          </div>
          <div className="delta-divider" />
          <div className="delta-stat-item">
            <span className="delta-stat-item__value delta-stat-item__value--wickets">
              {state_delta.wickets_lost}W
            </span>
            <span className="delta-stat-item__label">Wickets</span>
          </div>
          <div className="delta-divider" />
          <div className="delta-stat-item">
            <span className="delta-stat-item__value delta-stat-item__value--rr">
              {state_delta.interval_run_rate.toFixed(2)}
            </span>
            <span className="delta-stat-item__label">RPO</span>
          </div>
        </div>

        {/* Now */}
        <div className="score-node">
          <div>
            <div className="score-node__header">
              <span className="score-node__label">Interval End</span>
              <span className="score-node__tag">NOW</span>
            </div>
            <div className="score-node__title" style={{ marginTop: 8 }}>
              End of Over {state_after.overs_completed.toFixed(1)}
            </div>
          </div>
          <div className="score-node__runs state-box__score">
            <span className="score-node__runs-main">{endRunsDisplay}</span>
            <span className="score-node__runs-wkts">/ {state_after.wickets}</span>
            <span className="score-node__overs">
              ({state_after.overs_completed.toFixed(1)} ov)
            </span>
          </div>
          <div className="score-node__meta">
            <div>
              <div className="score-node__stat-label">Run Rate</div>
              <div className="score-node__stat-value">
                {state_after.run_rate.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="score-node__stat-label">Extras</div>
              <div className="score-node__stat-value">{state_after.extras_total}</div>
            </div>
          </div>
        </div>
      </section>

      {/* Story summary */}
      <section className="story-summary" aria-label="Match story">
        <div className="story-summary__label">
          <span>📝</span>
          {isFallback ? "BALL-BY-BALL RECAP" : "AI EXPLANATION · VERIFIED"}
        </div>
        <p className="story-summary__text">{explanation.summary}</p>
        {isFallback && (
          <p className="story-summary__fallback-notice">
            FanCue's AI storyteller is temporarily unavailable. Your recap is still grounded in the verified ball-by-ball record.
          </p>
        )}
      </section>

      {/* Runs-per-over phase barometer (Section D) */}
      <OverBarometer
        overFacts={overSummaryFacts}
        keyFacts={response.evidence_packet.key_facts}
      />

      {/* Crucial Turning Moments (Section E) */}
      <MomentCards
        facts={momentFacts}
        selectedFactId={selectedFactId}
        onSelectMoment={handleSelectMoment}
      />

      {/* Evidence drawer (Section G) */}
      <EvidencePanel
        response={response}
        open={evidenceOpen}
        onToggle={() => setEvidenceOpen((o) => !o)}
        selectedFactId={selectedFactId}
      />

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="warnings" role="note" aria-label="Warnings">
          {warnings.map((w, i) => (
            <div key={i}>ℹ {friendlyStoryWarning(w)}</div>
          ))}
        </div>
      )}

      {/* Provenance footer */}
      <div className="provenance-footer">
        Historical replay — data from{" "}
        <a
          href={response.evidence_packet.provenance.source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {response.evidence_packet.provenance.source_name}
        </a>{" "}
        under {response.evidence_packet.provenance.license_name}. Not a live feed.
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SECTION D — Runs-per-over Phase Barometer
// ---------------------------------------------------------------------------

function OverBarometer({
  overFacts,
  keyFacts,
}: {
  overFacts: EvidenceFact[];
  keyFacts: EvidenceFact[];
}) {
  if (overFacts.length === 0) return null;

  // Identify overs that had wickets
  const wicketOvers = new Set<number>();
  for (const f of keyFacts) {
    if (f.fact_type === "wicket" && typeof f.structured_payload?.over === "number") {
      wicketOvers.add(f.structured_payload.over);
    }
  }

  return (
    <section className="over-barometer" aria-label="Runs per over phase barometer">
      <div className="over-barometer__header">
        <div className="over-barometer__title">
          <span>📊</span>
          <span>Phase Over Barometer</span>
        </div>
        <div className="over-barometer__legend">
          <div>
            <span
              className="over-barometer__legend-dot"
              style={{ background: "var(--primary-container)" }}
            />
            <span>Over Runs</span>
          </div>
          <div>
            <span
              className="over-barometer__legend-dot"
              style={{ background: "var(--error)" }}
            />
            <span>Wicket Fallen</span>
          </div>
        </div>
      </div>
      <div className="over-barometer__grid" role="region" aria-label="Over progression">
        {overFacts.map((f, i) => {
          const overNum = f.structured_payload?.over as number;
          const runs = (f.structured_payload?.runs as number) ?? 0;
          const hasWicket = wicketOvers.has(overNum);
          const barPct = Math.max(8, Math.min(100, Math.round((runs / 24) * 100)));

          return (
            <div
              key={f.fact_id}
              className={`over-card${hasWicket ? " over-card--wicket" : ""}`}
              style={{ animationDelay: `${i * 40}ms` }}
            >
              <div className="over-card__header">
                <span className="over-card__num">OVER {overNum}</span>
                {hasWicket && <span className="over-card__wkt-badge">WKT</span>}
              </div>
              <div className="over-card__runs-row">
                <span className="over-card__runs">{runs}</span>
                <span className="over-card__runs-label">runs</span>
              </div>
              <div className="over-card__bar-track" aria-hidden>
                <div
                  className={`over-card__bar-fill${hasWicket ? " over-card__bar-fill--wicket" : ""}`}
                  style={{ width: `${barPct}%`, animationDelay: `${i * 40}ms` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// SECTION E — Turning Moment Cards (Story Reveal)
// ---------------------------------------------------------------------------

function MomentCards({
  facts,
  selectedFactId,
  onSelectMoment,
}: {
  facts: EvidenceFact[];
  selectedFactId: string | null;
  onSelectMoment: (factId: string) => void;
}) {
  if (facts.length === 0) return null;

  return (
    <section className="moment-section" aria-label="Crucial match-turning moments">
      <div className="moment-section__header">
        <div className="moment-section__title">
          <span>⚡</span>
          <span>Crucial Match-Turning Moments</span>
        </div>
        <div className="moment-section__sub">
          {facts.length} verified events from match record
        </div>
      </div>
      <div className="moment-grid" role="listbox" aria-label="Turning moment cards">
        {facts.map((f, i) => {
          const isSelected = selectedFactId === f.fact_id;
          const badgeClass =
            f.fact_type === "wicket"
              ? "moment-card__badge moment-card__badge--wicket"
              : f.fact_type === "boundary"
              ? "moment-card__badge moment-card__badge--boundary"
              : "moment-card__badge moment-card__badge--over";
          const overNum =
            typeof f.structured_payload?.over === "number"
              ? f.structured_payload.over
              : null;

          return (
            <div
              key={f.fact_id}
              className={`moment-card${isSelected ? " moment-card--selected" : ""}`}
              style={{ animationDelay: `${i * 60}ms` }}
              role="option"
              aria-selected={isSelected}
            >
              <div>
                <div className="moment-card__badge-row">
                  <span className={badgeClass}>{f.fact_type.replace(/_/g, " ")}</span>
                  {overNum !== null && (
                    <span className="moment-card__over-tag">Over {overNum}</span>
                  )}
                </div>
                <div className="moment-card__desc" style={{ marginTop: 10 }}>
                  {humanizeFactDescription(f.description)}
                </div>
              </div>
              <button
                type="button"
                id={`moment-btn-${f.fact_id}`}
                className="moment-card__action"
                onClick={() => onSelectMoment(f.fact_id)}
                aria-label={`Inspect evidence for ${f.fact_type}`}
              >
                <span>{isSelected ? "✓ Evidence Inspected" : "Inspect Ball Evidence"}</span>
                <span>→</span>
              </button>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// SECTION G — Evidence Drawer
// ---------------------------------------------------------------------------

function EvidencePanel({
  response,
  open,
  onToggle,
  selectedFactId,
}: {
  response: CricketCatchUpResponse;
  open: boolean;
  onToggle: () => void;
  selectedFactId: string | null;
}) {
  const packet = response.evidence_packet;
  const passages = packet.retrieved_passages ?? [];

  return (
    <>
      <button
        id="evidence-toggle"
        className="evidence-toggle"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls="evidence-content"
      >
        <span className="evidence-toggle__left">
          <span className="evidence-toggle__icon">📋</span>
          Inspect the Evidence ({packet.key_facts.length} verified facts
          {passages.length > 0 ? `, ${passages.length} passages` : ""})
        </span>
        <span
          className={`evidence-toggle__chevron${open ? " evidence-toggle__chevron--open" : ""}`}
          aria-hidden
        >
          ▾
        </span>
      </button>

      {open && (
        <div
          id="evidence-content"
          className="evidence-panel"
          aria-label="Evidence details"
        >
          {packet.key_facts.map((fact) => {
            const isSelected = selectedFactId === fact.fact_id;
            const isDimmed = Boolean(selectedFactId && selectedFactId !== fact.fact_id);
            return (
              <div
                key={fact.fact_id}
                id={`evidence-${fact.fact_id}`}
                className={`evidence-fact${isSelected ? " evidence-fact--highlighted" : ""}${isDimmed ? " evidence-fact--dimmed" : ""}`}
              >
                {isSelected && (
                  <div className="evidence-fact__highlight-tag">
                    ★ Selected Ball Evidence
                  </div>
                )}
                <div className="evidence-fact__type">
                  {fact.fact_type.replace(/_/g, " ")}
                </div>
                <div>{humanizeFactDescription(fact.description)}</div>
              </div>
            );
          })}

          {passages.map((p) => (
            <div key={p.doc_id} className="evidence-passage">
              <div className="evidence-passage__source">
                {p.source_name} · {p.topic.replace(/_/g, " ")}
              </div>
              <div className="evidence-passage__text">
                {p.content.slice(0, 240)}…
              </div>
              <a
                href={p.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="evidence-passage__link"
              >
                ↗ Source
              </a>
            </div>
          ))}

          <div className="evidence-fact">
            <div className="evidence-fact__type">Provenance</div>
            <div>
              {packet.provenance.source_name} — {packet.provenance.license_name}
              {" · "}
              <a
                href={packet.provenance.source_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "var(--primary-container)", textDecoration: "none" }}
              >
                Dataset
              </a>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Screen type
// ---------------------------------------------------------------------------

type Screen = "discovery" | "interval" | "story";

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------

export default function App() {
  const [screen, setScreen] = useState<Screen>("discovery");
  const [selectedMatch, setSelectedMatch] = useState<MatchDescriptor | null>(null);
  const [selectedInterval, setSelectedInterval] = useState<InningsIntervalOption | null>(null);
  const [catchUpResult, setCatchUpResult] = useState<CricketCatchUpResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleMatchSelected(match: MatchDescriptor) {
    setSelectedMatch(match);
    setSelectedInterval(null);
    setCatchUpResult(null);
    setError(null);
    setScreen("interval");
  }

  async function handleIntervalSelected(interval: InningsIntervalOption) {
    if (!selectedMatch) return;
    setSelectedInterval(interval);
    setError(null);
    setCatchUpResult(null);
    setLoading(true);

    try {
      const response = await fetchCatchUp({
        match_id: selectedMatch.match_id,
        interval: {
          innings: interval.innings,
          start_after_over: interval.start_after_over,
          end_after_over: interval.end_after_over,
        },
      });
      setCatchUpResult(response);
      setScreen("story");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch catch-up");
    } finally {
      setLoading(false);
    }
  }

  function handleBackToMatches() {
    setScreen("discovery");
    setCatchUpResult(null);
    setSelectedInterval(null);
  }

  function handleBackToInterval() {
    setScreen("interval");
    setCatchUpResult(null);
    setError(null);
  }

  const sessionLabel =
    selectedMatch && screen !== "discovery"
      ? `${selectedMatch.teams.join(" v ")} · ${selectedMatch.format}`
      : undefined;

  return (
    <div className="app">
      <TopNav
        onLogoClick={handleBackToMatches}
        showBack={screen !== "discovery"}
        onBack={screen === "story" ? handleBackToInterval : handleBackToMatches}
        sessionLabel={sessionLabel}
      />

      {screen === "discovery" && (
        <MatchDiscovery onMatchSelected={handleMatchSelected} />
      )}

      {screen === "interval" && selectedMatch && (
        <>
          {loading ? (
            <div className="page generation-loading" role="status" aria-live="polite">
              <div className="spinner" />
              <div className="generation-loading__status">Building your catch-up…</div>
              <div className="generation-loading__sub">
                Ground-truth Cricsheet calculation & verification in progress
              </div>
            </div>
          ) : error ? (
            <div className="page">
              <ErrorMsg message={error} />
              <div className="cta-bar" style={{ marginTop: 16 }}>
                <button className="catchup-btn" onClick={handleBackToInterval}>
                  Try Again
                </button>
              </div>
            </div>
          ) : (
            <IntervalSelector
              match={selectedMatch}
              onIntervalSelected={handleIntervalSelected}
              onBack={handleBackToMatches}
              isSubmitting={loading}
            />
          )}
        </>
      )}

      {screen === "story" && catchUpResult && selectedMatch && selectedInterval && (
        <StoryView
          match={selectedMatch}
          interval={selectedInterval}
          response={catchUpResult}
          onChangeInterval={handleBackToInterval}
          onChangeMatch={handleBackToMatches}
        />
      )}
    </div>
  );
}
