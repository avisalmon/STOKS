"""
add_expert_analysis.py — Claude-powered expert analysis for STOKS candidates.

Reads the latest scan run, calls the Anthropic API for each candidate,
and appends a deep expert analysis section to each report.md.

Usage:
    # Activate venv first, then:
    python add_expert_analysis.py                        # latest run
    python add_expert_analysis.py --run runs/2026-06-16_2159  # specific run
    python add_expert_analysis.py --model claude-opus-4-8     # use Opus
    python add_expert_analysis.py --ticker FOX --ticker HOG   # specific tickers only

Requirements:
    - ANTHROPIC_API_KEY in environment
    - pip install anthropic>=0.40.0
    - Corporate proxy: set HTTP_PROXY / HTTPS_PROXY or source proxy.bat first
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import anthropic
import httpx

# ---------------------------------------------------------------------------
# Proxy setup — apply corporate proxy if env vars not already set
# ---------------------------------------------------------------------------
def _ensure_proxy() -> None:
    proxy = "http://proxy-iil.intel.com:912"
    no_proxy = ".openai.azure.com,10.*,intel.com,.intel.com,localhost,.local,127.0.0.1"
    os.environ.setdefault("HTTP_PROXY", proxy)
    os.environ.setdefault("HTTPS_PROXY", proxy)
    os.environ.setdefault("NO_PROXY", no_proxy)


# ---------------------------------------------------------------------------
# Find the latest run directory
# ---------------------------------------------------------------------------
def _latest_run(base: str = "runs") -> Path:
    runs = sorted(Path(base).iterdir(), reverse=True)
    runs = [r for r in runs if r.is_dir() and (r / "reports").exists()]
    if not runs:
        raise FileNotFoundError(f"No scan runs found under '{base}/'")
    return runs[0]


# ---------------------------------------------------------------------------
# Build the analysis prompt for a single ticker
# ---------------------------------------------------------------------------
def _build_prompt(ticker: str, report_md: str) -> str:
    return f"""You are a senior equity analyst with 20+ years of experience in value investing (Graham/Buffett school).

You have been given a machine-generated screening report for **{ticker}**. Your job is to write a **world-class expert analysis section** to append to this report.

---
## REPORT DATA (machine-generated):
{report_md}
---

## YOUR TASK

Write an expert analysis section in **Markdown** that will be appended to this report. Use EXACTLY this structure (do not add anything before or after):

---

## 🧠 Claude Expert Analysis — Graham/Buffett Deep Dive

**Verdict:** [BUY / WATCH / AVOID]
**Conviction:** [X/10]
**Entry Zone:** $XX–$YY | **Strong Buy Below:** $XX

### The Business
[2–3 sentences: what this company actually does, its competitive moat or lack thereof, market position. Be specific — name products, market share numbers, customer types. Do NOT be generic.]

### Why the Market Is Pricing It This Way
[The specific narrative explaining the current valuation. What is Mr. Market pessimistic about? Is the pessimism justified or overdone? Reference the actual financial data in the report.]

