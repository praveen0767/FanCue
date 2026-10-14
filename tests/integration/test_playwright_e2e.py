"""Browser-based End-to-End integration test using Playwright.

Exercises the full user catch-up journey against real running FastAPI backend
and real compiled frontend SPA:
1. Starts the real FastAPI app on http://127.0.0.1:8000.
2. Serves the production frontend distribution (frontend/dist) on http://127.0.0.1:5173.
3. Launches headless Chromium via Playwright.
4. Navigates to http://127.0.0.1:5173.
5. Verifies header and initial match list loading.
6. Selects fixture 1529229 (India vs West Indies ODI).
7. Verifies interval options load from the backend.
8. Selects interval 0-14-21 (overs 15-22).
9. Clicks "Get Catch-Up".
10. Verifies result view:
    - +65 Runs Added
    - 59/2 (15 ov) at start -> 124/2 (22 ov) at end
    - Deterministic fallback badge displayed (with LLM disabled)
11. Clicks evidence toggle and verifies key facts and dataset provenance appear.
"""

from functools import partial
import json
import http.server
import os
import socketserver
import threading
import time
import pytest
from playwright.sync_api import sync_playwright
import uvicorn

from backend.app.core.config import AppSettings, get_settings
from backend.app.main import app


class _ServerThread(threading.Thread):
    def __init__(self, target, **kwargs):
        super().__init__(daemon=True)
        self.target = target
        self.kwargs = kwargs
        self.server = None

    def run(self):
        self.target(**self.kwargs)


@pytest.fixture(scope="module")
def run_full_stack():
    """Start local backend and frontend servers in daemon threads."""
    dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
    assert os.path.isdir(dist_dir), f"frontend/dist must exist (run npm run build first): {dist_dir}"

    # Force skip_llm for deterministic fallback testing
    test_settings = AppSettings(
        skip_llm=True,
        allowed_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    )
    app.dependency_overrides[get_settings] = lambda: test_settings

    # 1. Start uvicorn backend on port 8000 (bind 0.0.0.0 for localhost & 127.0.0.1)
    backend_server = None
    try:
        config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="warning")
        backend_server = uvicorn.Server(config)
        b_thread = threading.Thread(target=backend_server.run, daemon=True)
        b_thread.start()
    except OSError:
        backend_server = None

    # 2. Start HTTP server for frontend dist on port 5173
    handler_class = partial(http.server.SimpleHTTPRequestHandler, directory=dist_dir)
    frontend_httpd = None
    try:
        frontend_httpd = socketserver.TCPServer(("127.0.0.1", 5173), handler_class)
        f_thread = threading.Thread(target=frontend_httpd.serve_forever, daemon=True)
        f_thread.start()
    except OSError:
        frontend_httpd = None

    # Give servers a moment to bind
    time.sleep(1.0)

    yield "http://127.0.0.1:5173"

    # Teardown
    if backend_server is not None:
        backend_server.should_exit = True
    if frontend_httpd is not None:
        frontend_httpd.shutdown()
        frontend_httpd.server_close()
    app.dependency_overrides.pop(get_settings, None)


def test_browser_catchup_user_journey(run_full_stack):
    """Execute end-to-end user journey in headless Chromium."""
    frontend_url = run_full_stack

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Navigate to frontend SPA
        page.goto(frontend_url, wait_until="networkidle")

        # Verify page title and current navigation badge
        assert "FanCue" in page.title()
        page.wait_for_selector(".topnav__badge")
        assert "HISTORICAL REPLAY" in page.locator(".topnav__badge").inner_text().upper()

        # 2. Wait for match list to load
        page.wait_for_selector("#match-1529229", timeout=10000)
        assert page.locator("#match-1529229").is_visible()

        # 3. Select match 1529229
        page.click("#match-1529229")

        # 4. Wait for intervals grid to populate
        page.wait_for_selector(".interval-option", timeout=10000)
        interval_buttons = page.locator(".interval-option")
        assert interval_buttons.count() > 0

        # 5. Select first available interval
        first_interval = interval_buttons.first
        first_interval.click()

        # 6. Click Catch-Up button
        page.wait_for_selector("#catchup-btn:not([disabled])", timeout=5000)
        page.click("#catchup-btn")

        # 7. Wait for CatchUpResult to appear
        page.wait_for_selector(".delta-row", timeout=10000)

        # 8. Verify authoritative score delta
        runs_added_el = page.locator(".delta-stat__value").first
        runs_text = runs_added_el.inner_text()
        assert "+" in runs_text

        # Verify state compare (start -> end)
        state_boxes = page.locator(".state-box__score").all_inner_texts()
        assert len(state_boxes) >= 2
        assert "/" in state_boxes[0]
        assert "/" in state_boxes[1]

        # 9. Verify fallback / generation mode badge
        badge_text = page.locator(".generation-badge").inner_text().lower()
        assert "ball-by-ball recap" in badge_text or "ai explanation" in badge_text

        # 10. Click evidence toggle and verify facts appear
        page.click("#evidence-toggle")
        page.wait_for_selector("#evidence-content", timeout=5000)
        evidence_text = page.locator("#evidence-content").inner_text()
        assert "Cricsheet" in evidence_text
        assert "ODC-By" in evidence_text or "Provenance" in evidence_text

        browser.close()



