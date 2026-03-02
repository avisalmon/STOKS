"""
Static site generator — produces index.html + per-ticker detail pages.

Generates a beautifully crafted static HTML site using Jinja2 templates.
The site is self-contained (no external CDN dependencies) and designed
for GitHub Pages deployment from the repository root.

Output structure:
    index.html          (main dashboard)
    site/
        style.css       (shared styles)
        app.js          (sorting/filtering/search)
        methodology.html
        ticker/<TICKER>.html
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup
from loguru import logger

from src.run_manager import RunManager

# Template directory relative to this file
TEMPLATE_DIR = Path(__file__).parent / "templates"

# ---------------------------------------------------------------------------
# Glossary — plain-English explanations + Graham-Buffett perspective
# ---------------------------------------------------------------------------
GLOSSARY: dict[str, dict[str, str]] = {
    # Key Metrics
    "pe_ratio": {
        "title": "P/E Ratio (Price-to-Earnings)",
        "explanation": "How much investors pay per dollar of earnings. A P/E of 15 means you pay $15 for every $1 of annual profit.",
        "graham": "Graham insisted on buying only when P/E is below 15. A low P/E suggests the stock is cheap relative to its earnings — but always check that earnings are real and sustainable.",
    },
    "forward_pe": {
        "title": "Forward P/E",
        "explanation": "Same as P/E, but uses analysts' estimated future earnings instead of last year's reported earnings.",
        "graham": "Graham was skeptical of forecasts. Use forward P/E as a sanity check — if it's much lower than trailing P/E, ask why analysts expect a big jump.",
    },
    "pb_ratio": {
        "title": "P/B Ratio (Price-to-Book)",
        "explanation": "Compares the stock price to the company's net asset value (what you'd get if you sold everything and paid all debts). P/B of 1.0 means you're paying exactly book value.",
        "graham": "Graham's classic rule: never pay more than 1.5× book value. A stock trading below book value may be a bargain — the market is pricing it below liquidation value.",
    },
    "ev_ebitda": {
        "title": "EV/EBITDA",
        "explanation": "Enterprise Value divided by earnings before interest, taxes, depreciation & amortization. It measures how many years of operating cash it would take to buy the whole company (including its debt).",
        "graham": "Buffett likes EV/EBITDA below 10. It strips out accounting tricks and capital structure differences, giving a cleaner picture of value than P/E alone.",
    },
    "roe": {
        "title": "ROE (Return on Equity)",
        "explanation": "How much profit the company generates for each dollar shareholders have invested. An ROE of 15% means $0.15 profit per $1 of equity.",
        "graham": "Buffett seeks companies with consistently high ROE (above 15%). It signals a durable competitive advantage — the business earns strong returns without needing excessive capital.",
    },
    "roic": {
        "title": "ROIC (Return on Invested Capital)",
        "explanation": "Like ROE, but includes debt. It measures how efficiently the company uses ALL capital (equity + debt) to generate profits.",
        "graham": "ROIC above 10% indicates the company earns more than its cost of capital — it's genuinely creating value rather than destroying it. Buffett considers this a hallmark of great businesses.",
    },
    "gross_margin": {
        "title": "Gross Margin",
        "explanation": "Percentage of revenue left after subtracting the direct cost of making the product. A 40% gross margin means $0.40 of every $1 in sales is available to cover operations and profit.",
        "graham": "Buffett looks for gross margins above 40% as a sign of pricing power — a company that can charge premium prices likely has a moat protecting it from competitors.",
    },
    "operating_margin": {
        "title": "Operating Margin",
        "explanation": "Percentage of revenue remaining after all operating costs (salaries, rent, R&D) but before interest and taxes. It shows how efficiently the core business runs.",
        "graham": "Stable or growing operating margins over many years signal a well-managed business. Wide margins provide a cushion of safety during recessions.",
    },
    "net_margin": {
        "title": "Net Margin",
        "explanation": "The bottom line — what percentage of revenue turns into actual profit after everything is paid (costs, interest, taxes).",
        "graham": "Graham wanted companies with positive net margins for at least 10 consecutive years. Consistency matters more than the absolute number.",
    },
    "fcf_yield": {
        "title": "FCF Yield (Free Cash Flow Yield)",
        "explanation": "Free cash flow divided by market cap. Think of it as the company's real cash return on its stock price. A 10% yield means the company generates $0.10 of free cash per $1 of market value.",
        "graham": "Buffett cares deeply about free cash flow — it's the cash left after running and maintaining the business. High FCF yield means you're getting a lot of real cash for the price.",
    },
    "dividend_yield": {
        "title": "Dividend Yield",
        "explanation": "Annual dividend per share divided by share price. A 3% yield means $3 per year for every $100 invested.",
        "graham": "Graham favored companies that pay dividends — it's proof the profits are real, not just accounting. A long history of uninterrupted dividends signals financial strength.",
    },
    "debt_to_equity": {
        "title": "D/E Ratio (Debt-to-Equity)",
        "explanation": "Total debt divided by shareholders' equity. A D/E of 0.5 means the company has $0.50 of debt for every $1 of equity. Lower is safer.",
        "graham": "Graham's strict rule: D/E must be below 1.0. Low debt means the company can survive downturns without going bankrupt. Buffett agrees — he avoids heavily indebted companies.",
    },
    "current_ratio": {
        "title": "Current Ratio",
        "explanation": "Current assets divided by current liabilities. It measures whether the company can pay its bills due within the next 12 months. A ratio of 2.0 means it has $2 for every $1 it owes.",
        "graham": "Graham required a current ratio of at least 1.5. Below that, the company may struggle to meet short-term obligations — a red flag for financial health.",
    },
    "interest_coverage": {
        "title": "Interest Coverage",
        "explanation": "Operating income divided by interest expense. It shows how easily the company can pay interest on its debt. A ratio of 5 means profits cover interest payments 5 times over.",
        "graham": "Graham wanted interest coverage of at least 3×. Lower coverage means the company is dangerously close to not being able to service its debt, especially in a downturn.",
    },
    "beta": {
        "title": "Beta (Volatility)",
        "explanation": "Measures how much the stock swings compared to the overall market. Beta = 1 means it moves with the market; beta > 1 means it's more volatile; beta < 1 means it's calmer.",
        "graham": "Graham focused on value, not volatility. Buffett famously said 'volatility is not risk.' However, high-beta stocks require more emotional discipline to hold through drawdowns.",
    },
    # Stat cards
    "final_score": {
        "title": "Final Score",
        "explanation": "A composite score (0-100) combining quality, valuation, financial health, and safety metrics from all six pipeline stages.",
        "graham": "The higher the score, the more closely the stock matches the Graham-Buffett criteria. Scores above 70 indicate strong candidates; above 80 is exceptional.",
    },
    "margin_of_safety": {
        "title": "Margin of Safety",
        "explanation": "How far below intrinsic value the stock trades. A 40% margin of safety means you're buying at a 40% discount to its estimated true worth.",
        "graham": "This is Graham's most important concept. He insisted on at least a 30% margin of safety — buying well below value protects you from errors in your analysis and market downturns.",
    },
    "quality_score": {
        "title": "Quality Score",
        "explanation": "A score (0-100) measuring the company's financial quality: profitability consistency, return on capital, balance sheet strength, and earnings predictability.",
        "graham": "Quality comes before price. Buffett evolved Graham's framework: 'It's far better to buy a wonderful company at a fair price than a fair company at a wonderful price.'",
    },
    "current_price": {
        "title": "Current Price",
        "explanation": "The latest market price per share from the stock exchange.",
        "graham": "Mr. Market offers a price every day — sometimes too high, sometimes too low. Your job is to buy only when the price is significantly below intrinsic value.",
    },
    "market_cap": {
        "title": "Market Cap (Market Capitalization)",
        "explanation": "The total value the stock market places on the entire company (share price × total shares outstanding). It tells you the company's size.",
        "graham": "Graham preferred mid-to-large cap companies for safety. Buffett evolved to favor any size — what matters is the business quality and price, not the size alone.",
    },
    # Intrinsic value methods
    "low": {
        "title": "Intrinsic Value — Conservative",
        "explanation": "The lowest estimate of the company's true worth, calculated using pessimistic assumptions about growth, margins, and discount rates.",
        "graham": "Graham would focus here. The conservative estimate assumes things go somewhat wrong — buying below this price gives you the strongest margin of safety.",
    },
    "base": {
        "title": "Intrinsic Value — Base Case",
        "explanation": "The middle estimate of intrinsic worth, using moderate growth assumptions and normal discount rates. This is the 'most likely' fair value.",
        "graham": "A reasonable target. If the current price is well below the base case, the stock deserves serious consideration.",
    },
    "high": {
        "title": "Intrinsic Value — Optimistic",
        "explanation": "The highest estimate of fair value, assuming favorable growth, margin expansion, and lower risk. Represents the best-case scenario.",
        "graham": "Use this with caution. Graham warned against over-optimism. The gap between 'low' and 'high' shows how uncertain the valuation is.",
    },
    # Financial History columns
    "revenue": {
        "title": "Revenue (Total Sales)",
        "explanation": "The total money the company brings in from selling its products or services before any costs are subtracted. It's the 'top line' of the income statement.",
        "graham": "Graham looked for companies with steadily growing revenue over 10+ years. Consistency matters — erratic revenue suggests an unpredictable business that's hard to value.",
    },
    "gross_profit": {
        "title": "Gross Profit",
        "explanation": "Revenue minus the direct cost of making the product (cost of goods sold). It shows how much the company earns before overhead, salaries, marketing, etc.",
        "graham": "Buffett wants gross profit that is consistently above 40% of revenue — a sign of pricing power and competitive moat. Shrinking gross profit signals trouble.",
    },
    "operating_income": {
        "title": "Operating Income",
        "explanation": "Gross profit minus all operating expenses (salaries, rent, R&D, marketing). It's the profit from running the core business, before interest and taxes.",
        "graham": "Stable or growing operating income over many years shows management efficiency. A company that grows revenue but not operating income has a cost problem.",
    },
    "net_income": {
        "title": "Net Income (Bottom Line)",
        "explanation": "The final profit after ALL expenses: costs, operating expenses, interest, and taxes. This is what's left for shareholders.",
        "graham": "Graham required positive net income for at least 10 consecutive years. One bad year can happen, but repeated losses disqualify a company from consideration.",
    },
    "eps": {
        "title": "EPS (Earnings Per Share)",
        "explanation": "Net income divided by the number of shares outstanding. It tells you how much profit the company earned for each share you own.",
        "graham": "Graham's cornerstone metric. He wanted to see EPS growing at least 33% over the past 10 years. Declining EPS is a major red flag — the business is earning less per share.",
    },
    # Cash Flow columns
    "operating_cashflow": {
        "title": "Operating Cash Flow",
        "explanation": "The actual cash generated by the company's day-to-day business operations. Unlike net income, this strips out accounting tricks (depreciation, accruals) and shows real cash.",
        "graham": "Buffett says 'cash is king.' Operating cash flow should ideally exceed net income — if net income is high but cash flow is low, earnings may not be real.",
    },
    "capex": {
        "title": "CapEx (Capital Expenditures)",
        "explanation": "Money spent on buying or maintaining physical assets: factories, equipment, technology, buildings. It's the cost of keeping the business running and growing. Shown as a negative number because it's cash going out.",
        "graham": "Buffett prefers companies with low CapEx relative to earnings — 'capital-light' businesses. High CapEx means the company must constantly reinvest just to stay competitive, leaving less cash for shareholders.",
    },
    "free_cash_flow": {
        "title": "Free Cash Flow (FCF)",
        "explanation": "Operating cash flow minus CapEx. It's the cash left over after running and maintaining the business — the money available to pay dividends, buy back stock, reduce debt, or invest in growth.",
        "graham": "This is the real measure of a company's earning power. Buffett values businesses based on FCF, not accounting earnings. Consistently positive and growing FCF is the hallmark of a wonderful business. Negative FCF means the company is burning cash.",
    },
    # Section headings
    "financial_history": {
        "title": "How to Read Financial History",
        "explanation": "This table shows years of income statement data. All numbers should ideally trend upward over time. Revenue is the top line (total sales); Gross Profit, Operating Income, and Net Income show progressively deeper layers of profitability; EPS is what you earn per share.",
        "graham": "Graham required at least 10 years of financial history. Look for steady, predictable growth — not wild swings. A company whose revenue grows but net income shrinks has a cost problem. Consistent EPS growth of 5-10% per year is the ideal.",
    },
    "cashflow_history": {
        "title": "How to Read Cash Flow History",
        "explanation": "This table has 3 columns: Operating CF (cash generated by the business), CapEx (cash spent on equipment — ALWAYS shown as negative, that is normal!), and Free Cash Flow (what is left: Operating CF minus CapEx). Do not be alarmed by the negative CapEx numbers. Focus on the FREE CASH FLOW column on the right — that should be positive and growing.",
        "graham": "Buffett says 'owner earnings' (essentially FCF) is the true measure of a business. If Operating CF is $1B and CapEx is -$200M, the FCF is $800M — that is excellent. The only red flag is when the rightmost FCF column is negative, meaning the business burns more cash than it earns.",
    },
}


def generate_site(
    results: dict[str, Any],
    run_mgr: RunManager,
) -> Path:
    """
    Generate the complete static site.

    Args:
        results: Full pipeline results dict.
        run_mgr: Run folder manager.

    Returns:
        Path to generated index.html.
    """
    repo_root = Path.cwd()
    site_dir = repo_root / "site"
    ticker_dir = site_dir / "ticker"

    # Create directories
    site_dir.mkdir(exist_ok=True)
    ticker_dir.mkdir(exist_ok=True)

    # Setup Jinja2
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    env.filters["fmt_pct"] = _fmt_pct
    env.filters["fmt_num"] = _fmt_num
    env.filters["fmt_dollar"] = _fmt_dollar
    env.filters["signal_class"] = _signal_class
    env.filters["signal_label"] = _signal_label
    env.filters["sparkline"] = _sparkline_svg

    # Prepare template data
    candidates = results.get("candidates", [])
    rejected = results.get("rejected", [])
    errors = results.get("errors", [])
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    candidate_rows = [_build_candidate_row(c) for c in candidates]
    rejected_rows = [_build_rejected_row(r) for r in rejected]

    # Generate index.html at repo root
    index_tmpl = env.get_template("index.html")
    index_html = index_tmpl.render(
        candidates=candidate_rows,
        rejected=rejected_rows,
        errors=errors,
        total_scanned=len(candidates) + len(rejected) + len(errors),
        total_candidates=len(candidates),
        total_rejected=len(rejected),
        total_errors=len(errors),
        generated_at=generated_at,
        run_folder=str(run_mgr.run_dir),
    )
    index_path = repo_root / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    logger.info(f"Static site: index.html generated at {index_path}")

    # Generate per-ticker detail pages
    ticker_tmpl = env.get_template("ticker_detail.html")
    for c in candidates:
        try:
            ticker_data = _build_ticker_detail(c)
            ticker_html = ticker_tmpl.render(
                **ticker_data,
                glossary=GLOSSARY,
                generated_at=generated_at,
            )
            ticker_path = ticker_dir / f"{c['ticker']}.html"
            ticker_path.write_text(ticker_html, encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to generate ticker page for {c['ticker']}: {e}")

    # Generate methodology page
    method_tmpl = env.get_template("methodology.html")
    method_html = method_tmpl.render(generated_at=generated_at)
    method_path = site_dir / "methodology.html"
    method_path.write_text(method_html, encoding="utf-8")

    # Copy static assets
    _generate_css(site_dir / "style.css")
    _generate_js(site_dir / "app.js")

    total_pages = 1 + len(candidates) + 1  # index + tickers + methodology
    logger.info(f"Static site: {total_pages} pages generated")

    return index_path


# ---------------------------------------------------------------------------
# Data preparation helpers
# ---------------------------------------------------------------------------

def _build_candidate_row(c: dict) -> dict:
    """Build a flat dict for a candidate row in the index table."""
    data = c.get("data")
    return {
        "ticker": c["ticker"],
        "name": data.info.name if data else c["ticker"],
        "signal": c["signal"],
        "final_score": c.get("final_score", 0),
        "margin_of_safety": c.get("margin_of_safety", 0),
        "quality_score": c.get("quality_score", 0),
        "cyclicality": c.get("cyclicality", "UNKNOWN"),
        "trap_count": len(c.get("trap_flags", [])),
        "sector": data.info.sector if data else "",
        "industry": data.info.industry if data else "",
        "price": data.price.current_price if data else 0,
        "market_cap": data.price.market_cap if data else 0,
        "pe_ratio": data.metrics.pe_ratio if data else None,
        "roe": data.metrics.roe if data else None,
        "roic": data.metrics.roic if data else None,
        "fcf_yield": data.metrics.fcf_yield if data else None,
        "debt_to_equity": data.metrics.debt_to_equity if data else None,
        "intrinsic_low": _safe_min(c.get("intrinsic_range", {})),
        "intrinsic_high": _safe_max(c.get("intrinsic_range", {})),
        "sparklines": _extract_sparkline_data(data),
    }


def _build_rejected_row(r: dict) -> dict:
    """Build a flat dict for a rejected row."""
    data = r.get("data")
    return {
        "ticker": r["ticker"],
        "name": data.info.name if data else r["ticker"],
        "sector": data.info.sector if data else "",
        "reasons": r.get("reject_reasons", []),
        "reasons_str": "; ".join(r.get("reject_reasons", [])),
    }


def _build_ticker_detail(c: dict) -> dict:
    """Build detailed data dict for a ticker detail page."""
    data = c.get("data")
    stages = c.get("stages", {})

    detail = {
        "ticker": c["ticker"],
        "name": data.info.name if data else c["ticker"],
        "signal": c["signal"],
        "final_score": c.get("final_score", 0),
        "margin_of_safety": c.get("margin_of_safety", 0),
        "quality_score": c.get("quality_score", 0),
        "cyclicality": c.get("cyclicality", "UNKNOWN"),
        "trap_flags": c.get("trap_flags", []),
        "sector": data.info.sector if data else "",
        "industry": data.info.industry if data else "",
        "exchange": data.info.exchange if data else "",
        "country": data.info.country if data else "",
        "price": data.price.current_price if data else 0,
        "market_cap": data.price.market_cap if data else 0,
        "intrinsic_range": c.get("intrinsic_range", {}),
        "metrics": {},
        "stage_a": stages.get("a", {}),
        "stage_b": stages.get("b", {}),
        "stage_c": stages.get("c", {}),
        "stage_d": stages.get("d", {}),
        "stage_e": stages.get("e", {}),
        "stage_f": stages.get("f", {}),
        "income_history": [],
        "cashflow_history": [],
        "sparklines": _extract_sparkline_data(data),
    }

    if data and data.metrics:
        m = data.metrics
        detail["metrics"] = {
            "pe_ratio": m.pe_ratio,
            "forward_pe": m.forward_pe,
            "pb_ratio": m.pb_ratio,
            "ev_ebitda": m.ev_ebitda,
            "roe": m.roe,
            "roic": m.roic,
            "gross_margin": m.gross_margin,
            "operating_margin": m.operating_margin,
            "net_margin": m.net_margin,
            "fcf_yield": m.fcf_yield,
            "dividend_yield": m.dividend_yield,
            "debt_to_equity": m.debt_to_equity,
            "current_ratio": m.current_ratio,
            "interest_coverage": m.interest_coverage,
            "beta": m.beta,
        }

    # Financial history as list of dicts for easy template iteration
    if data and data.financials:
        inc = data.financials.income
        if inc is not None and not inc.empty:
            for year in sorted(inc.index):
                row = {"year": year}
                for col in inc.columns:
                    val = inc.loc[year, col]
                    row[col] = float(val) if pd.notna(val) else None
                detail["income_history"].append(row)

        cf = data.financials.cashflow
        if cf is not None and not cf.empty:
            for year in sorted(cf.index):
                row = {"year": year}
                for col in cf.columns:
                    val = cf.loc[year, col]
                    row[col] = float(val) if pd.notna(val) else None
                detail["cashflow_history"].append(row)

    return detail


# ---------------------------------------------------------------------------
# Jinja2 filter helpers
# ---------------------------------------------------------------------------

def _fmt_pct(v, decimals=1) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    return f"{v * 100:.{decimals}f}%"


def _fmt_num(v, decimals=2) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    return f"{v:,.{decimals}f}"


def _fmt_dollar(v, decimals=2) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    if abs(v) >= 1e12:
        return f"${v / 1e12:.1f}T"
    if abs(v) >= 1e9:
        return f"${v / 1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:.1f}M"
    return f"${v:,.{decimals}f}"


def _signal_class(signal: str) -> str:
    return {
        "STRONG_BUY_SIGNAL": "signal-strong-buy",
        "BUY_SIGNAL": "signal-buy",
        "WATCH": "signal-watch",
        "REJECT": "signal-reject",
    }.get(signal, "signal-unknown")


def _signal_label(signal: str) -> str:
    return {
        "STRONG_BUY_SIGNAL": "STRONG BUY",
        "BUY_SIGNAL": "BUY",
        "WATCH": "WATCH",
        "REJECT": "REJECT",
    }.get(signal, signal)


def _safe_min(d: dict) -> float | None:
    vals = [v for v in d.values() if v is not None and isinstance(v, (int, float))]
    return min(vals) if vals else None


def _safe_max(d: dict) -> float | None:
    vals = [v for v in d.values() if v is not None and isinstance(v, (int, float))]
    return max(vals) if vals else None


def _sparkline_svg(
    values: list,
    width: int = 80,
    height: int = 24,
    color: str = "#58a6ff",
    fill: bool = True,
) -> str:
    """Generate an inline SVG sparkline from a list of numeric values."""
    nums = [float(v) for v in values if v is not None and v == v]  # filter NaN
    if len(nums) < 2:
        return ""
    vmin = min(nums)
    vmax = max(nums)
    vrange = vmax - vmin if vmax != vmin else 1
    pad = 1  # 1px padding
    w = width - 2 * pad
    h = height - 2 * pad
    points = []
    for i, v in enumerate(nums):
        x = pad + (i / (len(nums) - 1)) * w
        y = pad + h - ((v - vmin) / vrange) * h
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    # Determine trend color: green if last > first, red if declining
    trend_color = color
    if nums[-1] > nums[0] * 1.02:
        trend_color = "#3fb950"  # green
    elif nums[-1] < nums[0] * 0.98:
        trend_color = "#f85149"  # red
    else:
        trend_color = "#d29922"  # yellow (flat)
    fill_path = ""
    if fill:
        fill_points = f"{pad:.1f},{pad + h:.1f} " + polyline + f" {pad + w:.1f},{pad + h:.1f}"
        fill_path = (
            f'<polygon points="{fill_points}" '
            f'fill="{trend_color}" fill-opacity="0.12" />'
        )
    svg = (
        f'<svg class="sparkline" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        f'{fill_path}'
        f'<polyline points="{polyline}" fill="none" '
        f'stroke="{trend_color}" stroke-width="1.5" stroke-linecap="round" '
        f'stroke-linejoin="round" />'
        f'<circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" '
        f'r="2" fill="{trend_color}" />'
        f'</svg>'
    )
    return Markup(svg)


def _extract_sparkline_data(data) -> dict[str, list]:
    """Extract sparkline-ready lists from TickerData financial history."""
    sparklines: dict[str, list] = {
        "revenue": [],
        "eps": [],
        "net_income": [],
        "fcf": [],
    }
    if data is None or data.financials is None:
        return sparklines
    inc = data.financials.income
    if inc is not None and not inc.empty:
        for year in sorted(inc.index):
            if "revenue" in inc.columns:
                v = inc.loc[year, "revenue"]
                sparklines["revenue"].append(float(v) if pd.notna(v) else None)
            if "eps" in inc.columns:
                v = inc.loc[year, "eps"]
                sparklines["eps"].append(float(v) if pd.notna(v) else None)
            if "net_income" in inc.columns:
                v = inc.loc[year, "net_income"]
                sparklines["net_income"].append(float(v) if pd.notna(v) else None)
    cf = data.financials.cashflow
    if cf is not None and not cf.empty:
        for year in sorted(cf.index):
            if "free_cash_flow" in cf.columns:
                v = cf.loc[year, "free_cash_flow"]
                sparklines["fcf"].append(float(v) if pd.notna(v) else None)
    return sparklines


# ---------------------------------------------------------------------------
# CSS & JS generation (self-contained, no CDN)
# ---------------------------------------------------------------------------

def _generate_css(path: Path) -> None:
    """Generate the shared CSS file."""
    css = _get_css_content()
    path.write_text(css, encoding="utf-8")


def _generate_js(path: Path) -> None:
    """Generate the shared JS file."""
    js = _get_js_content()
    js_path = path
    js_path.write_text(js, encoding="utf-8")


def _get_css_content() -> str:
    return """\
