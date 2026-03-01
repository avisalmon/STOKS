"""
CSV export generator.

Produces candidates.csv and rejected.csv for easy spreadsheet analysis.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger


def export_candidates_csv(
    candidates: list[dict[str, Any]],
    output_path: Path,
) -> Path:
    """
    Export candidates to a ranked CSV file.

    Args:
        candidates: List of candidate result dicts from pipeline.
        output_path: Path for the CSV file.

    Returns:
        Path to saved CSV.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "rank",
        "ticker",
        "company",
        "signal",
        "final_score",
        "margin_of_safety",
        "quality_score",
        "cyclicality",
        "trap_flags",
        "sector",
        "industry",
        "market_cap",
        "price",
        "pe_ratio",
        "pb_ratio",
        "roe",
        "roic",
        "gross_margin",
        "operating_margin",
        "fcf_yield",
        "debt_to_equity",
        "current_ratio",
        "intrinsic_low",
        "intrinsic_high",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for rank, c in enumerate(candidates, 1):
            data = c.get("data")
            intrinsic = c.get("intrinsic_range", {})

            row = {
                "rank": rank,
                "ticker": c["ticker"],
                "company": data.info.name if data else "",
                "signal": c["signal"],
                "final_score": _safe_csv(c.get("final_score")),
                "margin_of_safety": _safe_csv(c.get("margin_of_safety")),
                "quality_score": _safe_csv(c.get("quality_score")),
                "cyclicality": c.get("cyclicality", ""),
                "trap_flags": "; ".join(c.get("trap_flags", [])),
                "sector": data.info.sector if data else "",
                "industry": data.info.industry if data else "",
                "market_cap": _safe_csv(data.price.market_cap if data else None),
                "price": _safe_csv(data.price.current_price if data else None),
                "pe_ratio": _safe_csv(data.metrics.pe_ratio if data else None),
                "pb_ratio": _safe_csv(data.metrics.pb_ratio if data else None),
                "roe": _safe_csv(data.metrics.roe if data else None),
                "roic": _safe_csv(data.metrics.roic if data else None),
                "gross_margin": _safe_csv(data.metrics.gross_margin if data else None),
                "operating_margin": _safe_csv(data.metrics.operating_margin if data else None),
                "fcf_yield": _safe_csv(data.metrics.fcf_yield if data else None),
                "debt_to_equity": _safe_csv(data.metrics.debt_to_equity if data else None),
                "current_ratio": _safe_csv(data.metrics.current_ratio if data else None),
                "intrinsic_low": _safe_csv(min(intrinsic.values()) if intrinsic else None),
                "intrinsic_high": _safe_csv(max(intrinsic.values()) if intrinsic else None),
            }
            writer.writerow(row)

    logger.debug(f"Candidates CSV saved: {output_path} ({len(candidates)} rows)")
    return output_path


def export_rejected_csv(
    rejected: list[dict[str, Any]],
    output_path: Path,
) -> Path:
    """
    Export rejected tickers to CSV with rejection reasons.

    Args:
        rejected: List of rejected result dicts from pipeline.
        output_path: Path for the CSV file.

    Returns:
        Path to saved CSV.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "ticker",
        "company",
        "sector",
        "reject_reasons",
        "pe_ratio",
        "debt_to_equity",
        "current_ratio",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for r in rejected:
            data = r.get("data")
            metrics = r.get("metrics", {})

            row = {
                "ticker": r["ticker"],
                "company": data.info.name if data else "",
                "sector": data.info.sector if data else "",
                "reject_reasons": "; ".join(r.get("reject_reasons", [])),
                "pe_ratio": _safe_csv(
                    data.metrics.pe_ratio if data else metrics.get("pe_ratio")
                ),
                "debt_to_equity": _safe_csv(
                    data.metrics.debt_to_equity if data else metrics.get("debt_to_equity")
                ),
                "current_ratio": _safe_csv(
                    data.metrics.current_ratio if data else metrics.get("current_ratio")
                ),
            }
            writer.writerow(row)

    logger.debug(f"Rejected CSV saved: {output_path} ({len(rejected)} rows)")
    return output_path


def _safe_csv(v: Any) -> str:
    """Convert a value to a CSV-safe string."""
    if v is None:
        return ""
    if isinstance(v, float):
        if pd.isna(v) or v != v:
            return ""
        return f"{v:.4f}"
    return str(v)
