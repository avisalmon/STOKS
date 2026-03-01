"""
Abstract data provider interface.

All data providers must implement this ABC. This allows swapping
yfinance for FMP, Alpha Vantage, etc. without touching pipeline code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Data models returned by providers
# ---------------------------------------------------------------------------
@dataclass
class CompanyInfo:
    """Basic company identification and classification."""

    ticker: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: float = 0.0
    currency: str = "USD"
    exchange: str = ""
    country: str = ""


@dataclass
class PriceData:
    """Current price and share data."""

    ticker: str
    current_price: float = 0.0
    shares_outstanding: int = 0
    market_cap: float = 0.0


@dataclass
class FinancialStatements:
    """
    Multi-year financial data for a ticker.

    Each DataFrame is indexed by year (int) with metrics as columns.
    All values in USD.
    """

    ticker: str

    # Income statement fields per year
    income: pd.DataFrame = field(default_factory=pd.DataFrame)
    # Expected columns: revenue, cost_of_revenue, gross_profit, operating_income,
    #                    net_income, eps, ebitda, interest_expense, tax_expense,
    #                    shares_outstanding

    # Balance sheet fields per year
    balance: pd.DataFrame = field(default_factory=pd.DataFrame)
    # Expected columns: total_assets, total_liabilities, total_equity,
    #                    current_assets, current_liabilities, total_debt,
    #                    cash_and_equivalents, net_debt, book_value_per_share,
    #                    invested_capital

    # Cash flow fields per year
    cashflow: pd.DataFrame = field(default_factory=pd.DataFrame)
    # Expected columns: operating_cashflow, capex, free_cash_flow,
    #                    dividends_paid, share_repurchases


@dataclass
class DerivedMetrics:
    """
    Pre-computed or provider-supplied ratios.

    Pipeline can also compute these from raw statements.
    """

    ticker: str
    pe_ratio: float | None = None
    forward_pe: float | None = None
    pb_ratio: float | None = None
    ev_ebitda: float | None = None
    roe: float | None = None
    roic: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    fcf_yield: float | None = None
    dividend_yield: float | None = None
    payout_ratio: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    interest_coverage: float | None = None
    beta: float | None = None


@dataclass
class TickerData:
    """Complete data bundle for a single ticker."""

    info: CompanyInfo
    price: PriceData
    financials: FinancialStatements
    metrics: DerivedMetrics

    @property
    def ticker(self) -> str:
        return self.info.ticker


# ---------------------------------------------------------------------------
# Abstract provider
# ---------------------------------------------------------------------------
class DataProvider(ABC):
    """
    Abstract interface for financial data providers.

    Implementations must handle:
    - Rate limiting
    - Caching (via the cache layer)
    - Error handling (return None or raise with clear messages)
    """

    @abstractmethod
    def get_company_info(self, ticker: str) -> CompanyInfo | None:
        """Fetch basic company info and classification."""
        ...

    @abstractmethod
    def get_price_data(self, ticker: str) -> PriceData | None:
        """Fetch current price and share data."""
        ...

    @abstractmethod
    def get_financial_statements(self, ticker: str, years: int = 10) -> FinancialStatements | None:
        """
        Fetch multi-year financial statements.

        Args:
            ticker: Stock ticker symbol.
            years: Number of years of history to fetch.

        Returns:
            FinancialStatements with income, balance, cashflow DataFrames.
        """
        ...

    @abstractmethod
    def get_derived_metrics(self, ticker: str) -> DerivedMetrics | None:
        """Fetch pre-computed ratios/metrics from the provider."""
        ...

    def get_ticker_data(self, ticker: str, years: int = 10) -> TickerData | None:
        """
        Convenience: fetch all data for a ticker in one call.

        Default implementation calls individual methods. Providers can
        override for efficiency if their API supports batch fetching.
        """
        info = self.get_company_info(ticker)
        if info is None:
            return None

        price = self.get_price_data(ticker)
        if price is None:
            return None

        financials = self.get_financial_statements(ticker, years=years)
        if financials is None:
            return None

        metrics = self.get_derived_metrics(ticker)
        if metrics is None:
            metrics = DerivedMetrics(ticker=ticker)

        return TickerData(
            info=info,
            price=price,
            financials=financials,
            metrics=metrics,
        )

    @abstractmethod
    def get_universe_tickers(self, min_market_cap: float = 1e9) -> list[str]:
        """
        Get list of ticker symbols matching universe criteria.

        Args:
            min_market_cap: Minimum market cap filter.

        Returns:
            List of ticker symbols.
        """
        ...