/* STOKS — Value Investing Scanner Styles */
:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --bg-card: #1c2128;
    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
    --text-muted: #6e7681;
    --border: #30363d;
    --accent: #58a6ff;
    --accent-hover: #79c0ff;
    --green: #3fb950;
    --green-dim: #238636;
    --yellow: #d29922;
    --yellow-dim: #9e6a03;
    --red: #f85149;
    --red-dim: #da3633;
    --orange: #db6d28;
    --purple: #bc8cff;
    --shadow: 0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2);
    --shadow-lg: 0 10px 30px rgba(0,0,0,0.4);
    --radius: 8px;
    --radius-lg: 12px;
    --transition: 0.2s ease;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    min-height: 100vh;
}

a { color: var(--accent); text-decoration: none; transition: color var(--transition); }
a:hover { color: var(--accent-hover); text-decoration: underline; }

/* Layout */
.container { max-width: 1400px; margin: 0 auto; padding: 0 24px; }

header {
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    padding: 20px 0;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(10px);
}
header .container { display: flex; align-items: center; justify-content: space-between; }
header h1 { font-size: 1.5rem; font-weight: 700; letter-spacing: -0.5px; }
header h1 span { color: var(--accent); }
header nav a { margin-left: 24px; color: var(--text-secondary); font-size: 0.875rem; }
header nav a:hover { color: var(--text-primary); }

