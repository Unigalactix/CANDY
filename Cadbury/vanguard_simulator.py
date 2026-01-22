from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import time
import os
import json
import csv
from datetime import datetime, timezone
import re

# ============================================================
# CONFIG
# ============================================================

APP_URL = os.getenv(
    "APP_URL",
    "https://vanguard-app-f8fjbwhdf3e7g9ft.canadacentral-01.azurewebsites.net/",
)
HEADLESS = os.getenv("HEADLESS", "true").lower() in ("1", "true", "yes")

MIN_RUNTIME_S = int(os.getenv("MIN_RUNTIME_S", "300"))  # max wait per file
MAX_PROCESS_TIMEOUT_MS = MIN_RUNTIME_S * 1000
INTER_FILE_WAIT_MS = int(os.getenv("INTER_FILE_WAIT_MS", "2000"))

# Optional: enable Playwright tracing (handy for debugging flaky CI)
ENABLE_TRACE = os.getenv("ENABLE_TRACE", "false").lower() in ("1", "true", "yes")
TRACE_DIR = os.getenv("TRACE_DIR", "playwright_traces")

# Optional: save screenshots on failures/timeouts
SAVE_SCREENSHOTS = os.getenv("SAVE_SCREENSHOTS", "true").lower() in ("1", "true", "yes")
ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", "artifacts")

# ============================================================
# HELPERS
# ============================================================

def safe_filename(name: str, max_len: int = 160) -> str:
    """Make a filename-safe string."""
    name = name.strip().replace(os.sep, "_")
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    return name[:max_len] if len(name) > max_len else name


def ensure_dir(path: str) -> None:
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


# ============================================================
# DROPDOWN SCROLLER (FINAL)
# ============================================================

def collect_dropdown_pdfs(page):
    """
    Robustly collect ALL Streamlit/BaseWeb selectbox options by scrolling
    the actual dropdown popover container until the option count stabilizes.
    """

    # 0) (Recommended) Refresh the document list if the button exists
    try:
        btn = page.get_by_role("button", name="Refresh Document List")
        if btn.is_visible(timeout=500):
            btn.click()
            page.wait_for_timeout(1500)
    except Exception:
        pass

    # 1) Open dropdown
    selectbox = page.locator('div[data-testid="stSelectbox"]').first
    selectbox.click()
    page.wait_for_timeout(800)

    # 2) Find the dropdown popover + scroll container (Streamlit uses BaseWeb)
    # Try a few possible containers; whichever exists will be used.
    popover = page.locator('div[data-baseweb="popover"], div[role="presentation"]').first

    # A scrollable menu/list container is usually one of these:
    scroll_container_candidates = [
        popover.locator('[role="listbox"]').first,
        popover.locator('div[data-baseweb="menu"]').first,
        popover.locator('ul[role="listbox"]').first,
        page.locator('[role="listbox"]').first,
    ]

    scroll_container = None
    for c in scroll_container_candidates:
        try:
            if c.count() > 0 and c.is_visible(timeout=500):
                scroll_container = c
                break
        except Exception:
            continue

    # If we still can't find a scroll container, we can still collect options,
    # but scrolling might be limited.
    option_locator = page.locator('[role="option"]')

    seen = set()
    pdfs = []

    last_seen_count = -1
    stable_rounds = 0
    max_rounds = 200  # plenty for long lists

    for _ in range(max_rounds):
        # 3) Collect currently rendered options
        try:
            count = option_locator.count()
        except Exception:
            count = 0

        for i in range(count):
            try:
                txt = option_locator.nth(i).inner_text().strip()
            except Exception:
                continue

            if not txt.lower().endswith(".pdf"):
                continue
            if "pdfs for ocr" in txt.lower():
                continue

            if txt not in seen:
                seen.add(txt)
                pdfs.append(txt)

        # 4) Stabilization check
        if len(pdfs) == last_seen_count:
            stable_rounds += 1
        else:
            stable_rounds = 0
            last_seen_count = len(pdfs)

        # If no new PDFs after several scroll attempts, assume done
        if stable_rounds >= 8:
            break

        # 5) Scroll the dropdown container (preferred)
        try:
            if scroll_container is not None:
                # Scroll down inside the dropdown
                scroll_container.evaluate("el => el.scrollBy(0, el.clientHeight)")
                page.wait_for_timeout(250)

                # Also send End key occasionally to force lazy-load
                if stable_rounds in (2, 4, 6):
                    page.keyboard.press("End")
                    page.wait_for_timeout(250)
            else:
                # Fallback: try wheel scroll (less reliable)
                page.mouse.wheel(0, 1600)
                page.wait_for_timeout(250)
        except Exception:
            page.wait_for_timeout(250)

    # 6) Close dropdown
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    return pdfs



# ============================================================
# WAIT FOR SUCCESS / ERROR (TAILORED TO YOUR UI)
# ============================================================