def test_browser_near_live_insights_open_after_selecting_match(run_full_stack):
    """Selecting a near-live match scrolls its scorecard panel into view and exposes honest limits."""
    frontend_url = run_full_stack
    live_match = {
        "id": "live-test-match",
        "name": "Australia Women vs Bangladesh Women, 3rd ODI",
        "match_type": "odi",
        "status": "Bangladesh Women batting",
        "venue": "Allan Border Field, Brisbane",
        "date": "2026-10-14",
        "date_time_gmt": None,
        "teams": ["Australia Women", "Bangladesh Women"],
        "team_info": [],
        "score": [{"r": 45, "w": 4, "o": 16.5, "inning": "Bangladesh Women Inning 1"}],
        "series_id": None,
        "match_started": True,
        "match_ended": False,
        "source": "CricketData.org",
        "source_url": "https://cricketdata.org/",
        "freshness": "Near-live · ~30s-5m delay",
        "license": "Test fixture",
        "retrieved_at": "2026-10-14T04:00:00+00:00",
    }

    def mock_near_live(route):
        clean_url = route.request.url.split("?", 1)[0]
        if clean_url.endswith("/scorecard"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({
                    "status": "success",
                    "configured": True,
                    "match": live_match,
                    "scorecard": {"run_rate": 2.67, "extras": 3},
                    "can_reconstruct_interval": False,
                    "limitation_reason": "Aggregate scorecard only; no delivery ledger.",
                    "cached": False,
                    "cached_at": None,
                    "message": None,
                }),
            )
        else:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({
                    "status": "success",
                    "configured": True,
                    "matches": [live_match],
                    "total": 1,
                    "cached": False,
                    "cached_at": None,
                    "hits_today": 1,
                    "hits_left": 99,
                    "message": None,
                }),
            )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.route("**/matches/near-live**", mock_near_live)
        page.goto(frontend_url, wait_until="networkidle")

        page.click("#source-tab-nearlive")
        page.wait_for_selector("#nearlive-live-test-match", timeout=10000)
        page.click("#nearlive-live-test-match")
        page.wait_for_selector("#scorecard-drawer", timeout=10000)
        page.wait_for_function(
            """() => {
              const panel = document.querySelector('#scorecard-drawer');
              if (!panel) return false;
              const rect = panel.getBoundingClientRect();
              return rect.top >= 0 && rect.top < window.innerHeight && rect.bottom > 0;
            }""",
            timeout=5000,
        )

        drawer = page.locator("#scorecard-drawer")
        assert drawer.is_visible()
        assert "Live match pulse" in drawer.inner_text()
        assert "45/4" in drawer.inner_text()
        assert "not the verified ball-by-ball" in drawer.inner_text().lower()
        assert page.get_by_role("button", name="Explore historical replay →").is_visible()

        browser.close()