### Financial Trajectory Analysis
[Read the income statement and cash flow data carefully. What's the trend in revenue, margins, EPS, and FCF? Is this a business improving or deteriorating? Is the "normalized EPS" the pipeline uses representative of true earning power? Call out any distortions.]

### Bull Case → $[target] (+[X]% upside)
[3–4 specific, concrete catalysts. Include timelines where possible. NOT generic statements like "if the business improves." Real catalysts: rate cuts, contract wins, product launches, regulatory changes, M&A, etc.]

### Bear Case → $[target] (-[X]% downside)
[3–4 specific risks with QUANTIFIED impact where possible. "If X happens, earnings could fall to $Y, implying Z× P/E at current price." Be precise, not vague.]

### Capital Allocation Quality
[How does management deploy capital? Buybacks (share count trend), dividends, M&A (discipline or empire-building?), debt management. Score: Excellent / Good / Fair / Poor, with evidence.]

### Entry Framework

| Signal | Price Range | Rationale |
|--------|------------|-----------|
| 🟢 Strong Buy | Below $XX | >45% MOS; high conviction |
| 🟡 Buy | $XX – $YY | 30–45% MOS; good risk/reward |
| 🟠 Watch | $YY – $ZZ | 15–30% MOS; monitor closely |
| 🔴 Avoid | Above $ZZ | <15% MOS; no margin of safety |

> ⚠️ Claude expert analysis — {ticker} — {time.strftime('%Y-%m-%d')}. Educational use only. Not financial advice. Always do your own due diligence.

---

## RULES:
- Be specific, not generic. Reference actual numbers from the report data.
- Be honest about weaknesses — do not oversell any stock.
- If the MOS is deeply negative, say so and explain why the pipeline might be wrong OR why the stock is genuinely overvalued.
- If this is a cyclical business, explain how to think about normalized earnings properly.
- If the pipeline's "normalized EPS" is distorted (too high due to one peak year, or too low due to restructuring), explain the distortion.
- Do NOT flag "no financial advice" within the body — that's in the footer.
- Write at a level that would impress a CFA charterholder.
- Total length: 600–900 words in the analysis body (not counting the entry framework table).
"""


# ---------------------------------------------------------------------------
# Generate analysis for one report
# ---------------------------------------------------------------------------
def _generate_analysis(client: anthropic.Anthropic, ticker: str, report_md: str, model: str) -> str:
    prompt = _build_prompt(ticker, report_md)
    print(f"  > Calling Claude ({model}) for {ticker}...", end=" ", flush=True)
    t0 = time.time()
    message = client.messages.create(
        model=model,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = time.time() - t0
    print(f"done in {elapsed:.1f}s ({message.usage.output_tokens} tokens)")
    return message.content[0].text.strip()


# ---------------------------------------------------------------------------
# Append analysis to report.md
# ---------------------------------------------------------------------------
EXPERT_MARKER = "## 🧠 Claude Expert Analysis"


def _patch_report(report_path: Path, analysis: str) -> None:
    content = report_path.read_text(encoding="utf-8", errors="replace")

    # Remove any existing Claude or Copilot expert section
    for pattern in [
        r"\n---\n## 🧠 Claude Expert Analysis.*$",
        r"\n---\n## 🧠 Expert Manual Analysis.*$",
    ]:
        content = re.sub(pattern, "", content, flags=re.DOTALL)

    content = content.rstrip()
    content += "\n\n" + analysis + "\n"
    report_path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Regenerate the static site
# ---------------------------------------------------------------------------
def _regenerate_site(run_dir: Path) -> None:
    print("\nRegenerating static site...")
    import json

    # Load summary to get results
    summary_path = run_dir / "exports" / "summary.json"
    if not summary_path.exists():
        print("  ⚠ No summary.json found — skipping site regeneration.")
        return

    try:
        from src.config import load_config
        from src.run_manager import RunManager
        from src.site_generator import generate_site

        cfg = load_config(Path("config.yaml") if Path("config.yaml").exists() else None)
        run_mgr = RunManager(cfg)
        run_mgr._run_dir = run_dir
        run_mgr._log_dir = run_dir / "logs"

        with open(summary_path, encoding="utf-8") as f:
            results = json.load(f)

        generate_site(results, run_mgr)
        print("  ✓ Site regenerated: index.html + site/ticker/*.html")
    except Exception as e:
        print(f"  ⚠ Site regeneration failed: {e}")
        print("  Run manually: python -m src.main -t <TICKER> (or just open existing index.html)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    # Fix Windows console encoding for UTF-8 output
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(description="Add Claude expert analysis to STOKS reports.")
    parser.add_argument("--run", default=None, help="Path to run folder (default: latest)")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Claude model to use")
    parser.add_argument("--ticker", "-t", action="append", default=[], help="Specific ticker(s) only")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing analysis")
    parser.add_argument("--no-proxy", action="store_true", help="Skip proxy setup")
    args = parser.parse_args()

    if not args.no_proxy:
        _ensure_proxy()

    # Find run
    run_dir = Path(args.run) if args.run else _latest_run()
    reports_dir = run_dir / "reports"
    print(f"Run: {run_dir}")
    print(f"Model: {args.model}")

    # Validate API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    # Use Intel LaaS base URL if configured, otherwise fall back to public API
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
    intel_cert = r"C:\Users\asalmon\.claude\certs\intel-ca-bundle.pem"

    if base_url and not args.no_proxy:
        # Intel LaaS internal endpoint — use internal CA cert, no external proxy needed
        cert = intel_cert if Path(intel_cert).exists() else True
        http_client = httpx.Client(verify=cert, timeout=120.0)
        print(f"Endpoint: {base_url}  (Intel LaaS)")
    elif not args.no_proxy:
        # External Anthropic API via corporate proxy
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or "http://proxy-iil.intel.com:912"
        http_client = httpx.Client(proxy=proxy_url, verify=False, timeout=120.0)
        print(f"Proxy: {proxy_url}")
    else:
        http_client = httpx.Client(timeout=120.0)

    client = anthropic.Anthropic(
        api_key=api_key,
        base_url=base_url if base_url else None,
        http_client=http_client,
    )

    # Collect tickers
    tickers = sorted(t.name for t in reports_dir.iterdir() if t.is_dir())
    if args.ticker:
        tickers = [t.upper() for t in args.ticker if t.upper() in tickers]
        if not tickers:
            print(f"ERROR: None of the specified tickers found in {reports_dir}")
            sys.exit(1)

    print(f"Tickers to analyze ({len(tickers)}): {', '.join(tickers)}\n")

    success, skipped, failed = 0, 0, 0

    for ticker in tickers:
        report_path = reports_dir / ticker / "report.md"
        if not report_path.exists():
            print(f"[{ticker}] ⚠ report.md not found — skipping")
            failed += 1
            continue

        report_md = report_path.read_text(encoding="utf-8", errors="replace")

        # Skip if already analyzed and not overwriting
        if EXPERT_MARKER in report_md and not args.overwrite:
            print(f"[{ticker}] Already has expert analysis (use --overwrite to redo)")
            skipped += 1
            continue

        try:
            analysis = _generate_analysis(client, ticker, report_md, args.model)
            _patch_report(report_path, analysis)
            print(f"  OK {ticker}: analysis written to {report_path}")
            success += 1
        except anthropic.APIConnectionError as e:
            print(f"  FAIL {ticker}: connection error - {e}")
            print("    Tip: Make sure HTTP_PROXY / HTTPS_PROXY are set (source proxy.bat)")
            failed += 1
        except anthropic.AuthenticationError:
            print("  FAIL Authentication failed - check ANTHROPIC_API_KEY", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"  FAIL {ticker}: error - {e}")
            failed += 1

        # Brief pause to respect rate limits
        time.sleep(0.5)

    print(f"\nDone. {success} analyzed, {skipped} skipped, {failed} failed.")

    # Regenerate site if any reports were updated
    if success > 0:
        _regenerate_site(run_dir)


if __name__ == "__main__":
    main()