/* Disclaimer Banner */
.disclaimer {
    background: linear-gradient(135deg, var(--yellow-dim), var(--orange));
    color: #fff;
    padding: 10px 20px;
    text-align: center;
    font-size: 0.8rem;
    font-weight: 500;
}

/* Data Freshness Banner */
.data-freshness {
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border);
    color: var(--text-secondary);
    padding: 10px 20px;
    text-align: center;
    font-size: 0.82rem;
    line-height: 1.5;
}
.data-freshness strong {
    color: var(--accent);
}

/* Stats Strip */
.stats-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    padding: 24px 0;
}
.stat-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    text-align: center;
    transition: all var(--transition);
}
.stat-card:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: var(--shadow); }
.stat-card .value { font-size: 2rem; font-weight: 700; color: var(--accent); }
.stat-card .label { font-size: 0.8rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

/* Section */
.section { padding: 32px 0; }
.section h2 {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}

/* Controls */
.controls {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
    align-items: center;
}
.search-box {
    flex: 1;
    min-width: 200px;
    padding: 8px 14px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text-primary);
    font-size: 0.875rem;
    outline: none;
    transition: border-color var(--transition);
}
.search-box:focus { border-color: var(--accent); }
.search-box::placeholder { color: var(--text-muted); }

select.filter-select {
    padding: 8px 14px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text-primary);
    font-size: 0.875rem;
    cursor: pointer;
    outline: none;
}
select.filter-select:focus { border-color: var(--accent); }