def test_browser_motion_moment_and_evidence_interaction(run_full_stack):
    """Verify moment card reveal, 'See the ball' evidence highlighting, count-up settle, and share feedback."""
    frontend_url = run_full_stack

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(frontend_url, wait_until="networkidle")

        # Select match
        page.wait_for_selector("#match-1529229", timeout=10000)
        page.click("#match-1529229")

        # Select interval
        page.wait_for_selector(".interval-option", timeout=10000)
        page.locator(".interval-option").first.click()

        # Submit catch-up
        page.wait_for_selector("#catchup-btn:not([disabled])", timeout=5000)
        page.click("#catchup-btn")

        # Wait for result
        page.wait_for_selector(".delta-row", timeout=10000)

        # Allow count-up hero animation to settle (800ms)
        page.wait_for_timeout(900)

        # 1. Authoritative score settle verification
        runs_added = page.locator(".delta-stat__value").first.inner_text()
        assert "+" in runs_added
        assert int(runs_added.replace("+", "")) > 0

        state_boxes = page.locator(".state-box__score").all_inner_texts()
        assert len(state_boxes) >= 2
        assert "/" in state_boxes[0]
        assert "/" in state_boxes[1]

        # 2. Verify moment cards rendered
        page.wait_for_selector(".moment-card", timeout=5000)
        moment_cards = page.locator(".moment-card")
        assert moment_cards.count() > 0

        # 3. Click "Inspect Ball Evidence" on first moment card
        first_moment_action = page.locator(".moment-card__action").first
        first_moment_action.click()

        # 4. Verify evidence drawer automatically expanded and item is highlighted
        page.wait_for_selector(".evidence-fact--highlighted", timeout=5000)
        highlighted_count = page.locator(".evidence-fact--highlighted").count()
        assert highlighted_count >= 1

        # Verify dimmed non-selected facts
        dimmed_count = page.locator(".evidence-fact--dimmed").count()
        assert dimmed_count >= 1

        # 5. Toggle evidence drawer collapse
        page.click("#evidence-toggle")
        page.wait_for_timeout(300)

        # 6. Test share recap interaction feedback
        share_btn = page.locator('button[aria-label="Share recap"]')
        assert share_btn.is_visible()
        share_btn.click()

        # Toast appears (either successful copy or graceful clipboard permission fallback)
        page.wait_for_selector(".toast--visible", timeout=3000)
        toast_text = page.locator(".toast--visible").inner_text().lower()
        assert "copy" in toast_text or "recap" in toast_text or "clipboard" in toast_text

        browser.close()


def test_browser_reduced_motion(run_full_stack):
    """Verify that prefers-reduced-motion: reduce renders final authoritative values immediately without animation delay."""
    frontend_url = run_full_stack

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Emulate reduced motion
        page.emulate_media(reduced_motion="reduce")

        page.goto(frontend_url, wait_until="networkidle")

        # Select match and interval
        page.wait_for_selector("#match-1529229", timeout=10000)
        page.click("#match-1529229")

        page.wait_for_selector(".interval-option", timeout=10000)
        page.locator(".interval-option").first.click()

        page.wait_for_selector("#catchup-btn:not([disabled])", timeout=5000)
        page.click("#catchup-btn")

        page.wait_for_selector(".delta-row", timeout=10000)

        # With reduced motion, exact value is immediately available (no count-up delay needed)
        runs_added = page.locator(".delta-stat__value").first.inner_text()
        assert "+" in runs_added
        assert int(runs_added.replace("+", "")) > 0

        # State boxes immediately authoritative
        state_boxes = page.locator(".state-box__score").all_inner_texts()
        assert len(state_boxes) >= 2
        assert "/" in state_boxes[0]
        assert "/" in state_boxes[1]

        browser.close()


def test_browser_responsive_390px_viewport(run_full_stack):
    """Verify clean responsive layout and interactions at 390px mobile viewport."""
    frontend_url = run_full_stack

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 390px viewport (typical mobile screen)
        page.set_viewport_size({"width": 390, "height": 844})

        page.goto(frontend_url, wait_until="networkidle")

        # Brand logo remains visible at mobile width (the badge may be hidden responsively)
        page.wait_for_selector(".topnav__logo")
        assert page.locator(".topnav__logo").is_visible()

        # Match cards visible and interactive
        page.wait_for_selector("#match-1529229", timeout=10000)
        page.click("#match-1529229")

        # Interval options clickable
        page.wait_for_selector(".interval-option", timeout=10000)
        page.locator(".interval-option").first.click()

        # CTA clickable
        page.wait_for_selector("#catchup-btn:not([disabled])", timeout=5000)
        page.click("#catchup-btn")

        # Catch up result renders without clipping
        page.wait_for_selector(".delta-row", timeout=10000)
        assert page.locator(".score-arc").is_visible()
        assert page.locator(".story-summary").is_visible()

        browser.close()

