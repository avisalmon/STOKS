"""
CLI entrypoint for STOKS value investing scanner.

Usage:
    python -m src.main [OPTIONS]

Examples:
    python -m src.main                          # Full scan with defaults
    python -m src.main --ticker AAPL            # Single ticker analysis
    python -m src.main --sector-mode full       # Include financials/REITs
    python -m src.main --config my_config.yaml  # Custom config
    python -m src.main --verbose                # Debug output
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from loguru import logger

from src.config import load_config
from src.log_setup import setup_logging
from src.providers.yfinance_provider import YFinanceProvider
from src.run_manager import RunManager
from src.universe import UniverseBuilder


@click.command()
@click.option(
    "--config",
    "config_path",
    default="config.yaml",
    type=click.Path(exists=False),
    help="Path to config.yaml (default: config.yaml)",
)
@click.option(
    "--ticker", "-t",
    multiple=True,
    help="Analyze specific ticker(s). Repeat for multiple: -t AAPL -t MSFT",
)
@click.option(
    "--sector-mode",
    default=None,
    type=click.Choice(["simple", "full"]),
    help="Override sector mode from config.",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose (DEBUG) console output.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Build universe and show ticker count without running analysis.",
)
def main(
    config_path: str,
    ticker: tuple[str, ...],
    sector_mode: str | None,
    verbose: bool,
    dry_run: bool,
) -> None:
    """STOKS — Value Investing Scanner & Analysis Pipeline."""

    # Step 1: Load configuration
    cfg_path = Path(config_path) if Path(config_path).exists() else None
    try:
        cfg = load_config(cfg_path)
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)

    # Override sector mode if specified
    if sector_mode:
        cfg.universe.sector_mode = sector_mode

    # Step 2: Initialize run manager
    run_mgr = RunManager(cfg).initialize()

    # Step 3: Setup logging (file + console)
    setup_logging(log_dir=run_mgr.log_dir, verbose=verbose)
    logger.info("=" * 60)
    logger.info("STOKS Value Investing Scanner — Starting")
    logger.info(f"Run folder: {run_mgr.run_dir}")
    logger.info("=" * 60)

    # Step 4: Initialize data provider
    provider = YFinanceProvider(
        cache_ttl_hours=cfg.provider.cache_ttl_hours,
        rate_limit_per_second=cfg.provider.rate_limit_per_second,
        max_retries=cfg.provider.max_retries,
        retry_backoff=cfg.provider.retry_backoff,
    )

    # Step 5: Build universe or use specific tickers
    if ticker:
        tickers = [t.upper() for t in ticker]
        logger.info(f"Ticker mode: {', '.join(tickers)}")
    else:
        universe_builder = UniverseBuilder(cfg, provider)
        tickers = universe_builder.build()

    logger.info(f"Scanning {len(tickers)} ticker(s)")

    if dry_run:
        logger.info("DRY RUN — listing tickers only:")
        for t in tickers:
            click.echo(t)
        logger.info(f"Total: {len(tickers)} tickers")
        return

    # Step 6: Run pipeline
    from src.pipeline.orchestrator import run_pipeline

    results = run_pipeline(
        tickers=tickers,
        config=cfg,
        provider=provider,
        run_mgr=run_mgr,
    )

    # Step 7: Generate reports & exports
    from src.reports import generate_all_reports

    report_files = generate_all_reports(results, run_mgr)

    # Step 8: Generate static site
    from src.site_generator import generate_site

    generate_site(results, run_mgr)

    logger.info("=" * 60)
    n_candidates = len(results.get("candidates", []))
    logger.info(f"Scan complete. {n_candidates} candidates found.")
    logger.info(f"Results: {run_mgr.run_dir}")
    if n_candidates > 0:
        logger.info("Top candidates:")
        for c in results["candidates"][:10]:
            logger.info(
                f"  {c['signal']:20s} {c['ticker']:6s} "
                f"Score={c['final_score']:.0f}  "
                f"MOS={c.get('margin_of_safety', 0):.1%}"
            )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
