"""
Configuration loader and validator.

Loads config.yaml, merges with defaults, validates all thresholds.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Default configuration (embedded so the system works even without config.yaml)
# ---------------------------------------------------------------------------
DEFAULTS: dict[str, Any] = {
    "universe": {
        "market": "US",
        "min_market_cap": 1_000_000_000,
        "sector_mode": "simple",
        "exclude_sectors": ["Financial Services", "Real Estate"],
        "allow_turnarounds": False,
    },
    "hard_filters": {
        "pe_max": 10,
        "eps_positive_min_years": 5,
        "eps_lookback_years": 7,
        "fcf_positive_min_years": 4,
        "fcf_lookback_years": 5,
        "debt_to_equity_max": 1.0,
        "current_ratio_min": 1.5,
        "dilution_cagr_max": 0.03,
    },
    "quality": {
        "roic_min": 0.12,
        "roe_min": 0.15,
        "gross_margin_max_stddev": 0.05,
        "quality_score_min": 60,
    },
    "cyclicality": {
        "normalization_years": 5,
        "peak_margin_deviation": 0.5,
        "cyclical_pe_max": 7,
    },
    "valuation": {
        "conservative_multiple": 10,
        "cyclical_multiple": 7,
        "discount_rate": 0.11,
        "growth_rate": 0.02,
        "growth_rate_max": 0.03,
        "terminal_growth": 0.02,
        "dcf_years": 10,
        "mos_buy": 0.30,
        "mos_strong_buy": 0.45,
    },
    "trap_detection": {
        "revenue_decline_years": 3,
        "interest_coverage_min": 3.0,
        "debt_growth_threshold": 0.10,
    },
    "scoring": {
        "weights": {
            "valuation": 0.30,
            "earnings_quality": 0.25,
            "balance_sheet": 0.20,
            "stability": 0.15,
            "moat_proxies": 0.10,
        },
        "signal_thresholds": {
            "strong_buy_quality": 75,
            "buy_quality": 65,
        },
    },
    "provider": {
        "name": "yfinance",
        "cache_ttl_hours": 24,
        "rate_limit_per_second": 2,
        "max_retries": 3,
        "retry_backoff": 2.0,
    },
    "output": {
        "run_dir": "runs",
        "exports_dir": "exports",
        "site_root": ".",
        "site_assets": "site",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* (non-destructive)."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# ---------------------------------------------------------------------------
# Typed config dataclasses for IDE-friendly access
# ---------------------------------------------------------------------------
@dataclass
class UniverseConfig:
    market: str = "US"
    min_market_cap: int = 1_000_000_000
    sector_mode: str = "simple"
    exclude_sectors: list[str] = field(default_factory=lambda: ["Financial Services", "Real Estate"])
    allow_turnarounds: bool = False


@dataclass
class HardFiltersConfig:
    pe_max: float = 10
    eps_positive_min_years: int = 5
    eps_lookback_years: int = 7
    fcf_positive_min_years: int = 4
    fcf_lookback_years: int = 5
    debt_to_equity_max: float = 1.0
    current_ratio_min: float = 1.5
    dilution_cagr_max: float = 0.03


@dataclass
class QualityConfig:
    roic_min: float = 0.12
    roe_min: float = 0.15
    gross_margin_max_stddev: float = 0.05
    quality_score_min: int = 60


@dataclass
class CyclicalityConfig:
    normalization_years: int = 5
    peak_margin_deviation: float = 0.5
    cyclical_pe_max: float = 7


@dataclass
class ValuationConfig:
    conservative_multiple: float = 10
    cyclical_multiple: float = 7
    discount_rate: float = 0.11
    growth_rate: float = 0.02
    growth_rate_max: float = 0.03
    terminal_growth: float = 0.02
    dcf_years: int = 10
    mos_buy: float = 0.30
    mos_strong_buy: float = 0.45


@dataclass
class TrapDetectionConfig:
    revenue_decline_years: int = 3
    interest_coverage_min: float = 3.0
    debt_growth_threshold: float = 0.10


@dataclass
class ScoringWeights:
    valuation: float = 0.30
    earnings_quality: float = 0.25
    balance_sheet: float = 0.20
    stability: float = 0.15
    moat_proxies: float = 0.10


@dataclass
class SignalThresholds:
    strong_buy_quality: int = 75
    buy_quality: int = 65


@dataclass
class ScoringConfig:
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    signal_thresholds: SignalThresholds = field(default_factory=SignalThresholds)


@dataclass
class ProviderConfig:
    name: str = "yfinance"
    cache_ttl_hours: int = 24
    rate_limit_per_second: float = 2
    max_retries: int = 3
    retry_backoff: float = 2.0


@dataclass
class OutputConfig:
    run_dir: str = "runs"
    exports_dir: str = "exports"
    site_root: str = "."
    site_assets: str = "site"


@dataclass
class AppConfig:
    """Top-level application configuration."""

    universe: UniverseConfig = field(default_factory=UniverseConfig)
    hard_filters: HardFiltersConfig = field(default_factory=HardFiltersConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    cyclicality: CyclicalityConfig = field(default_factory=CyclicalityConfig)
    valuation: ValuationConfig = field(default_factory=ValuationConfig)
    trap_detection: TrapDetectionConfig = field(default_factory=TrapDetectionConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        """Build AppConfig from a flat dictionary (e.g., merged YAML)."""
        cfg = cls()
        if "universe" in data:
            cfg.universe = UniverseConfig(**data["universe"])
        if "hard_filters" in data:
            cfg.hard_filters = HardFiltersConfig(**data["hard_filters"])
        if "quality" in data:
            cfg.quality = QualityConfig(**data["quality"])
        if "cyclicality" in data:
            cfg.cyclicality = CyclicalityConfig(**data["cyclicality"])
        if "valuation" in data:
            cfg.valuation = ValuationConfig(**data["valuation"])
        if "trap_detection" in data:
            cfg.trap_detection = TrapDetectionConfig(**data["trap_detection"])
        if "scoring" in data:
            sd = data["scoring"]
            weights = ScoringWeights(**sd["weights"]) if "weights" in sd else ScoringWeights()
            thresholds = SignalThresholds(**sd["signal_thresholds"]) if "signal_thresholds" in sd else SignalThresholds()
            cfg.scoring = ScoringConfig(weights=weights, signal_thresholds=thresholds)
        if "provider" in data:
            cfg.provider = ProviderConfig(**data["provider"])
        if "output" in data:
            cfg.output = OutputConfig(**data["output"])
        return cfg


def _validate(cfg: AppConfig) -> list[str]:
    """Return list of validation errors (empty = OK)."""
    errors: list[str] = []

    if cfg.universe.min_market_cap < 0:
        errors.append("universe.min_market_cap must be >= 0")
    if cfg.universe.sector_mode not in ("simple", "full"):
        errors.append("universe.sector_mode must be 'simple' or 'full'")

    if cfg.hard_filters.pe_max <= 0:
        errors.append("hard_filters.pe_max must be > 0")
    if cfg.hard_filters.debt_to_equity_max < 0:
        errors.append("hard_filters.debt_to_equity_max must be >= 0")

    w = cfg.scoring.weights
    total = w.valuation + w.earnings_quality + w.balance_sheet + w.stability + w.moat_proxies
    if abs(total - 1.0) > 0.01:
        errors.append(f"scoring.weights must sum to 1.0, got {total:.3f}")

    if cfg.valuation.discount_rate <= cfg.valuation.terminal_growth:
        errors.append("valuation.discount_rate must be > terminal_growth")

    if cfg.valuation.mos_buy >= 1.0 or cfg.valuation.mos_buy < 0:
        errors.append("valuation.mos_buy must be in [0, 1)")
    if cfg.valuation.mos_strong_buy >= 1.0 or cfg.valuation.mos_strong_buy < 0:
        errors.append("valuation.mos_strong_buy must be in [0, 1)")

    return errors


def load_config(path: str | Path | None = None) -> AppConfig:
    """
    Load configuration from YAML file, merge with defaults, validate.

    Args:
        path: Path to config.yaml. If None, uses defaults only.

    Returns:
        Validated AppConfig instance.

    Raises:
        FileNotFoundError: If path is specified but doesn't exist.
        ValueError: If config validation fails.
    """
    if path is not None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            user_data = yaml.safe_load(f) or {}
        merged = _deep_merge(DEFAULTS, user_data)
    else:
        merged = copy.deepcopy(DEFAULTS)

    cfg = AppConfig.from_dict(merged)
    errors = _validate(cfg)
    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

    return cfg


def save_resolved_config(cfg: AppConfig, path: Path) -> None:
    """Save the resolved (merged + validated) config to YAML for reproducibility."""
    import dataclasses

    def _to_dict(obj: Any) -> Any:
        if dataclasses.is_dataclass(obj):
            return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
        return obj

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(_to_dict(cfg), f, default_flow_style=False, sort_keys=False)