def wait_for_processing_result(page, timeout_ms: int):
    """
    Wait for the Streamlit success banner:
      "Document processed successfully! Saved to: <file>.json"

    Fail fast on common Streamlit exception/error surfaces.

    Returns:
        (status, message)
        status in {"succeeded","failed","timeout"}
    """
    success = page.locator('text=/Document processed successfully!/i')

    # Streamlit exceptions often render with data-testid="stException"
    errors = [
        page.locator('[data-testid="stException"]'),
        page.locator('text=/traceback/i'),
        page.locator('text=/exception/i'),
        page.locator('text=/\\berror\\b/i'),
        page.locator('text=/failed/i'),
    ]

    start = time.time()
    poll_ms = 1000

    # Optional: stage texts (useful for printing current stage if you want)
    stage_texts = [
        "Downloading document from blob storage",
        "Extracting content using Azure Document Intelligence",
        "Structuring and validating content using Azure OpenAI",
        "Saving processed data to blob storage",
    ]

    last_stage = None

    while (time.time() - start) * 1000 < timeout_ms:
        # ✅ SUCCESS
        try:
            if success.first.is_visible(timeout=200):
                msg = success.first.inner_text().strip()
                return ("succeeded", msg)
        except Exception:
            pass

        # ❌ FAILURE
        for e in errors:
            try:
                if e.first.is_visible(timeout=200):
                    txt = e.first.inner_text().strip()
                    return ("failed", txt or "Error detected in UI")
            except Exception:
                pass

        # (Optional) Print stage transitions for visibility in logs
        for s in stage_texts:
            try:
                loc = page.locator(f'text=/{re.escape(s)}/i')
                if loc.first.is_visible(timeout=50):
                    if last_stage != s:
                        last_stage = s
                        print(f"   ↳ Stage: {s}...")
                    break
            except Exception:
                pass

        page.wait_for_timeout(poll_ms)

    return ("timeout", f"No success/error signal within {timeout_ms/1000:.0f}s")


# ============================================================
# MAIN RUNNER
# ============================================================

def run_vanguard_simulator():
    ensure_dir(ARTIFACT_DIR)
    ensure_dir(TRACE_DIR)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                headless=HEADLESS, 
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
        except Exception as e:
            # If the browser executable is missing, install it and retry
            if "Executable doesn't exist" in str(e):
                print("⚠️ Playwright browser not found. Installing chromium...")
                import subprocess
                import sys
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                print("✅ Browser installed. Retrying launch...")
                browser = p.chromium.launch(
                    headless=HEADLESS,
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )
            else:
                raise e

        context = browser.new_context()
        if ENABLE_TRACE:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)

        page = context.new_page()

        # Helpful console logging (Streamlit sometimes logs useful details)
        page.on("console", lambda msg: print(f"[console:{msg.type}] {msg.text}"))

        print(f"🌍 Opening Vanguard App (HEADLESS={HEADLESS})")
        page.goto(APP_URL, timeout=120000)
        page.wait_for_timeout(6000)

        # --------------------------------------------------------
        # READ FILES FROM UI
        # --------------------------------------------------------
        print("📂 Reading file list from UI dropdown...")
        files = collect_dropdown_pdfs(page)

        if not files:
            print("❌ No eligible PDF files found in dropdown.")
            context.close()
            browser.close()
            return

        print(f"📄 PDFs to process ({len(files)}):")
        for f in files:
            print(" -", f)

        results = []

        # --------------------------------------------------------
        # PROCESS EACH FILE
        # --------------------------------------------------------
        for file_label in files:
            print(f"\n========== Processing {file_label} ==========")
            start = time.time()
            status = "failed"
            msg = ""

            try:
                # Open dropdown
                page.locator('div[data-testid="stSelectbox"]').first.click()
                page.wait_for_timeout(400)

                # Select by label (Streamlit options are text nodes; substring collisions are rare but possible)
                # If you ever see collisions, switch to exact regex match with anchors.
                page.locator('[role="option"]', has_text=file_label).first.click()
                page.wait_for_timeout(600)

                # Click Process Document
                page.get_by_role("button", name="Process Document").first.click()
                print("⏳ Processing started...")

                # Wait for success/failure/timeout based on UI
                status, msg = wait_for_processing_result(page, MAX_PROCESS_TIMEOUT_MS)

                # Optional sanity check: ensure "Download JSON" button exists after success
                if status == "succeeded":
                    try:
                        page.get_by_role("button", name="Download JSON").wait_for(timeout=5000)
                    except Exception:
                        status = "failed"
                        msg = "Success banner appeared but 'Download JSON' button not found."

                if status == "succeeded":
                    print(f"✅ Completed: {file_label}")
                    print(f"   {msg}")
                elif status == "timeout":
                    print(f"⏱️ TIMEOUT: {file_label}")
                    print(f"   {msg}")
                else:
                    print(f"❌ FAILED: {file_label}")
                    print(f"   {msg}")

            except Exception as e:
                status = "failed"
                msg = str(e)
                print(f"❌ Exception: {file_label} | {msg}")

            # Artifacts on non-success
            if SAVE_SCREENSHOTS and status != "succeeded":
                try:
                    fn = safe_filename(f"{file_label}_{status}.png")
                    path = os.path.join(ARTIFACT_DIR, fn)
                    page.screenshot(path=path, full_page=True)
                    print(f"🖼️ Saved screenshot: {path}")
                except Exception as _:
                    pass

            results.append({
                "file": file_label,
                "status": status,
                "duration_seconds": round(time.time() - start, 2),
                "message": msg,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            page.wait_for_timeout(INTER_FILE_WAIT_MS)

        # --------------------------------------------------------
        # SAVE RESULTS
        # --------------------------------------------------------
        with open("vanguard_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        with open("vanguard_results.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["file", "status", "duration_seconds", "message", "timestamp"])
            for r in results:
                writer.writerow([
                    r["file"],
                    r["status"],
                    r["duration_seconds"],
                    r["message"],
                    r["timestamp"]
                ])

        if ENABLE_TRACE:
            trace_path = os.path.join(TRACE_DIR, f"trace_{int(time.time())}.zip")
            context.tracing.stop(path=trace_path)
            print(f"🧵 Saved Playwright trace: {trace_path}")

        print("\n🎉 Vanguard run complete")
        context.close()
        browser.close()


if __name__ == "__main__":
    run_vanguard_simulator()