/* Table */
.table-wrapper {
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--bg-secondary);
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
}
thead { background: var(--bg-tertiary); }
th {
    padding: 12px 16px;
    text-align: left;
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
    position: relative;
}
th:hover { color: var(--accent); }
th.sort-asc::after { content: " ▲"; font-size: 0.65rem; }
th.sort-desc::after { content: " ▼"; font-size: 0.65rem; }

td {
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
}
tr:last-child td { border-bottom: none; }
tr:hover { background: rgba(88, 166, 255, 0.04); }

td.num { text-align: right; font-variant-numeric: tabular-nums; }

/* Signal Badges */
.signal-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.signal-strong-buy { background: var(--green-dim); color: var(--green); }
.signal-buy { background: rgba(63, 185, 80, 0.15); color: var(--green); }
.signal-watch { background: rgba(210, 153, 34, 0.15); color: var(--yellow); }
.signal-reject { background: rgba(248, 81, 73, 0.1); color: var(--red); }

/* Score Bar */
.score-bar {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-width: 80px;
}
.score-bar .bar {
    flex: 1;
    height: 6px;
    background: var(--bg-tertiary);
    border-radius: 3px;
    overflow: hidden;
    min-width: 40px;
}
.score-bar .bar .fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease;
}
.score-bar .value { font-size: 0.8rem; font-weight: 600; min-width: 24px; }

