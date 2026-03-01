"""
JSON report generator.

Produces machine-readable per-ticker JSON reports and summary exports.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger


def _safe_value(v: Any) -> Any:
    """Convert values to JSON-safe types."""
    if v is None:
        return None
    if isinstance(v, float):
        if pd.isna(v) or v != v:  # NaN check
            return None
        return round(v, 6)
    if isinstance(v, (int, bool, str)):
        return v
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, pd.DataFrame):
        return _df_to_dict(v)
    if isinstance(v, dict):
        return {str(k): _safe_value(vv) for k, vv in v.items()}
    if isinstance(v, (list, tuple)):
        return [_safe_value(item) for item in v]
    return str(v)


def _df_to_dict(df: pd.DataFrame) -> dict:
    """Convert DataFrame to a year-keyed dict of dicts."""
    if df is None or df.empty:
        return {}
    result = {}
    for idx, row in df.iterrows():
        year_key = str(idx)
        result[year_key] = {
            col: _safe_value(row[col]) for col in df.columns
        }
    return result


def generate_ticker_json(ticker_result: dict[str, Any]) -> dict:
    """
    Build a complete JSON report for one ticker.

    Args:
        ticker_result: Pipeline result dict for a single ticker.

    Returns:
        JSON-serializable dict with full analysis data.
    """
    data = ticker_result.get("data")
    stages = ticker_result.get("stages", {})

    report = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "version": "1.0",
            "disclaimer": (
                "This report is for educational/research purposes only. "
                "Not financial advice. Always do your own due diligence."
            ),
        },
        "ticker": ticker_result["ticker"],
        "signal": ticker_result["signal"],
        "final_score": _safe_value(ticker_result.get("final_score", 0)),
        "margin_of_safety": _safe_value(ticker_result.get("margin_of_safety", 0)),
        "quality_score": _safe_value(ticker_result.get("quality_score", 0)),
        "cyclicality": ticker_result.get("cyclicality", "UNKNOWN"),
        "trap_flags": ticker_result.get("trap_flags", []),
    }

    # Company info
    if data and data.info:
        report["company"] = {
            "name": data.info.name,
            "sector": data.info.sector,
            "industry": data.info.industry,
            "exchange": data.info.exchange,
            "country": data.info.country,
            "currency": data.info.currency,
        }

    # Price data
    if data and data.price:
        report["price"] = {
            "current_price": _safe_value(data.price.current_price),
            "market_cap": _safe_value(data.price.market_cap),
            "shares_outstanding": data.price.shares_outstanding,
        }

    # Key metrics
    if data and data.metrics:
        m = data.metrics
        report["metrics"] = {
            "pe_ratio": _safe_value(m.pe_ratio),
            "forward_pe": _safe_value(m.forward_pe),
            "pb_ratio": _safe_value(m.pb_ratio),
            "ev_ebitda": _safe_value(m.ev_ebitda),
            "roe": _safe_value(m.roe),
            "roic": _safe_value(m.roic),
            "gross_margin": _safe_value(m.gross_margin),
            "operating_margin": _safe_value(m.operating_margin),
            "net_margin": _safe_value(m.net_margin),
            "fcf_yield": _safe_value(m.fcf_yield),
            "dividend_yield": _safe_value(m.dividend_yield),
            "debt_to_equity": _safe_value(m.debt_to_equity),
            "current_ratio": _safe_value(m.current_ratio),
            "interest_coverage": _safe_value(m.interest_coverage),
            "beta": _safe_value(m.beta),
        }

    # Financial statements summary
    if data and data.financials:
        report["financials"] = {
            "income": _df_to_dict(data.financials.income),
            "balance": _df_to_dict(data.financials.balance),
            "cashflow": _df_to_dict(data.financials.cashflow),
        }

    # Intrinsic value range
    report["valuation"] = {
        "intrinsic_range": _safe_value(
            ticker_result.get("intrinsic_range", {})
        ),
        "margin_of_safety": _safe_value(
            ticker_result.get("margin_of_safety", 0)
        ),
    }

    # Stage details (compact)
    report["stages"] = {}
    for stage_key in ["a", "b", "c", "d", "e", "f"]:
        stage = stages.get(stage_key, {})
        # Strip the 'data' reference to avoid circular refs
        report["stages"][stage_key] = _safe_value(
            {k: v for k, v in stage.items() if k != "data"}
        )

    return report


def save_ticker_json(
    ticker_result: dict[str, Any],
    output_dir: Path,
) -> Path:
    """
    Generate and save JSON report for one ticker.

    Args:
        ticker_result: Pipeline result for ticker.
        output_dir: Directory to save into (e.g., reports/<TICKER>/).

    Returns:
        Path to the saved JSON file.
    """
    report = generate_ticker_json(ticker_result)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "report.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.debug(f"JSON report saved: {path}")
    return path


def save_summary_json(
    results: dict[str, Any],
    output_path: Path,
) -> Path:
    """
    Save a summary JSON with all candidates and metadata.

    Args:
        results: Full pipeline results dict.
        output_path: Path for the output file.

    Returns:
        Path to saved file.
    """
    summary = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "total_scanned": (
                len(results.get("candidates", []))
                + len(results.get("rejected", []))
                + len(results.get("errors", []))
            ),
            "total_candidates": len(results.get("candidates", [])),
            "total_rejected": len(results.get("rejected", [])),
            "total_errors": len(results.get("errors", [])),
        },
        "candidates": [],
        "rejected_summary": [],
        "errors": results.get("errors", []),
    }

    for c in results.get("candidates", []):
        summary["candidates"].append({
            "ticker": c["ticker"],
            "signal": c["signal"],
            "final_score": _safe_value(c.get("final_score", 0)),
            "margin_of_safety": _safe_value(c.get("margin_of_safety", 0)),
            "quality_score": _safe_value(c.get("quality_score", 0)),
            "cyclicality": c.get("cyclicality", "UNKNOWN"),
            "trap_flags": c.get("trap_flags", []),
        })

    for r in results.get("rejected", []):
        summary["rejected_summary"].append({
            "ticker": r["ticker"],
            "reasons": r.get("reject_reasons", []),
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.debug(f"Summary JSON saved: {output_path}")
    return output_path
