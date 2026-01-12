"""ETL configuration with sensible defaults."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class MatchingConfig:
    """Configuration for fuzzy matching thresholds."""

    product_threshold: float = 0.70
    category_threshold: int = 85
    location_threshold: int = 75
    channel_threshold: int = 70


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuration for database operations."""

    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    batch_size: int = 100


@dataclass(frozen=True)
class LoggingConfig:
    """Configuration for logging."""

    level: int = logging.INFO
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"


@dataclass
class ETLConfig:
    """Main ETL configuration."""

    matching: MatchingConfig = field(default_factory=MatchingConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # Paths (set at runtime)
    data_dir: Path | None = None

    @classmethod
    def from_env(cls) -> "ETLConfig":
        """Create config from environment variables with defaults."""
        return cls(
            matching=MatchingConfig(
                product_threshold=float(os.environ.get("ETL_PRODUCT_THRESHOLD", "0.70")),
                category_threshold=int(os.environ.get("ETL_CATEGORY_THRESHOLD", "85")),
                location_threshold=int(os.environ.get("ETL_LOCATION_THRESHOLD", "75")),
                channel_threshold=int(os.environ.get("ETL_CHANNEL_THRESHOLD", "70")),
            ),
            database=DatabaseConfig(
                max_retries=int(os.environ.get("ETL_MAX_RETRIES", "3")),
                retry_delay_seconds=float(os.environ.get("ETL_RETRY_DELAY", "1.0")),
                batch_size=int(os.environ.get("ETL_BATCH_SIZE", "100")),
            ),
        )


def setup_logging(config: LoggingConfig | None = None) -> None:
    """Configure logging for the ETL pipeline."""
    if config is None:
        config = LoggingConfig()

    logging.basicConfig(
        level=config.level,
        format=config.format,
        datefmt=config.date_format,
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# Default config instance
_default_config: ETLConfig | None = None


def get_config() -> ETLConfig:
    """Get the current ETL configuration."""
    global _default_config
    if _default_config is None:
        _default_config = ETLConfig.from_env()
    return _default_config


def set_config(config: ETLConfig) -> None:
    """Set the ETL configuration (for testing)."""
    global _default_config
    _default_config = config
