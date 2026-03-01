"""
Run folder management.

Creates timestamped output directories for each pipeline run,
ensuring reproducibility and clean organization.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from loguru import logger

from src.config import AppConfig, save_resolved_config


class RunManager:
    """
    Manages the timestamped run folder and its subdirectories.

    Structure:
        runs/<timestamp>/
            config_resolved.yaml
            logs/run.log
            data/raw/
            data/processed/
            reports/<TICKER>/report.md, report.json
            exports/candidates.csv, rejected.csv
    """

    def __init__(self, config: AppConfig, timestamp: str | None = None):
        self.config = config
        self.timestamp = timestamp or datetime.now().strftime("%Y-%m-%d_%H%M")
        self.base_dir = Path(config.output.run_dir)
        self.run_dir = self.base_dir / self.timestamp

    def initialize(self) -> "RunManager":
        """Create the run folder structure and save resolved config."""
        dirs = [
            self.run_dir,
            self.log_dir,
            self.data_raw_dir,
            self.data_processed_dir,
            self.reports_dir,
            self.exports_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        # Save resolved config for reproducibility
        config_path = self.run_dir / "config_resolved.yaml"
        save_resolved_config(self.config, config_path)
        logger.info(f"Run initialized: {self.run_dir}")

        return self

    @property
    def log_dir(self) -> Path:
        return self.run_dir / "logs"

    @property
    def data_raw_dir(self) -> Path:
        return self.run_dir / "data" / "raw"

    @property
    def data_processed_dir(self) -> Path:
        return self.run_dir / "data" / "processed"

    @property
    def reports_dir(self) -> Path:
        return self.run_dir / "reports"

    @property
    def exports_dir(self) -> Path:
        return self.run_dir / "exports"

    def ticker_report_dir(self, ticker: str) -> Path:
        """Get/create the report directory for a specific ticker."""
        d = self.reports_dir / ticker
        d.mkdir(parents=True, exist_ok=True)
        return d
