"""
Pipeline orchestrator — runs all screening stages in sequence.

This is the main engine that chains:
  Stage A (Hard Filters) → Stage B (Quality) → Stage C (Cyclicality)
  → Stage D (Valuation) → Stage E (Trap Detection) → Stage F (Scoring)

Then generates reports and the static site.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.config import AppConfig
from src.providers.base import DataProvider, TickerData
from src.run_manager import RunManager
from src.universe import UniverseBuilder


def run_pipeline(
    tickers: list[str],
    config: AppConfig,
    provider: DataProvider,
    run_mgr: RunManager,
) -> dict[str, Any]:
    """
    Execute the full screening pipeline.

    Args:
        tickers: List of ticker symbols to analyze.
        config: Application configuration.
        provider: Data provider instance.
        run_mgr: Run folder manager.

    Returns:
        Dict with 'candidates', 'rejected', 'errors' lists.
    """
    results: dict[str, Any] = {
        "candidates": [],
        "rejected": [],
        "errors": [],
        "ticker_data": {},
    }

    universe_builder = UniverseBuilder(config, provider)
    total = len(tickers)

    logger.info(f"Pipeline starting: {total} tickers to process")

    for i, ticker in enumerate(tickers, 1):
        logger.info(f"[{i}/{total}] Processing {ticker}...")

        try:
            # Fetch all data
            data = provider.get_ticker_data(ticker)
            if data is None:
                logger.warning(f"[{i}/{total}] {ticker}: No data available, skipping")
                results["errors"].append({
                    "ticker": ticker,
                    "reason": "MISSING_DATA:all",
                })
                continue

            # Check sector filter (universe-level)
            if not universe_builder.filter_by_sector(ticker, data.info.sector):
                results["rejected"].append({
                    "ticker": ticker,
                    "signal": "REJECT",
                    "reject_reasons": [f"Excluded sector: {data.info.sector}"],
                })
                continue

            # Check market cap
            if data.price.market_cap < config.universe.min_market_cap:
                results["rejected"].append({
                    "ticker": ticker,
                    "signal": "REJECT",
                    "reject_reasons": [
                        f"Market cap ${data.price.market_cap:,.0f} "
                        f"< ${config.universe.min_market_cap:,.0f}"
                    ],
                })
                continue

            # Stage A: Hard Filters
            stage_a = _run_stage_a(data, config)
            if not stage_a["passed"]:
                results["rejected"].append({
                    "ticker": ticker,
                    "signal": "REJECT",
                    "reject_reasons": stage_a["reasons"],
                    "metrics": stage_a.get("metrics", {}),
                })
                logger.info(f"  {ticker}: REJECTED (Stage A) — {stage_a['reasons']}")
                continue

            # Stage B: Quality Filter
            stage_b = _run_stage_b(data, config)
            quality_score = stage_b["quality_score"]

            # Stage C: Cyclicality
            stage_c = _run_stage_c(data, config)

            # Stage D: Valuation & Margin of Safety
            stage_d = _run_stage_d(data, config, stage_c)

            # Stage E: Value Trap Detection
            stage_e = _run_stage_e(data, config)

            # Stage F: Final Scoring & Signal
            stage_f = _run_stage_f(
                data, config, stage_a, stage_b, stage_c, stage_d, stage_e
            )

            ticker_result = {
                "ticker": ticker,
                "signal": stage_f["signal"],
                "final_score": stage_f["final_score"],
                "margin_of_safety": stage_d.get("margin_of_safety", 0),
                "quality_score": quality_score,
                "cyclicality": stage_c.get("cyclicality_flag", "UNKNOWN"),
                "trap_flags": stage_e.get("trap_flags", []),
                "intrinsic_range": stage_d.get("intrinsic_range", {}),
                "stages": {
                    "a": stage_a,
                    "b": stage_b,
                    "c": stage_c,
                    "d": stage_d,
                    "e": stage_e,
                    "f": stage_f,
                },
                "data": data,
            }

            if stage_f["signal"] == "REJECT":
                results["rejected"].append(ticker_result)
            else:
                results["candidates"].append(ticker_result)

            logger.info(
                f"  {ticker}: {stage_f['signal']} "
                f"(score={stage_f['final_score']:.0f}, "
                f"MOS={stage_d.get('margin_of_safety', 0):.1%})"
            )

        except Exception as e:
            logger.error(f"[{i}/{total}] {ticker}: Pipeline error — {e}")
            results["errors"].append({
                "ticker": ticker,
                "reason": f"PIPELINE_ERROR: {str(e)}",
            })

    # Sort candidates by signal strength then score
    signal_order = {"STRONG_BUY_SIGNAL": 0, "BUY_SIGNAL": 1, "WATCH": 2}
    results["candidates"].sort(
        key=lambda x: (
            signal_order.get(x["signal"], 99),
            -x["final_score"],
            -x.get("margin_of_safety", 0),
        )
    )

    logger.info(
        f"Pipeline complete: "
        f"{len(results['candidates'])} candidates, "
        f"{len(results['rejected'])} rejected, "
        f"{len(results['errors'])} errors"
    )

    return results


# ===========================================================================
# Stage implementations
# ===========================================================================

def _run_stage_a(data: TickerData, config: AppConfig) -> dict[str, Any]:
    """Stage A: Hard Filters (Graham)."""
    hf = config.hard_filters
    reasons: list[str] = []
    metrics: dict[str, Any] = {}

    # P/E check
    pe = data.metrics.pe_ratio
    metrics["pe_ratio"] = pe
    if pe is None or pe <= 0:
        if not config.universe.allow_turnarounds:
            reasons.append(f"P/E invalid or negative: {pe}")
    elif pe > hf.pe_max:
        reasons.append(f"P/E {pe:.1f} > {hf.pe_max}")

    # EPS positive years check
    income = data.financials.income
    if "eps" in income.columns and len(income) > 0:
        eps_series = income["eps"].dropna()
        lookback = eps_series.tail(hf.eps_lookback_years)
        positive_years = int((lookback > 0).sum())
        available_years = len(lookback)
        metrics["eps_positive_years"] = positive_years
        metrics["eps_lookback"] = available_years

        # Adaptive threshold: if data has fewer years than config requires,
        # scale the requirement proportionally (e.g. need 5/7 → need 3/4)
        required = hf.eps_positive_min_years
        if available_years < hf.eps_lookback_years:
            ratio = hf.eps_positive_min_years / hf.eps_lookback_years
            required = max(1, int(round(ratio * available_years)))

        if positive_years < required:
            reasons.append(
                f"EPS positive {positive_years}/{available_years} years "
                f"(need {required})"
            )
    else:
        reasons.append("MISSING_DATA:eps")

    # FCF positive years check
    cashflow = data.financials.cashflow
    if "free_cash_flow" in cashflow.columns and len(cashflow) > 0:
        fcf_series = cashflow["free_cash_flow"].dropna()
        lookback_fcf = fcf_series.tail(hf.fcf_lookback_years)
        fcf_positive = int((lookback_fcf > 0).sum())
        fcf_available = len(lookback_fcf)
        metrics["fcf_positive_years"] = fcf_positive
        metrics["fcf_lookback"] = fcf_available

        # Adaptive threshold for limited data
        fcf_required = hf.fcf_positive_min_years
        if fcf_available < hf.fcf_lookback_years:
            ratio = hf.fcf_positive_min_years / hf.fcf_lookback_years
            fcf_required = max(1, int(round(ratio * fcf_available)))

        if fcf_positive < fcf_required:
            reasons.append(
                f"FCF positive {fcf_positive}/{fcf_available} years "
                f"(need {fcf_required})"
            )
    else:
        reasons.append("MISSING_DATA:free_cash_flow")

    # Debt/Equity check
    de = data.metrics.debt_to_equity
    if de is not None:
        # yfinance returns D/E as percentage (e.g., 150 = 1.5x)
        de_ratio = de / 100 if de > 10 else de
        metrics["debt_to_equity"] = de_ratio
        if de_ratio > hf.debt_to_equity_max:
            reasons.append(f"D/E {de_ratio:.2f} > {hf.debt_to_equity_max}")
    else:
        # Try computing from balance sheet
        bal = data.financials.balance
        if not bal.empty and "total_debt" in bal.columns and "total_equity" in bal.columns:
            latest = bal.iloc[-1]
            equity = latest.get("total_equity", 0)
            debt = latest.get("total_debt", 0)
            if equity and equity > 0:
                de_ratio = debt / equity
                metrics["debt_to_equity"] = de_ratio
                if de_ratio > hf.debt_to_equity_max:
                    reasons.append(f"D/E {de_ratio:.2f} > {hf.debt_to_equity_max}")
            else:
                reasons.append("MISSING_DATA:equity_for_de_ratio")
        else:
            reasons.append("MISSING_DATA:debt_to_equity")

    # Current ratio check
    cr = data.metrics.current_ratio
    if cr is not None:
        metrics["current_ratio"] = cr
        if cr < hf.current_ratio_min:
            reasons.append(f"Current ratio {cr:.2f} < {hf.current_ratio_min}")
    else:
        # Try computing from balance sheet
        bal = data.financials.balance
        if not bal.empty and "current_assets" in bal.columns and "current_liabilities" in bal.columns:
            latest = bal.iloc[-1]
            ca = latest.get("current_assets", 0)
            cl = latest.get("current_liabilities", 0)
            if cl and cl > 0:
                cr_calc = ca / cl
                metrics["current_ratio"] = cr_calc
                if cr_calc < hf.current_ratio_min:
                    reasons.append(f"Current ratio {cr_calc:.2f} < {hf.current_ratio_min}")
        else:
            reasons.append("MISSING_DATA:current_ratio")

    # Dilution check (share count CAGR over 5 years)
    bal = data.financials.balance
    if "shares_outstanding" in bal.columns and len(bal) >= 2:
        shares = bal["shares_outstanding"].dropna()
        if len(shares) >= 2:
            first = shares.iloc[0]
            last = shares.iloc[-1]
            n_years = len(shares) - 1
            if first > 0 and n_years > 0:
                dilution_cagr = (last / first) ** (1 / n_years) - 1
                metrics["dilution_cagr"] = dilution_cagr
                if dilution_cagr > hf.dilution_cagr_max:
                    reasons.append(
                        f"Dilution CAGR {dilution_cagr:.1%} > {hf.dilution_cagr_max:.1%}"
                    )

    return {
        "passed": len(reasons) == 0,
        "reasons": reasons,
        "metrics": metrics,
    }


def _run_stage_b(data: TickerData, config: AppConfig) -> dict[str, Any]:
    """Stage B: Quality Filter (Buffett)."""
    qc = config.quality
    sub_scores: dict[str, float] = {}
    warnings: list[str] = []

    # ROIC — compute from statements if not provided
    roic = data.metrics.roic
    if roic is None:
        income = data.financials.income
        balance = data.financials.balance
        if (
            not income.empty
            and not balance.empty
            and "net_income" in income.columns
            and "tax_expense" in income.columns
            and "interest_expense" in income.columns
            and "invested_capital" in balance.columns
        ):
            latest_inc = income.iloc[-1]
            latest_bal = balance.iloc[-1]
            nopat = (latest_inc.get("net_income", 0) or 0) + (latest_inc.get("interest_expense", 0) or 0)
            # Rough NOPAT: net_income + interest*(1-tax_rate)
            tax = latest_inc.get("tax_expense", 0) or 0
            pretax = (latest_inc.get("net_income", 0) or 0) + tax
            tax_rate = tax / pretax if pretax > 0 else 0.25
            nopat = ((latest_inc.get("operating_income", 0) or 0)) * (1 - tax_rate)
            ic = latest_bal.get("invested_capital", 0)
            if ic and ic > 0:
                roic = nopat / ic

    if roic is not None:
        if roic >= qc.roic_min:
            sub_scores["roic"] = min(100, (roic / qc.roic_min) * 70)
        else:
            sub_scores["roic"] = max(0, (roic / qc.roic_min) * 50)
    else:
        sub_scores["roic"] = 30  # Penalty for missing data

    # ROE
    roe = data.metrics.roe
    if roe is not None:
        if roe >= qc.roe_min:
            sub_scores["roe"] = min(100, (roe / qc.roe_min) * 70)
        else:
            sub_scores["roe"] = max(0, (roe / qc.roe_min) * 50)

        # Check if ROE is leverage-driven
        de = data.metrics.debt_to_equity
        if de and de > 200:  # yfinance gives percentage
            warnings.append("ROE may be leverage-driven (high D/E)")
    else:
        sub_scores["roe"] = 30

    # Gross margin stability
    income = data.financials.income
    if "gross_profit" in income.columns and "revenue" in income.columns:
        margins = (income["gross_profit"] / income["revenue"]).dropna()
        if len(margins) >= 3:
            margin_std = margins.std()
            if margin_std <= qc.gross_margin_max_stddev:
                sub_scores["margin_stability"] = 80
            else:
                sub_scores["margin_stability"] = max(20, 80 - (margin_std - qc.gross_margin_max_stddev) * 500)
        else:
            sub_scores["margin_stability"] = 40
    else:
        sub_scores["margin_stability"] = 30

    # Operating margin trend (not declining)
    if "operating_income" in income.columns and "revenue" in income.columns:
        op_margins = (income["operating_income"] / income["revenue"]).dropna()
        if len(op_margins) >= 3:
            # Simple trend: compare first half avg to second half avg
            mid = len(op_margins) // 2
            first_half = op_margins.iloc[:mid].mean()
            second_half = op_margins.iloc[mid:].mean()
            if second_half >= first_half * 0.9:  # Not declining by more than 10%
                sub_scores["op_margin_trend"] = 75
            else:
                sub_scores["op_margin_trend"] = 35
                warnings.append("Operating margin in structural decline")
        else:
            sub_scores["op_margin_trend"] = 40
    else:
        sub_scores["op_margin_trend"] = 30

    # Revenue trend
    if "revenue" in income.columns:
        revenue = income["revenue"].dropna()
        if len(revenue) >= 3:
            # Check if revenue is growing
            cagr_n = len(revenue) - 1
            if revenue.iloc[0] > 0 and cagr_n > 0:
                rev_cagr = (revenue.iloc[-1] / revenue.iloc[0]) ** (1 / cagr_n) - 1
                if rev_cagr > 0.02:
                    sub_scores["revenue_trend"] = 80
                elif rev_cagr > -0.02:
                    sub_scores["revenue_trend"] = 55
                else:
                    sub_scores["revenue_trend"] = 25
                    warnings.append(f"Revenue declining: {rev_cagr:.1%} CAGR")
            else:
                sub_scores["revenue_trend"] = 40
        else:
            sub_scores["revenue_trend"] = 40
    else:
        sub_scores["revenue_trend"] = 30

    # FCF margin
    cashflow = data.financials.cashflow
    if "free_cash_flow" in cashflow.columns and "revenue" in income.columns:
        latest_fcf = cashflow["free_cash_flow"].dropna()
        latest_rev = income["revenue"].dropna()
        if len(latest_fcf) > 0 and len(latest_rev) > 0:
            fcf_margin = latest_fcf.iloc[-1] / latest_rev.iloc[-1] if latest_rev.iloc[-1] > 0 else 0
            if fcf_margin > 0.10:
                sub_scores["fcf_margin"] = 85
            elif fcf_margin > 0.05:
                sub_scores["fcf_margin"] = 65
            elif fcf_margin > 0:
                sub_scores["fcf_margin"] = 45
            else:
                sub_scores["fcf_margin"] = 15
                warnings.append("Negative FCF margin")
        else:
            sub_scores["fcf_margin"] = 30
    else:
        sub_scores["fcf_margin"] = 30

    # Compute weighted quality score
    weights = {
        "roic": 0.25,
        "roe": 0.20,
        "margin_stability": 0.15,
        "op_margin_trend": 0.15,
        "revenue_trend": 0.15,
        "fcf_margin": 0.10,
    }
    quality_score = sum(
        sub_scores.get(k, 30) * w for k, w in weights.items()
    )

    return {
        "quality_score": round(quality_score, 1),
        "sub_scores": sub_scores,
        "warnings": warnings,
        "passed": quality_score >= qc.quality_score_min,
        "roic_computed": roic,
    }


def _run_stage_c(data: TickerData, config: AppConfig) -> dict[str, Any]:
    """Stage C: Cyclicality Detection & Normalization."""
    cc = config.cyclicality
    income = data.financials.income

    cyclicality_flag = "LOW"
    evidence: list[str] = []
    normalized_eps = None
    normalized_fcf = None

    # Check operating margin volatility
    if "operating_income" in income.columns and "revenue" in income.columns:
        op_margins = (income["operating_income"] / income["revenue"]).dropna()
        if len(op_margins) >= 3:
            margin_mean = op_margins.mean()
            margin_std = op_margins.std()
            current_margin = op_margins.iloc[-1]

            # High cyclicality: current margin deviates significantly from mean
            if margin_mean > 0 and current_margin > margin_mean * (1 + cc.peak_margin_deviation):
                cyclicality_flag = "HIGH"
                evidence.append(
                    f"Current operating margin ({current_margin:.1%}) is "
                    f"{((current_margin / margin_mean) - 1):.0%} above long-run mean ({margin_mean:.1%})"
                )
            elif margin_std > 0.05:
                cyclicality_flag = "MED"
                evidence.append(f"Operating margin stddev: {margin_std:.1%}")

    # Normalize EPS
    if "eps" in income.columns:
        eps = income["eps"].dropna().tail(cc.normalization_years)
        if len(eps) > 0:
            normalized_eps = eps.mean()

    # Normalize FCF
    cashflow = data.financials.cashflow
    if "free_cash_flow" in cashflow.columns:
        fcf = cashflow["free_cash_flow"].dropna().tail(cc.normalization_years)
        if len(fcf) > 0:
            normalized_fcf = fcf.mean()

    # Sector-based heuristic
    cyclical_sectors = {"Energy", "Basic Materials", "Industrials"}
    if data.info.sector in cyclical_sectors:
        if cyclicality_flag == "LOW":
            cyclicality_flag = "MED"
        evidence.append(f"Cyclical sector: {data.info.sector}")

    return {
        "cyclicality_flag": cyclicality_flag,
        "evidence": evidence,
        "normalized_eps": normalized_eps,
        "normalized_fcf": normalized_fcf,
    }


def _run_stage_d(
    data: TickerData, config: AppConfig, stage_c: dict[str, Any]
) -> dict[str, Any]:
    """Stage D: Intrinsic Value & Margin of Safety."""
    vc = config.valuation
    price = data.price.current_price

    if price <= 0:
        return {
            "intrinsic_range": {"low": 0, "base": 0, "high": 0},
            "margin_of_safety": 0,
            "methods": {},
        }

    methods: dict[str, Any] = {}
    intrinsic_values: list[float] = []

    cyclicality = stage_c.get("cyclicality_flag", "LOW")
    normalized_eps = stage_c.get("normalized_eps")
    normalized_fcf = stage_c.get("normalized_fcf")

    # Method 1: Conservative Earnings Power Value
    if normalized_eps is not None and normalized_eps > 0:
        multiple = vc.cyclical_multiple if cyclicality == "HIGH" else vc.conservative_multiple
        epv = normalized_eps * multiple
        methods["earnings_power"] = {
            "normalized_eps": round(normalized_eps, 2),
            "multiple": multiple,
            "intrinsic_price": round(epv, 2),
        }
        intrinsic_values.append(epv)

    # Method 2: Conservative DCF (per-share FCF)
    if normalized_fcf is not None and normalized_fcf > 0:
        shares = data.price.shares_outstanding
        if shares > 0:
            fcf_per_share = normalized_fcf / shares
            r = vc.discount_rate
            g = min(vc.growth_rate, vc.growth_rate_max)
            tg = vc.terminal_growth
            n = vc.dcf_years

            # Project FCF and discount
            dcf_value = 0.0
            for year in range(1, n + 1):
                projected_fcf = fcf_per_share * ((1 + g) ** year)
                dcf_value += projected_fcf / ((1 + r) ** year)

            # Terminal value (Gordon Growth)
            terminal_fcf = fcf_per_share * ((1 + g) ** n) * (1 + tg)
            terminal_value = terminal_fcf / (r - tg)
            pv_terminal = terminal_value / ((1 + r) ** n)

            dcf_total = dcf_value + pv_terminal

            # Range: base, low (80% of base), high (120% of base)
            methods["dcf"] = {
                "fcf_per_share": round(fcf_per_share, 2),
                "discount_rate": r,
                "growth_rate": g,
                "terminal_growth": tg,
                "dcf_years": n,
                "intrinsic_price": round(dcf_total, 2),
            }
            intrinsic_values.append(dcf_total)

    # Compute combined intrinsic value
    if intrinsic_values:
        base = sum(intrinsic_values) / len(intrinsic_values)
        low = base * 0.80
        high = base * 1.20
        mos = 1 - (price / base) if base > 0 else 0
    else:
        base = low = high = 0
        mos = 0

    return {
        "intrinsic_range": {
            "low": round(low, 2),
            "base": round(base, 2),
            "high": round(high, 2),
        },
        "margin_of_safety": round(mos, 4),
        "current_price": price,
        "methods": methods,
    }


def _run_stage_e(data: TickerData, config: AppConfig) -> dict[str, Any]:
    """Stage E: Value Trap Detection."""
    tc = config.trap_detection
    flags: list[dict[str, Any]] = []
    income = data.financials.income
    cashflow = data.financials.cashflow
    balance = data.financials.balance

    # Flag 1: Revenue + margin declining simultaneously for N years
    if "revenue" in income.columns and "operating_income" in income.columns:
        revenue = income["revenue"].dropna()
        op_income = income["operating_income"].dropna()
        n = tc.revenue_decline_years
        if len(revenue) >= n + 1:
            rev_tail = revenue.tail(n + 1)
            rev_declining = all(
                rev_tail.iloc[i] > rev_tail.iloc[i + 1] for i in range(len(rev_tail) - 1)
            )
            if rev_declining and len(op_income) >= n + 1:
                op_tail = op_income.tail(n + 1)
                op_declining = all(
                    op_tail.iloc[i] > op_tail.iloc[i + 1] for i in range(len(op_tail) - 1)
                )
                if op_declining:
                    flags.append({
                        "flag": "REVENUE_AND_MARGIN_DECLINE",
                        "severity": "HIGH",
                        "evidence": (
                            f"Revenue and operating income both declining "
                            f"for {n} consecutive years"
                        ),
                    })

    # Flag 2: FCF negative while EPS positive
    if "free_cash_flow" in cashflow.columns and "eps" in income.columns:
        fcf_latest = cashflow["free_cash_flow"].dropna()
        eps_latest = income["eps"].dropna()
        if len(fcf_latest) > 0 and len(eps_latest) > 0:
            if fcf_latest.iloc[-1] < 0 and eps_latest.iloc[-1] > 0:
                flags.append({
                    "flag": "FCF_EPS_DIVERGENCE",
                    "severity": "HIGH",
                    "evidence": (
                        f"FCF is negative ({fcf_latest.iloc[-1]:,.0f}) "
                        f"while EPS is positive ({eps_latest.iloc[-1]:.2f}) — "
                        f"possible accrual accounting issue"
                    ),
                })

    # Flag 3: Net debt growing faster than operating income
    if "net_debt" in balance.columns and "operating_income" in income.columns:
        net_debt = balance["net_debt"].dropna()
        op_inc = income["operating_income"].dropna()
        if len(net_debt) >= 3 and len(op_inc) >= 3:
            debt_growth = (net_debt.iloc[-1] / net_debt.iloc[0]) if net_debt.iloc[0] > 0 else 0
            income_growth = (op_inc.iloc[-1] / op_inc.iloc[0]) if op_inc.iloc[0] > 0 else 0
            if debt_growth > 1 and (debt_growth - 1) > tc.debt_growth_threshold:
                if income_growth < debt_growth:
                    flags.append({
                        "flag": "DEBT_OUTPACING_INCOME",
                        "severity": "MED",
                        "evidence": (
                            f"Net debt growth ({debt_growth - 1:.1%}) "
                            f"outpacing operating income growth ({income_growth - 1:.1%})"
                        ),
                    })

    # Flag 4: Interest coverage deteriorating
    if "operating_income" in income.columns and "interest_expense" in income.columns:
        oi = income["operating_income"].dropna()
        ie = income["interest_expense"].dropna()
        if len(oi) > 0 and len(ie) > 0:
            int_exp = abs(ie.iloc[-1]) if ie.iloc[-1] != 0 else 0
            if int_exp > 0:
                coverage = oi.iloc[-1] / int_exp
                if coverage < tc.interest_coverage_min:
                    flags.append({
                        "flag": "LOW_INTEREST_COVERAGE",
                        "severity": "MED" if coverage > 1.5 else "HIGH",
                        "evidence": f"Interest coverage ratio: {coverage:.1f}x (min: {tc.interest_coverage_min}x)",
                    })

    has_high = any(f["severity"] == "HIGH" for f in flags)

    return {
        "trap_flags": flags,
        "has_high_severity": has_high,
    }


def _run_stage_f(
    data: TickerData,
    config: AppConfig,
    stage_a: dict[str, Any],
    stage_b: dict[str, Any],
    stage_c: dict[str, Any],
    stage_d: dict[str, Any],
    stage_e: dict[str, Any],
) -> dict[str, Any]:
    """Stage F: Final Scoring & Signal Assignment."""
    sc = config.scoring
    vc = config.valuation
    weights = sc.weights

    # Sub-scores for final composite (0–100 each)
    sub_scores: dict[str, float] = {}

    # Valuation score: based on margin of safety
    mos = stage_d.get("margin_of_safety", 0)
    if mos >= vc.mos_strong_buy:
        sub_scores["valuation"] = 95
    elif mos >= vc.mos_buy:
        sub_scores["valuation"] = 75
    elif mos >= 0.15:
        sub_scores["valuation"] = 55
    elif mos > 0:
        sub_scores["valuation"] = 35
    else:
        sub_scores["valuation"] = 10

    # Earnings & Cash Quality
    sub_scores["earnings_quality"] = stage_b.get("quality_score", 50)

    # Balance Sheet score
    de = stage_a.get("metrics", {}).get("debt_to_equity", 1.0)
    cr = stage_a.get("metrics", {}).get("current_ratio", 1.5)
    bal_score = 50
    if de is not None and de < 0.5:
        bal_score += 25
    elif de is not None and de < 1.0:
        bal_score += 10
    if cr is not None and cr > 2.0:
        bal_score += 15
    elif cr is not None and cr > 1.5:
        bal_score += 5
    sub_scores["balance_sheet"] = min(100, bal_score)

    # Stability score
    cyclicality = stage_c.get("cyclicality_flag", "LOW")
    if cyclicality == "LOW":
        sub_scores["stability"] = 80
    elif cyclicality == "MED":
        sub_scores["stability"] = 55
    else:
        sub_scores["stability"] = 30

    # Moat proxies: from margin stability + ROIC consistency
    margin_stability = stage_b.get("sub_scores", {}).get("margin_stability", 40)
    roic_score = stage_b.get("sub_scores", {}).get("roic", 40)
    sub_scores["moat_proxies"] = (margin_stability + roic_score) / 2

    # Final weighted score
    final_score = (
        sub_scores["valuation"] * weights.valuation
        + sub_scores["earnings_quality"] * weights.earnings_quality
        + sub_scores["balance_sheet"] * weights.balance_sheet
        + sub_scores["stability"] * weights.stability
        + sub_scores["moat_proxies"] * weights.moat_proxies
    )

    # Signal assignment
    quality_score = stage_b.get("quality_score", 0)
    has_high_traps = stage_e.get("has_high_severity", False)
    thresholds = sc.signal_thresholds

    if has_high_traps:
        signal = "REJECT"
        signal_reasons = ["HIGH severity value trap flags detected"]
    elif (
        quality_score >= thresholds.strong_buy_quality
        and mos >= vc.mos_strong_buy
    ):
        signal = "STRONG_BUY_SIGNAL"
        signal_reasons = [
            f"Quality score {quality_score:.0f} >= {thresholds.strong_buy_quality}",
            f"Margin of safety {mos:.1%} >= {vc.mos_strong_buy:.0%}",
            "No HIGH severity trap flags",
        ]
    elif (
        quality_score >= thresholds.buy_quality
        and mos >= vc.mos_buy
    ):
        signal = "BUY_SIGNAL"
        signal_reasons = [
            f"Quality score {quality_score:.0f} >= {thresholds.buy_quality}",
            f"Margin of safety {mos:.1%} >= {vc.mos_buy:.0%}",
        ]
    elif stage_a["passed"]:
        signal = "WATCH"
        signal_reasons = [
            f"Passed hard filters but: quality={quality_score:.0f}, MOS={mos:.1%}",
        ]
        if quality_score < thresholds.buy_quality:
            signal_reasons.append(f"Quality below BUY threshold ({thresholds.buy_quality})")
        if mos < vc.mos_buy:
            signal_reasons.append(f"MOS below BUY threshold ({vc.mos_buy:.0%})")
    else:
        signal = "REJECT"
        signal_reasons = stage_a.get("reasons", ["Failed hard filters"])

    # Top drivers, risks, and invalidators
    drivers = _get_top_drivers(data, stage_a, stage_b, stage_c, stage_d, mos)
    risks = _get_top_risks(data, stage_e, stage_c, stage_b)
    invalidators = _get_thesis_invalidators(data, stage_d, stage_b, mos)

    return {
        "signal": signal,
        "signal_reasons": signal_reasons,
        "final_score": round(final_score, 1),
        "sub_scores": sub_scores,
        "score_breakdown": {
            "valuation": round(sub_scores.get("valuation", 0) * weights.valuation, 1),
            "earnings_quality": round(sub_scores.get("earnings_quality", 0) * weights.earnings_quality, 1),
            "balance_sheet": round(sub_scores.get("balance_sheet", 0) * weights.balance_sheet, 1),
            "stability": round(sub_scores.get("stability", 0) * weights.stability, 1),
            "moat_proxies": round(sub_scores.get("moat_proxies", 0) * weights.moat_proxies, 1),
        },
        "drivers": drivers[:5],
        "risks": risks[:5],
        "invalidators": invalidators[:5],
    }


def _get_top_drivers(
    data: TickerData, stage_a: dict, stage_b: dict, stage_c: dict,
    stage_d: dict, mos: float,
) -> list[str]:
    """Extract top 5 positive drivers explaining WHY this is a value stock."""
    drivers: list[str] = []
    price = data.price.current_price
    name = data.info.name or data.info.ticker

    # 1. Margin of Safety / Valuation
    intrinsic = stage_d.get("intrinsic_range", {})
    base_val = intrinsic.get("base", 0)
    if mos >= 0.45:
        drivers.append(
            f"Deep discount: {name} trades at ${price:.2f}, estimated intrinsic "
            f"value is ${base_val:.2f} — a {mos:.0%} margin of safety. "
            f"Graham requires ≥30%; this exceeds even the 45% strong-buy threshold."
        )
    elif mos >= 0.30:
        drivers.append(
            f"Undervalued: price ${price:.2f} vs estimated intrinsic value "
            f"${base_val:.2f} gives a {mos:.0%} margin of safety — meeting "
            f"Graham's 30% minimum safety requirement."
        )
    elif mos > 0:
        drivers.append(
            f"Modest discount: {mos:.0%} margin of safety "
            f"(price ${price:.2f} vs intrinsic ${base_val:.2f})."
        )

    # 2. Quality score
    quality = stage_b.get("quality_score", 0)
    if quality >= 80:
        drivers.append(
            f"Exceptional business quality (score {quality:.0f}/100): consistent "
            f"profitability, strong returns on capital, and stable margins — "
            f"hallmarks of a Buffett-style competitive moat."
        )
    elif quality >= 70:
        drivers.append(
            f"High quality business (score {quality:.0f}/100): above-average "
            f"returns on capital and reliable earnings generation."
        )
    elif quality >= 60:
        drivers.append(
            f"Adequate quality (score {quality:.0f}/100): meets minimum "
            f"quality thresholds for the Graham-Buffett framework."
        )

    # 3. Low P/E (classic Graham)
    pe = data.metrics.pe_ratio
    if pe and 0 < pe <= 10:
        drivers.append(
            f"Low P/E of {pe:.1f}x — classic Graham deep-value territory. "
            f"The market is pricing in pessimism, yet the business continues "
            f"to generate positive earnings."
        )
    elif pe and 0 < pe <= 15:
        drivers.append(
            f"Reasonable P/E of {pe:.1f}x — below long-run market average "
            f"(~15-17x), suggesting the stock is not overpriced."
        )

    # 4. ROIC (Buffett's key metric)
    roic = stage_b.get("roic_computed")
    if roic and roic > 0.15:
        drivers.append(
            f"High ROIC of {roic:.1%} — the business earns well above its "
            f"cost of capital, indicating a strong competitive advantage "
            f"and efficient capital allocation (Buffett seeks ROIC > 12%)."
        )
    elif roic and roic > 0.12:
        drivers.append(
            f"Solid ROIC of {roic:.1%} — above the 12% threshold, indicating "
            f"the business creates genuine economic value for shareholders."
        )

    # 5. Conservative balance sheet
    de = stage_a.get("metrics", {}).get("debt_to_equity")
    cr = stage_a.get("metrics", {}).get("current_ratio")
    if de is not None and de < 0.5 and cr is not None and cr > 2.0:
        drivers.append(
            f"Fortress balance sheet: D/E of {de:.2f}x (conservative) "
            f"and current ratio of {cr:.2f}x — ample liquidity and low "
            f"financial risk. Graham emphasis on capital preservation."
        )
    elif de is not None and de < 1.0:
        drivers.append(
            f"Conservative leverage: D/E ratio of {de:.2f}x is well within "
            f"Graham's maximum of 1.0x, reducing insolvency risk."
        )

    # 6. FCF generation
    sub_scores = stage_b.get("sub_scores", {})
    fcf_score = sub_scores.get("fcf_margin", 0)
    if fcf_score >= 70:
        drivers.append(
            f"Strong free cash flow generation — the company converts "
            f"earnings into real cash effectively, supporting dividends, "
            f"buybacks, and debt reduction."
        )

    # 7. Stable/non-cyclical
    cyclicality = stage_c.get("cyclicality_flag", "LOW")
    if cyclicality == "LOW":
        drivers.append(
            f"Low cyclicality: earnings are relatively stable and predictable, "
            f"making intrinsic value estimates more reliable."
        )

    return drivers[:5]


def _get_top_risks(
    data: TickerData, stage_e: dict, stage_c: dict, stage_b: dict
) -> list[str]:
    """Extract top 5 risks with detailed context."""
    risks: list[str] = []

    # Value trap flags (most critical)
    for flag in stage_e.get("trap_flags", []):
        severity = flag["severity"]
        evidence = flag["evidence"]
        flag_name = flag["flag"]
        if flag_name == "REVENUE_AND_MARGIN_DECLINE":
            risks.append(
                f"⚠️ [{severity}] Secular decline: {evidence}. This is the #1 "
                f"value trap pattern — a stock looks cheap because the business "
                f"is structurally deteriorating."
            )
        elif flag_name == "FCF_EPS_DIVERGENCE":
            risks.append(
                f"⚠️ [{severity}] Earnings quality concern: {evidence}. "
                f"When FCF diverges from EPS, reported earnings may be "
                f"inflated by accounting choices."
            )
        elif flag_name == "DEBT_OUTPACING_INCOME":
            risks.append(
                f"⚠️ [{severity}] Leverage risk: {evidence}. Growing debt "
                f"with stagnant income can lead to financial distress."
            )
        elif flag_name == "LOW_INTEREST_COVERAGE":
            risks.append(
                f"⚠️ [{severity}] Debt service risk: {evidence}. If rates "
                f"rise or earnings dip, the company may struggle to cover "
                f"interest payments."
            )
        else:
            risks.append(f"⚠️ [{severity}] {flag_name}: {evidence}")

    # Cyclicality risk
    if stage_c.get("cyclicality_flag") == "HIGH":
        risks.append(
            f"Cyclical business at potentially peak earnings — if the cycle "
            f"turns, earnings could drop significantly and the stock may "
            f"become much less cheap than it appears today."
        )
    elif stage_c.get("cyclicality_flag") == "MED":
        evidence = stage_c.get("evidence", [])
        ev_str = "; ".join(evidence) if evidence else "moderate margin volatility"
        risks.append(f"Moderate cyclicality ({ev_str}) — earnings may fluctuate.")

    # Quality warnings
    for w in stage_b.get("warnings", []):
        risks.append(f"Quality concern: {w}")

    # General market risk
    beta = data.metrics.beta
    if beta and beta > 1.5:
        risks.append(
            f"High market sensitivity (beta {beta:.2f}): the stock tends to "
            f"amplify market swings, creating larger drawdown risk."
        )

    if not risks:
        risks.append("No significant risks identified in this analysis.")

    return risks[:5]


def _get_thesis_invalidators(
    data: TickerData, stage_d: dict, stage_b: dict, mos: float
) -> list[str]:
    """Generate clear triggers that would invalidate the investment thesis."""
    invalidators: list[str] = []
    price = data.price.current_price
    intrinsic = stage_d.get("intrinsic_range", {})
    base_val = intrinsic.get("base", 0)

    # Earnings deterioration
    income = data.financials.income
    if "eps" in income.columns:
        latest_eps = income["eps"].dropna()
        if len(latest_eps) > 0:
            eps_val = latest_eps.iloc[-1]
            if eps_val > 0:
                invalidators.append(
                    f"EPS drops below ${eps_val * 0.7:.2f} (-30%): would signal "
                    f"fundamental deterioration and destroy the valuation thesis."
                )

    # Margin collapse
    if data.metrics.operating_margin and data.metrics.operating_margin > 0:
        half_margin = data.metrics.operating_margin * 0.5
        invalidators.append(
            f"Operating margin falls below {half_margin:.1%}: would indicate "
            f"loss of pricing power or competitive advantage."
        )

    # Debt explosion
    de = data.metrics.debt_to_equity
    if de is not None:
        de_ratio = de / 100 if de > 10 else de
        invalidators.append(
            f"D/E ratio rises above {max(de_ratio * 2, 1.5):.1f}x: would "
            f"signal aggressive leverage inconsistent with conservative investment."
        )

    # FCF turning negative
    invalidators.append(
        "Free cash flow turns negative for 2+ consecutive years: "
        "would undermine ability to service debt, pay dividends, or buy back shares."
    )

    # Management actions
    invalidators.append(
        "Major acquisition at premium prices or significant share dilution: "
        "would signal capital allocation discipline has broken down."
    )

    return invalidators[:5]
