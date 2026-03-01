"""
yfinance-based data provider implementation.

Fetches financial data from Yahoo Finance via the yfinance library.
Includes caching and rate limiting.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

from src.providers.base import (
    CompanyInfo,
    DataProvider,
    DerivedMetrics,
    FinancialStatements,
    PriceData,
    TickerData,
)
from src.providers.cache import FileCache
from src.providers.rate_limiter import RateLimiter, retry_with_backoff


def _safe_get(d: dict, *keys, default=None):
    """Safely navigate nested dicts."""
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, default)
        else:
            return default
    return d


def _to_float(val, default: float | None = None) -> float | None:
    """Convert a value to float, returning default on failure."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class YFinanceProvider(DataProvider):
    """
    Data provider using yfinance library.

    Caches responses to avoid redundant API calls.
    Rate-limits to be polite to Yahoo's servers.
    """

    def __init__(
        self,
        cache_ttl_hours: float = 24,
        rate_limit_per_second: float = 2.0,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
    ):
        self.cache = FileCache(cache_dir=".cache/yfinance", ttl_hours=cache_ttl_hours)
        self.rate_limiter = RateLimiter(calls_per_second=rate_limit_per_second)
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

    def _fetch_ticker(self, ticker: str) -> yf.Ticker:
        """Create a yfinance Ticker object with rate limiting."""
        self.rate_limiter.wait()
        return yf.Ticker(ticker)

    @retry_with_backoff(max_retries=3, backoff_factor=2.0)
    def _get_info_raw(self, ticker: str) -> dict:
        """Fetch raw info dict from yfinance with retry."""
        cached = self.cache.get("info", ticker)
        if cached is not None:
            return cached

        t = self._fetch_ticker(ticker)
        info = t.info or {}
        if info:
            self.cache.set("info", ticker, info)
        return info

    def get_company_info(self, ticker: str) -> CompanyInfo | None:
        """Fetch basic company info."""
        try:
            info = self._get_info_raw(ticker)
            if not info or info.get("quoteType") not in ("EQUITY", None):
                return None

            return CompanyInfo(
                ticker=ticker,
                name=info.get("longName", info.get("shortName", "")),
                sector=info.get("sector", ""),
                industry=info.get("industry", ""),
                market_cap=_to_float(info.get("marketCap"), 0.0) or 0.0,
                currency=info.get("currency", "USD"),
                exchange=info.get("exchange", ""),
                country=info.get("country", ""),
            )
        except Exception as e:
            logger.error(f"Failed to get company info for {ticker}: {e}")
            return None

    def get_price_data(self, ticker: str) -> PriceData | None:
        """Fetch current price and share data."""
        try:
            info = self._get_info_raw(ticker)
            if not info:
                return None

            return PriceData(
                ticker=ticker,
                current_price=_to_float(
                    info.get("currentPrice", info.get("regularMarketPrice")), 0.0
                ) or 0.0,
                shares_outstanding=int(info.get("sharesOutstanding", 0) or 0),
                market_cap=_to_float(info.get("marketCap"), 0.0) or 0.0,
            )
        except Exception as e:
            logger.error(f"Failed to get price data for {ticker}: {e}")
            return None

    @retry_with_backoff(max_retries=3, backoff_factor=2.0)
    def get_financial_statements(
        self, ticker: str, years: int = 10
    ) -> FinancialStatements | None:
        """Fetch multi-year financial statements."""
        try:
            # Check cache for the full bundle
            cache_key = f"{ticker}_statements_{years}y"
            cached = self.cache.get("statements", cache_key)
            if cached is not None:
                return self._deserialize_statements(ticker, cached)

            t = self._fetch_ticker(ticker)

            # Fetch annual data
            inc = t.financials  # income statement
            bal = t.balance_sheet
            cf = t.cashflow

            if inc is None or inc.empty:
                logger.warning(f"No income statement data for {ticker}")
                return None

            income_df = self._parse_income_statement(inc)
            balance_df = self._parse_balance_sheet(bal) if bal is not None else pd.DataFrame()
            cashflow_df = self._parse_cashflow(cf) if cf is not None else pd.DataFrame()

            # Also fetch shares outstanding history from income stmt
            if bal is not None and not bal.empty:
                balance_df = self._enrich_balance_with_shares(balance_df, t)

            result = FinancialStatements(
                ticker=ticker,
                income=income_df,
                balance=balance_df,
                cashflow=cashflow_df,
            )

            # Cache it
            self.cache.set("statements", cache_key, self._serialize_statements(result))

            return result

        except Exception as e:
            logger.error(f"Failed to get financial statements for {ticker}: {e}")
            return None

    def _parse_income_statement(self, df: pd.DataFrame) -> pd.DataFrame:
        """Parse yfinance income statement into our standard format."""
        # yfinance returns columns as dates, rows as items
        # We want rows as years, columns as metrics
        field_map = {
            "Total Revenue": "revenue",
            "Cost Of Revenue": "cost_of_revenue",
            "Gross Profit": "gross_profit",
            "Operating Income": "operating_income",
            "Net Income": "net_income",
            "Basic EPS": "eps",
            "Diluted EPS": "eps",
            "EBITDA": "ebitda",
            "Interest Expense": "interest_expense",
            "Tax Provision": "tax_expense",
        }

        records = {}
        for col in df.columns:
            year = col.year if hasattr(col, "year") else int(str(col)[:4])
            row_data = {}
            for yf_field, our_field in field_map.items():
                if yf_field in df.index:
                    val = _to_float(df.loc[yf_field, col])
                    if our_field not in row_data or val is not None:
                        row_data[our_field] = val
            if row_data:
                records[year] = row_data

        result = pd.DataFrame.from_dict(records, orient="index")
        result.index.name = "year"
        result.sort_index(inplace=True)
        return result

    def _parse_balance_sheet(self, df: pd.DataFrame) -> pd.DataFrame:
        """Parse yfinance balance sheet into our standard format."""
        field_map = {
            "Total Assets": "total_assets",
            "Total Liabilities Net Minority Interest": "total_liabilities",
            "Total Equity Gross Minority Interest": "total_equity",
            "Stockholders Equity": "total_equity",
            "Current Assets": "current_assets",
            "Current Liabilities": "current_liabilities",
            "Total Debt": "total_debt",
            "Cash And Cash Equivalents": "cash_and_equivalents",
            "Net Debt": "net_debt",
            "Ordinary Shares Number": "shares_outstanding",
        }

        records = {}
        for col in df.columns:
            year = col.year if hasattr(col, "year") else int(str(col)[:4])
            row_data = {}
            for yf_field, our_field in field_map.items():
                if yf_field in df.index:
                    val = _to_float(df.loc[yf_field, col])
                    if our_field not in row_data or val is not None:
                        row_data[our_field] = val
            if row_data:
                records[year] = row_data

        result = pd.DataFrame.from_dict(records, orient="index")
        result.index.name = "year"
        result.sort_index(inplace=True)

        # Compute derived fields
        if "total_equity" in result.columns and "shares_outstanding" in result.columns:
            mask = result["shares_outstanding"] > 0
            result.loc[mask, "book_value_per_share"] = (
                result.loc[mask, "total_equity"] / result.loc[mask, "shares_outstanding"]
            )

        # Compute invested capital: total_equity + total_debt - cash
        if all(c in result.columns for c in ["total_equity", "total_debt", "cash_and_equivalents"]):
            result["invested_capital"] = (
                result["total_equity"].fillna(0)
                + result["total_debt"].fillna(0)
                - result["cash_and_equivalents"].fillna(0)
            )

        return result

    def _parse_cashflow(self, df: pd.DataFrame) -> pd.DataFrame:
        """Parse yfinance cash flow statement into our standard format."""
        field_map = {
            "Operating Cash Flow": "operating_cashflow",
            "Capital Expenditure": "capex",
            "Free Cash Flow": "free_cash_flow",
            "Common Stock Dividend Paid": "dividends_paid",
            "Repurchase Of Capital Stock": "share_repurchases",
        }

        records = {}
        for col in df.columns:
            year = col.year if hasattr(col, "year") else int(str(col)[:4])
            row_data = {}
            for yf_field, our_field in field_map.items():
                if yf_field in df.index:
                    val = _to_float(df.loc[yf_field, col])
                    row_data[our_field] = val
            # Compute FCF if not directly available
            if "free_cash_flow" not in row_data or row_data.get("free_cash_flow") is None:
                ocf = row_data.get("operating_cashflow")
                capex = row_data.get("capex")
                if ocf is not None and capex is not None:
                    row_data["free_cash_flow"] = ocf + capex  # capex is negative
            if row_data:
                records[year] = row_data

        result = pd.DataFrame.from_dict(records, orient="index")
        result.index.name = "year"
        result.sort_index(inplace=True)
        return result

    def _enrich_balance_with_shares(
        self, balance_df: pd.DataFrame, t: yf.Ticker
    ) -> pd.DataFrame:
        """Try to fill shares_outstanding from other sources if missing."""
        if "shares_outstanding" in balance_df.columns and balance_df["shares_outstanding"].notna().any():
            return balance_df
        # Fallback: use current shares for all years (imperfect but functional)
        info = t.info or {}
        shares = info.get("sharesOutstanding")
        if shares and "shares_outstanding" not in balance_df.columns:
            balance_df["shares_outstanding"] = float(shares)
        return balance_df

    def get_derived_metrics(self, ticker: str) -> DerivedMetrics | None:
        """Fetch pre-computed ratios from yfinance info."""
        try:
            info = self._get_info_raw(ticker)
            if not info:
                return None

            return DerivedMetrics(
                ticker=ticker,
                pe_ratio=_to_float(info.get("trailingPE")),
                forward_pe=_to_float(info.get("forwardPE")),
                pb_ratio=_to_float(info.get("priceToBook")),
                ev_ebitda=_to_float(info.get("enterpriseToEbitda")),
                roe=_to_float(info.get("returnOnEquity")),
                gross_margin=_to_float(info.get("grossMargins")),
                operating_margin=_to_float(info.get("operatingMargins")),
                net_margin=_to_float(info.get("profitMargins")),
                dividend_yield=_to_float(info.get("dividendYield")),
                payout_ratio=_to_float(info.get("payoutRatio")),
                debt_to_equity=_to_float(info.get("debtToEquity")),
                current_ratio=_to_float(info.get("currentRatio")),
                beta=_to_float(info.get("beta")),
                # ROIC and interest_coverage computed in pipeline from raw data
                roic=None,
                interest_coverage=None,
                fcf_yield=None,
            )
        except Exception as e:
            logger.error(f"Failed to get derived metrics for {ticker}: {e}")
            return None

    def get_ticker_data(self, ticker: str, years: int = 10) -> TickerData | None:
        """
        Fetch all data for a ticker efficiently.

        Uses single yfinance Ticker object to reduce API calls.
        """
        try:
            info_data = self.get_company_info(ticker)
            if info_data is None:
                logger.warning(f"Could not fetch company info for {ticker}, skipping")
                return None

            price_data = self.get_price_data(ticker)
            if price_data is None:
                logger.warning(f"Could not fetch price data for {ticker}, skipping")
                return None

            financials = self.get_financial_statements(ticker, years=years)
            if financials is None:
                logger.warning(f"Could not fetch financials for {ticker}, skipping")
                return None

            metrics = self.get_derived_metrics(ticker)
            if metrics is None:
                metrics = DerivedMetrics(ticker=ticker)

            return TickerData(
                info=info_data,
                price=price_data,
                financials=financials,
                metrics=metrics,
            )
        except Exception as e:
            logger.error(f"Failed to get complete data for {ticker}: {e}")
            return None

    def get_universe_tickers(self, min_market_cap: float = 1e9) -> list[str]:
        """
        Get list of US equity tickers with market cap above threshold.

        Uses a curated approach: fetch S&P 500 + S&P 400 MidCap components
        from Wikipedia/yfinance, then filter by market cap.
        """
        tickers: set[str] = set()

        try:
            # S&P 500 components
            logger.info("Fetching S&P 500 components...")
            sp500 = self._get_sp500_tickers()
            tickers.update(sp500)
            logger.info(f"S&P 500: {len(sp500)} tickers")
        except Exception as e:
            logger.warning(f"Failed to fetch S&P 500 list: {e}")

        try:
            # S&P 400 MidCap
            logger.info("Fetching S&P 400 MidCap components...")
            sp400 = self._get_sp400_tickers()
            tickers.update(sp400)
            logger.info(f"S&P 400: {len(sp400)} tickers")
        except Exception as e:
            logger.warning(f"Failed to fetch S&P 400 list: {e}")

        result = sorted(tickers)
        logger.info(f"Universe: {len(result)} unique tickers before market cap filter")
        return result

    def _get_sp500_tickers(self) -> list[str]:
        """Fetch S&P 500 ticker list from Wikipedia."""
        cached = self.cache.get("universe", "sp500_tickers")
        if cached is not None:
            return cached

        try:
            import io
            import requests

            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            tables = pd.read_html(io.StringIO(resp.text))
            if tables:
                df = tables[0]
                tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
                self.cache.set("universe", "sp500_tickers", tickers)
                return tickers
        except Exception as e:
            logger.warning(f"Wikipedia S&P 500 fetch failed: {e}")

        return []

    def _get_sp400_tickers(self) -> list[str]:
        """Fetch S&P 400 MidCap ticker list from Wikipedia."""
        cached = self.cache.get("universe", "sp400_tickers")
        if cached is not None:
            return cached

        try:
            import io
            import requests

            url = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            tables = pd.read_html(io.StringIO(resp.text))
            if tables:
                df = tables[0]
                # Column name may vary
                symbol_col = None
                for col in df.columns:
                    if "symbol" in str(col).lower() or "ticker" in str(col).lower():
                        symbol_col = col
                        break
                if symbol_col is None and len(df.columns) > 0:
                    symbol_col = df.columns[0]

                if symbol_col:
                    tickers = df[symbol_col].str.replace(".", "-", regex=False).tolist()
                    self.cache.set("universe", "sp400_tickers", tickers)
                    return tickers
        except Exception as e:
            logger.warning(f"Wikipedia S&P 400 fetch failed: {e}")

        return []

    def _serialize_statements(self, stmts: FinancialStatements) -> dict:
        """Serialize FinancialStatements to a JSON-safe dict."""
        return {
            "ticker": stmts.ticker,
            "income": stmts.income.to_dict() if not stmts.income.empty else {},
            "balance": stmts.balance.to_dict() if not stmts.balance.empty else {},
            "cashflow": stmts.cashflow.to_dict() if not stmts.cashflow.empty else {},
        }

    def _deserialize_statements(self, ticker: str, data: dict) -> FinancialStatements:
        """Deserialize cached dict back to FinancialStatements."""
        def _df_from_dict(d: dict) -> pd.DataFrame:
            if not d:
                return pd.DataFrame()
            df = pd.DataFrame.from_dict(d)
            df.index = df.index.astype(int)
            df.index.name = "year"
            df.sort_index(inplace=True)
            return df

        return FinancialStatements(
            ticker=ticker,
            income=_df_from_dict(data.get("income", {})),
            balance=_df_from_dict(data.get("balance", {})),
            cashflow=_df_from_dict(data.get("cashflow", {})),
        )