/* MOS Bar Colors */
.mos-high { background: var(--green); }
.mos-mid { background: var(--yellow); }
.mos-low { background: var(--red); }

/* Detail Page */
.detail-header {
    padding: 32px 0;
    border-bottom: 1px solid var(--border);
}
.detail-header h1 { font-size: 2rem; font-weight: 700; }
.detail-header .subtitle { color: var(--text-secondary); margin-top: 4px; }

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 12px;
    margin: 20px 0;
}
.metric-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px;
}
.metric-card .metric-label { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
.metric-card .metric-value { font-size: 1.2rem; font-weight: 600; margin-top: 4px; }

.stage-section {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 20px;
    margin: 16px 0;
}
.stage-section h3 { font-size: 1rem; font-weight: 600; margin-bottom: 12px; }

.flag-list { list-style: none; padding: 0; }
.flag-list li {
    padding: 6px 10px;
    margin: 4px 0;
    background: rgba(248, 81, 73, 0.08);
    border-left: 3px solid var(--red);
    border-radius: 0 var(--radius) var(--radius) 0;
    font-size: 0.85rem;
}

/* Footer */
footer {
    border-top: 1px solid var(--border);
    padding: 24px 0;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8rem;
    margin-top: 40px;
}

/* Empty state */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-secondary);
}
.empty-state .icon { font-size: 3rem; margin-bottom: 16px; }
.empty-state h3 { font-size: 1.2rem; margin-bottom: 8px; color: var(--text-primary); }

