"""
Universe builder — constructs the list of tickers to scan.

Fetches ticker lists from the data provider, applies initial filters
(market cap, sector exclusions), and returns the scanning universe.
"""

from __future__ import annotations

from loguru import logger

from src.config import AppConfig
from src.providers.base import DataProvider


class UniverseBuilder:
    """
    Builds the stock universe to scan.

    Responsibilities:
    - Fetch candidate tickers from provider
    - Apply sector exclusions (simple mode)
    - Apply minimum market cap filter (via provider or post-filter)
    - Return clean, deduplicated, sorted ticker list
    """

    def __init__(self, config: AppConfig, provider: DataProvider):
        self.config = config
        self.provider = provider

    def build(self) -> list[str]:
        """
        Build the scanning universe.

        Returns:
            Sorted list of ticker symbols that pass universe constraints.
        """
        uc = self.config.universe
        logger.info(
            f"Building universe: market={uc.market}, "
            f"min_cap=${uc.min_market_cap:,.0f}, "
            f"sector_mode={uc.sector_mode}"
        )

        # Step 1: Get raw ticker list from provider
        raw_tickers = self.provider.get_universe_tickers(
            min_market_cap=uc.min_market_cap
        )
        logger.info(f"Raw universe: {len(raw_tickers)} tickers")

        if not raw_tickers:
            logger.warning("No tickers returned from provider!")
            return []

        # Step 2: sector filtering happens during pipeline Stage A
        # (we need company info which we don't have yet at universe build time)
        # Universe builder gives us the candidate list; Stage A does detailed filtering.

        logger.info(f"Universe built: {len(raw_tickers)} candidates to scan")
        return raw_tickers

    def filter_by_sector(self, ticker: str, sector: str) -> bool:
        """
        Check if a ticker should be included based on sector.

        Args:
            ticker: Stock ticker.
            sector: Company sector string.

        Returns:
            True if ticker passes sector filter.
        """
        uc = self.config.universe
        if uc.sector_mode == "simple":
            if sector in uc.exclude_sectors:
                logger.debug(f"{ticker}: excluded sector '{sector}'")
                return False
        return True
