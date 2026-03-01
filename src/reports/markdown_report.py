"""
Markdown report generator.

Produces human-readable per-ticker analysis reports following the
Graham-Buffett value investing framework.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger


def _fmt_pct(v: float | None, decimals: int = 1) -> str:
    """Format a decimal as percentage string."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    return f"{v * 100:.{decimals}f}%"


def _fmt_num(v: float | None, decimals: int = 2) -> str:
    """Format a number with commas."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    return f"{v:,.{decimals}f}"


def _fmt_dollar(v: float | None, decimals: int = 2) -> str:
    """Format a dollar amount."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    if abs(v) >= 1e12:
        return f"${v / 1e12:.1f}T"
    if abs(v) >= 1e9:
        return f"${v / 1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:.1f}M"
    return f"${v:,.{decimals}f}"


def _signal_emoji(signal: str) -> str:
    """Map signal to visual indicator."""
    return {
        "STRONG_BUY_SIGNAL": "🟢🟢",
        "BUY_SIGNAL": "🟢",
        "WATCH": "🟡",
        "REJECT": "🔴",
    }.get(signal, "⚪")


def generate_ticker_markdown(ticker_result: dict[str, Any]) -> str:
    """
    Generate a complete Markdown analysis report for one ticker.

    Args:
        ticker_result: Pipeline result dict for a single ticker.

    Returns:
        Full Markdown report as a string.
    """
    data = ticker_result.get("data")
    stages = ticker_result.get("stages", {})
    signal = ticker_result["signal"]
    ticker = ticker_result["ticker"]

    lines: list[str] = []

    # Header
    company_name = data.info.name if data else ticker
    lines.append(f"# {_signal_emoji(signal)} {company_name} ({ticker})")
    lines.append("")
    lines.append(f"**Signal:** {signal}  ")
    lines.append(f"**Final Score:** {_fmt_num(ticker_result.get('final_score', 0), 0)}/100  ")
    lines.append(f"**Margin of Safety:** {_fmt_pct(ticker_result.get('margin_of_safety', 0))}  ")
    lines.append(f"**Quality Score:** {_fmt_num(ticker_result.get('quality_score', 0), 0)}/100  ")
    lines.append(f"**Cyclicality:** {ticker_result.get('cyclicality', 'UNKNOWN')}  ")
    lines.append("")
    lines.append(f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  ")
    lines.append("> ⚠️ **Disclaimer:** This is for educational/research purposes only. Not financial advice.")
    lines.append("")

    # Public Research Links
    lines.append("### 🔗 Research Links")
    lines.append("")
    lines.append(f"- [Yahoo Finance](https://finance.yahoo.com/quote/{ticker})")
    lines.append(f"- [Finviz](https://finviz.com/quote.ashx?t={ticker})")
    lines.append(f"- [SEC EDGAR Filings](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type=10-K&dateb=&owner=include&count=10)")
    lines.append(f"- [Macrotrends](https://www.macrotrends.net/stocks/charts/{ticker}/financial-ratios)")
    lines.append(f"- [Simply Wall St](https://simplywall.st/stocks/us/{ticker})")
    lines.append("")

    # Investment Thesis Summary
    stage_f = stages.get("f", {})
    drivers = stage_f.get("drivers", [])
    risks = stage_f.get("risks", [])
    invalidators = stage_f.get("invalidators", [])
    mos_val = ticker_result.get("margin_of_safety", 0)

    lines.append("---")
    lines.append("## 📝 Investment Thesis")
    lines.append("")
    _write_thesis_narrative(lines, data, stages, ticker_result)
    lines.append("")

    # Company Overview
    lines.append("---")
    lines.append("## Company Overview")
    lines.append("")
    if data and data.info:
        lines.append(f"| Field | Value |")
        lines.append(f"|-------|-------|")
        lines.append(f"| **Sector** | {data.info.sector} |")
        lines.append(f"| **Industry** | {data.info.industry} |")
        lines.append(f"| **Exchange** | {data.info.exchange} |")
        lines.append(f"| **Country** | {data.info.country} |")
        if data.price:
            lines.append(f"| **Price** | ${_fmt_num(data.price.current_price)} |")
            lines.append(f"| **Market Cap** | {_fmt_dollar(data.price.market_cap)} |")
        lines.append("")

    # Key Metrics
    lines.append("## Key Metrics")
    lines.append("")
    if data and data.metrics:
        m = data.metrics
        lines.append("| Metric | Value | Threshold |")
        lines.append("|--------|-------|-----------|")
        lines.append(f"| P/E Ratio | {_fmt_num(m.pe_ratio)} | ≤ 10 (Graham) |")
        lines.append(f"| Forward P/E | {_fmt_num(m.forward_pe)} | — |")
        lines.append(f"| P/B Ratio | {_fmt_num(m.pb_ratio)} | — |")
        lines.append(f"| EV/EBITDA | {_fmt_num(m.ev_ebitda)} | — |")
        lines.append(f"| ROE | {_fmt_pct(m.roe)} | ≥ 15% |")
        lines.append(f"| ROIC | {_fmt_pct(m.roic)} | ≥ 12% |")
        lines.append(f"| Gross Margin | {_fmt_pct(m.gross_margin)} | — |")
        lines.append(f"| Operating Margin | {_fmt_pct(m.operating_margin)} | — |")
        lines.append(f"| Net Margin | {_fmt_pct(m.net_margin)} | — |")
        lines.append(f"| FCF Yield | {_fmt_pct(m.fcf_yield)} | — |")
        lines.append(f"| D/E Ratio | {_fmt_num(m.debt_to_equity)} | ≤ 1.0 |")
        lines.append(f"| Current Ratio | {_fmt_num(m.current_ratio)} | ≥ 1.5 |")
        lines.append(f"| Interest Coverage | {_fmt_num(m.interest_coverage)} | — |")
        lines.append(f"| Beta | {_fmt_num(m.beta)} | — |")
        lines.append("")

    # Stage A: Hard Filters
    stage_a = stages.get("a", {})
    lines.append("## Stage A — Hard Filters")
    lines.append("")
    passed_a = stage_a.get("passed", False)
    lines.append(f"**Result:** {'✅ PASSED' if passed_a else '❌ FAILED'}")
    lines.append("")
    if stage_a.get("reasons"):
        lines.append("**Rejection reasons:**")
        for reason in stage_a["reasons"]:
            lines.append(f"- {reason}")
        lines.append("")
    a_metrics = stage_a.get("metrics", {})
    if a_metrics:
        lines.append("| Check | Value |")
        lines.append("|-------|-------|")
        for key, val in sorted(a_metrics.items()):
            lines.append(f"| {key} | {_fmt_num(val) if isinstance(val, float) else val} |")
        lines.append("")

    # Stage B: Quality
    stage_b = stages.get("b", {})
    lines.append("## Stage B — Quality Score")
    lines.append("")
    qs = stage_b.get("quality_score", 0)
    lines.append(f"**Quality Score:** {_fmt_num(qs, 0)}/100")
    lines.append("")
    components = stage_b.get("components", {})
    if components:
        lines.append("| Component | Score | Weight |")
        lines.append("|-----------|-------|--------|")
        for comp_name, comp_data in components.items():
            if isinstance(comp_data, dict):
                score = comp_data.get("score", 0)
                weight = comp_data.get("weight", 0)
                lines.append(f"| {comp_name} | {_fmt_num(score, 1)} | {_fmt_pct(weight, 0)} |")
            else:
                lines.append(f"| {comp_name} | {_fmt_num(comp_data, 1)} | — |")
        lines.append("")

    # Stage C: Cyclicality
    stage_c = stages.get("c", {})
    lines.append("## Stage C — Cyclicality Analysis")
    lines.append("")
    cyc_flag = stage_c.get("cyclicality_flag", "UNKNOWN")
    lines.append(f"**Classification:** {cyc_flag}")
    lines.append("")
    if stage_c.get("normalized_eps"):
        lines.append(f"**Normalized EPS:** ${_fmt_num(stage_c['normalized_eps'])}")
        lines.append("")
    if stage_c.get("margin_deviation"):
        lines.append(f"**Margin Deviation:** {_fmt_pct(stage_c['margin_deviation'])}")
        lines.append("")

    # Stage D: Valuation
    stage_d = stages.get("d", {})
    lines.append("## Stage D — Intrinsic Value & Margin of Safety")
    lines.append("")
    intrinsic = stage_d.get("intrinsic_range", {})
    if intrinsic:
        lines.append("| Method | Value |")
        lines.append("|--------|-------|")
        for method, val in intrinsic.items():
            lines.append(f"| {method} | ${_fmt_num(val)} |")
        lines.append("")
    mos = stage_d.get("margin_of_safety", 0)
    lines.append(f"**Margin of Safety:** {_fmt_pct(mos)}")
    lines.append("")
    if mos and mos > 0:
        if mos >= 0.45:
            lines.append("📊 Strong margin of safety — price is well below estimated intrinsic value.")
        elif mos >= 0.30:
            lines.append("📊 Adequate margin of safety — reasonable discount to intrinsic value.")
        else:
            lines.append("📊 Thin margin of safety — limited downside protection.")
    lines.append("")

    # Stage E: Value Trap Detection
    stage_e = stages.get("e", {})
    lines.append("## Stage E — Value Trap Detection")
    lines.append("")
    trap_flags = stage_e.get("trap_flags", [])
    trap_score = stage_e.get("trap_score", 0)
    if trap_flags:
        lines.append(f"**⚠️ Trap Score:** {trap_score} ({len(trap_flags)} flag(s))")
        lines.append("")
        for flag in trap_flags:
            lines.append(f"- 🚩 {flag}")
        lines.append("")
    else:
        lines.append("✅ No value trap flags detected.")
        lines.append("")

    # Stage F: Final Scoring
    stage_f = stages.get("f", {})
    lines.append("## Stage F — Final Score & Signal")
    lines.append("")
    lines.append(f"**Signal:** {_signal_emoji(signal)} **{signal}**")
    lines.append(f"**Final Score:** {_fmt_num(stage_f.get('final_score', 0), 1)}/100")
    lines.append("")
    score_breakdown = stage_f.get("score_breakdown", {})
    if score_breakdown:
        lines.append("| Component | Weighted Score |")
        lines.append("|-----------|---------------|")
        for comp, val in score_breakdown.items():
            lines.append(f"| {comp} | {_fmt_num(val, 1)} |")
        lines.append("")

    # Signal Drivers & Risks
    drivers = stage_f.get("drivers", [])
    risks = stage_f.get("risks", [])
    invalidators = stage_f.get("invalidators", [])

    if drivers:
        lines.append("### Top Signal Drivers")
        for d in drivers[:5]:
            lines.append(f"1. {d}")
        lines.append("")

    if risks:
        lines.append("### Top Risks")
        for r in risks[:5]:
            lines.append(f"1. {r}")
        lines.append("")

    if invalidators:
        lines.append("### Thesis Invalidators")
        for inv in invalidators[:5]:
            lines.append(f"- ❌ {inv}")
        lines.append("")

    # Financial History
    if data and data.financials:
        _add_financial_tables(lines, data.financials)

    # Footer
    lines.append("---")
    lines.append(f"*Report generated by STOKS Value Investing Scanner — {datetime.now().strftime('%Y-%m-%d')}*")
    lines.append("")

    return "\n".join(lines)


def _add_financial_tables(lines: list[str], financials) -> None:
    """Append financial history tables to the report."""
    lines.append("## Financial History")
    lines.append("")

    # Income statement
    inc = financials.income
    if inc is not None and not inc.empty:
        lines.append("### Income Statement (Annual)")
        lines.append("")
        cols_to_show = [
            c for c in ["revenue", "gross_profit", "operating_income", "net_income", "eps"]
            if c in inc.columns
        ]
        if cols_to_show:
            header = "| Year | " + " | ".join(c.replace("_", " ").title() for c in cols_to_show) + " |"
            sep = "|------|" + "|".join(["-------"] * len(cols_to_show)) + "|"
            lines.append(header)
            lines.append(sep)
            for year in sorted(inc.index):
                vals = []
                for col in cols_to_show:
                    v = inc.loc[year, col] if col in inc.columns else None
                    if col == "eps":
                        vals.append(f"${_fmt_num(v)}")
                    else:
                        vals.append(_fmt_dollar(v))
                lines.append(f"| {year} | " + " | ".join(vals) + " |")
            lines.append("")

    # Cash flow
    cf = financials.cashflow
    if cf is not None and not cf.empty:
        lines.append("### Cash Flow (Annual)")
        lines.append("")
        cols_to_show = [
            c for c in ["operating_cashflow", "capex", "free_cash_flow"]
            if c in cf.columns
        ]
        if cols_to_show:
            header = "| Year | " + " | ".join(c.replace("_", " ").title() for c in cols_to_show) + " |"
            sep = "|------|" + "|".join(["-------"] * len(cols_to_show)) + "|"
            lines.append(header)
            lines.append(sep)
            for year in sorted(cf.index):
                vals = []
                for col in cols_to_show:
                    v = cf.loc[year, col] if col in cf.columns else None
                    vals.append(_fmt_dollar(v))
                lines.append(f"| {year} | " + " | ".join(vals) + " |")
            lines.append("")


def save_ticker_markdown(
    ticker_result: dict[str, Any],
    output_dir: Path,
) -> Path:
    """
    Generate and save Markdown report for one ticker.

    Args:
        ticker_result: Pipeline result for ticker.
        output_dir: Directory to save into (e.g., reports/<TICKER>/).

    Returns:
        Path to the saved Markdown file.
    """
    md = generate_ticker_markdown(ticker_result)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "report.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    logger.debug(f"Markdown report saved: {path}")
    return path


def _write_thesis_narrative(
    lines: list[str],
    data,
    stages: dict[str, Any],
    ticker_result: dict[str, Any],
) -> None:
    """Write a narrative investment thesis summary."""
    ticker = ticker_result["ticker"]
    signal = ticker_result["signal"]
    name = data.info.name if data else ticker
    mos = ticker_result.get("margin_of_safety", 0)
    quality = ticker_result.get("quality_score", 0)
    price = data.price.current_price if data else 0
    stage_d = stages.get("d", {})
    stage_f = stages.get("f", {})
    intrinsic = stage_d.get("intrinsic_range", {})
    base_val = intrinsic.get("base", 0)

    if signal in ("STRONG_BUY_SIGNAL", "BUY_SIGNAL"):
        lines.append(
            f"**{name}** appears to be a genuine value opportunity based on our "
            f"Graham-Buffett screening framework. "
        )
        if mos > 0:
            lines.append(
                f"The stock currently trades at **${price:.2f}**, which is "
                f"**{mos:.0%} below** our estimated intrinsic value of "
                f"**${base_val:.2f}**. This provides a meaningful margin of "
                f"safety — the core principle of Benjamin Graham's investment "
                f"philosophy."
            )
        lines.append("")
        if quality >= 70:
            lines.append(
                f"Beyond being undervalued, the business demonstrates strong "
                f"quality characteristics (score: {quality:.0f}/100), including "
                f"consistent profitability, attractive returns on capital, and "
                f"stable margins — attributes Warren Buffett looks for when "
                f"identifying businesses with durable competitive advantages."
            )
        lines.append("")
    elif signal == "WATCH":
        lines.append(
            f"**{name}** passes our fundamental screening criteria but does not "
            f"yet meet the full requirements for a buy signal. "
        )
        if mos <= 0:
            lines.append(
                f"At **${price:.2f}**, the stock trades "
                f"**above** our estimated intrinsic value of **${base_val:.2f}**, "
                f"offering no margin of safety. While the business quality "
                f"may be solid (score: {quality:.0f}/100), Graham's #1 rule is "
                f"\"never overpay.\" This stock deserves monitoring for a better "
                f"entry point."
            )
        elif mos < 0.30:
            lines.append(
                f"At **${price:.2f}**, the margin of safety is only **{mos:.0%}** "
                f"(our buy threshold is 30%). The business quality is "
                f"{'strong' if quality >= 70 else 'adequate'} (score: {quality:.0f}/100), "
                f"but we'd want a larger discount before committing capital."
            )
        lines.append("")
    else:
        lines.append(
            f"**{name}** does not meet our value investing criteria at this time."
        )
        lines.append("")

    # Key thesis points from drivers
    drivers = stage_f.get("drivers", [])
    if drivers:
        lines.append("**Key thesis points:**")
        lines.append("")
        for d in drivers[:3]:
            lines.append(f"- {d}")
        lines.append("")

    # Key risks summary
    risks = stage_f.get("risks", [])
    if risks and risks[0] != "No significant risks identified in this analysis.":
        lines.append("**Key risks to monitor:**")
        lines.append("")
        for r in risks[:3]:
            lines.append(f"- {r}")
        lines.append("")