/* Sparkline */
.sparkline-cell { padding: 4px 8px; text-align: center; }
.sparkline-cell svg.sparkline { vertical-align: middle; }
.sparkline-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin: 20px 0; }
.sparkline-card { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; text-align: center; }
.sparkline-card .sparkline-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }
.sparkline-card .sparkline-chart { display: flex; justify-content: center; }
.sparkline-card svg.sparkline { display: block; }

/* Help Tooltip (?) */
.help-icon {
    display: inline-flex; align-items: center; justify-content: center;
    width: 18px; height: 18px; border-radius: 50%;
    background: var(--bg-tertiary); border: 1px solid var(--border);
    color: var(--text-muted); font-size: 0.65rem; font-weight: 700;
    cursor: pointer; margin-left: 6px; vertical-align: middle;
    transition: all var(--transition); flex-shrink: 0;
}
.help-icon:hover { background: var(--accent); color: var(--bg-primary); border-color: var(--accent); }
.metric-label { display: flex; align-items: center; }
.stat-card .label { display: flex; align-items: center; justify-content: center; gap: 4px; }

/* Glossary Modal Overlay */
.glossary-overlay {
    display: none; position: fixed; inset: 0; z-index: 9999;
    background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
    align-items: center; justify-content: center; padding: 20px;
}
.glossary-overlay.active { display: flex; }
.glossary-modal {
    background: var(--bg-secondary); border: 1px solid var(--border);
    border-radius: var(--radius-lg); padding: 28px 32px;
    max-width: 520px; width: 100%; box-shadow: var(--shadow-lg);
    position: relative; animation: glossaryIn 0.2s ease;
}
@keyframes glossaryIn {
    from { opacity: 0; transform: translateY(10px) scale(0.97); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}
.glossary-modal .gm-close {
    position: absolute; top: 14px; right: 16px;
    background: none; border: none; color: var(--text-muted);
    font-size: 1.3rem; cursor: pointer; line-height: 1;
    transition: color var(--transition);
}
.glossary-modal .gm-close:hover { color: var(--text-primary); }
.glossary-modal h3 { font-size: 1.1rem; font-weight: 700; margin-bottom: 14px; color: var(--accent); }
.glossary-modal .gm-section { margin-bottom: 14px; }
.glossary-modal .gm-section:last-child { margin-bottom: 0; }
.glossary-modal .gm-heading {
    font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 6px;
}
.glossary-modal .gm-text { font-size: 0.9rem; line-height: 1.6; color: var(--text-primary); }
.glossary-modal .gm-graham {
    background: rgba(63,185,80,0.08); border-left: 3px solid var(--green);
    border-radius: 0 var(--radius) var(--radius) 0;
    padding: 10px 14px; font-size: 0.85rem; line-height: 1.6;
    color: var(--text-secondary); margin-top: 4px;
}

/* Responsive */
@media (max-width: 768px) {
    .container { padding: 0 16px; }
    .stats-strip { grid-template-columns: repeat(2, 1fr); }
    .controls { flex-direction: column; }
    header .container { flex-direction: column; gap: 12px; }
    header nav a { margin-left: 0; margin-right: 16px; }
}
"""


def _get_js_content() -> str:
    return """\
/* STOKS — Table Sorting, Filtering & Search */
(function() {
    'use strict';

    // Table sorting
    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const table = th.closest('table');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const col = th.dataset.sort;
            const type = th.dataset.type || 'string';
            const currentDir = th.classList.contains('sort-asc') ? 'desc' : 'asc';

            // Clear all sort indicators
            table.querySelectorAll('th').forEach(t => t.classList.remove('sort-asc', 'sort-desc'));
            th.classList.add('sort-' + currentDir);

            rows.sort((a, b) => {
                let aVal = a.querySelector(`td[data-col="${col}"]`)?.dataset.value || '';
                let bVal = b.querySelector(`td[data-col="${col}"]`)?.dataset.value || '';

                if (type === 'number') {
                    aVal = parseFloat(aVal) || 0;
                    bVal = parseFloat(bVal) || 0;
                } else {
                    aVal = aVal.toLowerCase();
                    bVal = bVal.toLowerCase();
                }

                if (aVal < bVal) return currentDir === 'asc' ? -1 : 1;
                if (aVal > bVal) return currentDir === 'asc' ? 1 : -1;
                return 0;
            });

            rows.forEach(row => tbody.appendChild(row));
        });
    });

    // Search
    const searchBox = document.getElementById('search-box');
    if (searchBox) {
        searchBox.addEventListener('input', filterTable);
    }

    // Sector filter
    const sectorFilter = document.getElementById('sector-filter');
    if (sectorFilter) {
        sectorFilter.addEventListener('change', filterTable);
    }

    // Signal filter
    const signalFilter = document.getElementById('signal-filter');
    if (signalFilter) {
        signalFilter.addEventListener('change', filterTable);
    }

    function filterTable() {
        const search = (searchBox?.value || '').toLowerCase();
        const sector = sectorFilter?.value || '';
        const signal = signalFilter?.value || '';

        document.querySelectorAll('#candidates-table tbody tr').forEach(row => {
            const ticker = row.dataset.ticker?.toLowerCase() || '';
            const name = row.dataset.name?.toLowerCase() || '';
            const rowSector = row.dataset.sector || '';
            const rowSignal = row.dataset.signal || '';

            const matchSearch = !search || ticker.includes(search) || name.includes(search);
            const matchSector = !sector || rowSector === sector;
            const matchSignal = !signal || rowSignal === signal;

            row.style.display = (matchSearch && matchSector && matchSignal) ? '' : 'none';
        });
    }

    // Tab switching for rejected/errors
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            document.getElementById(target)?.classList.add('active');
        });
    });
})();

/* Glossary Help Popup */
(function() {
    'use strict';
    const overlay = document.getElementById('glossary-overlay');
    if (!overlay) return;
    const modal = overlay.querySelector('.glossary-modal');
    const titleEl = modal?.querySelector('.gm-title');
    const explEl = modal?.querySelector('.gm-expl');
    const grahamEl = modal?.querySelector('.gm-graham-text');
    const closeBtn = modal?.querySelector('.gm-close');

    document.addEventListener('click', e => {
        const icon = e.target.closest('.help-icon');
        if (!icon) return;
        e.stopPropagation();
        const t = icon.dataset.glossTitle || '';
        const ex = icon.dataset.glossExpl || '';
        const gr = icon.dataset.glossGraham || '';
        if (titleEl) titleEl.textContent = t;
        if (explEl) explEl.textContent = ex;
        if (grahamEl) grahamEl.textContent = gr;
        overlay.classList.add('active');
    });

    if (closeBtn) closeBtn.addEventListener('click', () => overlay.classList.remove('active'));
    overlay.addEventListener('click', e => {
        if (e.target === overlay) overlay.classList.remove('active');
    });
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') overlay.classList.remove('active');
    });
})();
"""
