"""
Report generation package (Markdown + JSON + CSV exports).

Usage:
    from src.reports import generate_all_reports
    generate_all_reports(pipeline_results, run_mgr)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from src.reports.csv_export import export_candidates_csv, export_rejected_csv
from src.reports.json_report import save_summary_json, save_ticker_json
from src.reports.markdown_report import save_ticker_markdown
from src.run_manager import RunManager


def generate_all_reports(
    results: dict[str, Any],
    run_mgr: RunManager,
) -> dict[str, list[Path]]:
    """
    Generate all reports and exports for a pipeline run.

    Creates:
    - Per-ticker Markdown + JSON reports (for candidates)
    - Summary JSON
    - Candidates CSV
    - Rejected CSV

    Args:
        results: Full pipeline results dict.
        run_mgr: Run folder manager.

    Returns:
        Dict keyed by type with lists of generated file paths.
    """
    generated: dict[str, list[Path]] = {
        "ticker_reports": [],
        "exports": [],
    }

    # Per-ticker reports (candidates get full reports)
    for candidate in results.get("candidates", []):
        ticker = candidate["ticker"]
        report_dir = run_mgr.ticker_report_dir(ticker)

        try:
            md_path = save_ticker_markdown(candidate, report_dir)
            json_path = save_ticker_json(candidate, report_dir)
            generated["ticker_reports"].append(md_path)
            generated["ticker_reports"].append(json_path)
        except Exception as e:
            logger.error(f"Failed to generate report for {ticker}: {e}")

    # Summary JSON
    try:
        summary_path = save_summary_json(
            results,
            run_mgr.exports_dir / "summary.json",
        )
        generated["exports"].append(summary_path)
    except Exception as e:
        logger.error(f"Failed to generate summary JSON: {e}")

    # CSV exports
    try:
        cand_csv = export_candidates_csv(
            results.get("candidates", []),
            run_mgr.exports_dir / "candidates.csv",
        )
        generated["exports"].append(cand_csv)
    except Exception as e:
        logger.error(f"Failed to export candidates CSV: {e}")

    try:
        rej_csv = export_rejected_csv(
            results.get("rejected", []),
            run_mgr.exports_dir / "rejected.csv",
        )
        generated["exports"].append(rej_csv)
    except Exception as e:
        logger.error(f"Failed to export rejected CSV: {e}")

    total = len(generated["ticker_reports"]) + len(generated["exports"])
    logger.info(f"Reports generated: {total} files")

    return generated

