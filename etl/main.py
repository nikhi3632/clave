"""ETL pipeline orchestrator with graceful shutdown support."""

import atexit
import logging
import signal
import sys
import threading
from datetime import datetime
from pathlib import Path
from types import FrameType

from dotenv import load_dotenv

from .classifier import CategoryClassifier
from .config import ETLConfig, setup_logging
from .exceptions import ETLError, ExtractionError, LoadError
from .extract import extract_doordash, extract_square, extract_toast, seed_locations
from .load import Loader
from .transform import Transformer
from .validator import Validator

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Handle graceful shutdown on signals."""

    def __init__(self) -> None:
        self._shutdown_requested = threading.Event()
        self._original_handlers: dict[int, signal.Handlers] = {}
        self._loader: Loader | None = None

    def register(self, loader: Loader | None = None) -> None:
        """Register signal handlers."""
        self._loader = loader

        # Store original handlers and register ours
        for sig in (signal.SIGINT, signal.SIGTERM):
            self._original_handlers[sig] = signal.signal(sig, self._handle_signal)

        # Also register SIGHUP on Unix systems
        if hasattr(signal, "SIGHUP"):
            self._original_handlers[signal.SIGHUP] = signal.signal(
                signal.SIGHUP, self._handle_signal
            )

        # Register cleanup on exit
        atexit.register(self.cleanup)

    def _handle_signal(self, signum: int, frame: FrameType | None) -> None:
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        logger.warning(f"Received {sig_name}, initiating graceful shutdown...")
        self._shutdown_requested.set()

        # If we receive the signal twice, force exit
        signal.signal(signum, self._force_exit)

    def _force_exit(self, signum: int, frame: FrameType | None) -> None:
        """Force exit on second signal."""
        sig_name = signal.Signals(signum).name
        logger.error(f"Received {sig_name} again, forcing exit...")
        self.cleanup()
        sys.exit(130)  # 128 + SIGINT(2)

    @property
    def should_stop(self) -> bool:
        """Check if shutdown was requested."""
        return self._shutdown_requested.is_set()

    def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up resources...")

        # Close database connections
        if self._loader:
            try:
                self._loader.close()
                logger.info("Database connections closed")
            except Exception as e:
                logger.error(f"Error closing database connections: {e}")

        # Restore original signal handlers
        for sig, handler in self._original_handlers.items():
            try:
                signal.signal(sig, handler)
            except Exception:
                pass

    def check_or_raise(self) -> None:
        """Raise KeyboardInterrupt if shutdown requested."""
        if self.should_stop:
            raise KeyboardInterrupt("Shutdown requested")


# Global shutdown handler
shutdown = GracefulShutdown()


def run_etl(data_dir: Path, config: ETLConfig | None = None) -> dict:
    """
    Run the full ETL pipeline.

    Args:
        data_dir: Directory containing source data files.
        config: Optional ETL configuration.

    Returns:
        Dict with counts: {extracted, loaded, failed, interrupted}

    Raises:
        ETLError: If a critical error occurs.
    """
    if config is None:
        config = ETLConfig.from_env()

    setup_logging(config.logging)

    run_id = f"etl_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"Starting ETL run: {run_id}")
    logger.info(f"Data directory: {data_dir}")

    # Counts
    extracted = 0
    loaded = 0
    failed = 0
    interrupted = False

    # Initialize loader
    loader = None
    try:
        loader = Loader()
        shutdown.register(loader)
    except LoadError as e:
        logger.error(f"Failed to initialize loader: {e}")
        raise

    try:
        # Seed location matcher from database
        try:
            location_names = loader.get_location_names()
            seed_locations(location_names)
            logger.info(f"Loaded {len(location_names)} locations from database")
        except Exception as e:
            logger.warning(f"Could not seed locations from database: {e}")

        shutdown.check_or_raise()

        # Seed transformer with existing products
        try:
            existing_products = loader.get_existing_products()
            logger.info(f"Loaded {len(existing_products)} existing products from database")
        except Exception as e:
            logger.warning(f"Could not load existing products: {e}")
            existing_products = []

        # Initialize category classifier
        classifier = None
        try:
            classifier = CategoryClassifier(loader.client)
            classifier.load_cache()
        except Exception as e:
            logger.warning(f"Could not initialize category classifier: {e}")
            logger.warning("Continuing without LLM category classification")

        transformer = Transformer(existing_products, category_classifier=classifier)

        # Initialize validator for anomaly detection
        validator = Validator(run_id=run_id, client=loader.client)

        # Source configs
        sources = [
            ("toast", lambda: extract_toast(data_dir / "sources" / "toast_pos_export.json")),
            ("doordash", lambda: extract_doordash(data_dir / "sources" / "doordash_orders.json")),
            (
                "square",
                lambda: extract_square(
                    data_dir / "sources" / "square" / "orders.json",
                    data_dir / "sources" / "square" / "catalog.json",
                    data_dir / "sources" / "square" / "locations.json",
                ),
            ),
        ]

        all_orders = []

        for source_name, extractor in sources:
            if shutdown.should_stop:
                logger.warning(f"Skipping {source_name} due to shutdown request")
                break

            source_extracted = 0
            source_transformed = 0
            logger.info(f"Processing {source_name}...")

            try:
                for raw_order in extractor():
                    # Check for shutdown periodically
                    if shutdown.should_stop:
                        logger.warning(f"Stopping {source_name} extraction due to shutdown")
                        break

                    source_extracted += 1
                    result = transformer.transform(raw_order)

                    if result.success and result.order:
                        # Validate order and detect anomalies
                        validator.validate_order(result.order, source_name)
                        source_transformed += 1
                        all_orders.append(result.order)
                    else:
                        failed += 1
                        if result.error:
                            logger.warning(f"Transform failed: {result.error}")

            except ExtractionError as e:
                logger.error(f"Extraction failed for {source_name}: {e}")
            except Exception:
                logger.exception(f"Unexpected error processing {source_name}")

            extracted += source_extracted
            logger.info(
                f"  {source_name}: extracted={source_extracted}, transformed={source_transformed}"
            )

        # Check for price variance across products
        if not shutdown.should_stop:
            validator.check_price_variance()

        # Run LLM category classification and apply normalized categories
        if not shutdown.should_stop and classifier:
            try:
                classifier.classify_pending()
                transformer.apply_llm_categories()
                classifier.save_cache()
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}")

        # Load products first (if not interrupted)
        if not shutdown.should_stop:
            products = transformer.get_products()
            try:
                loader.load_products(products)
                logger.info(f"Products loaded: {len(products)}")
            except LoadError as e:
                logger.error(f"Failed to load products: {e}")

        # Load orders
        for i, order in enumerate(all_orders):
            if shutdown.should_stop:
                logger.warning(f"Stopping order loading at {i}/{len(all_orders)} due to shutdown")
                interrupted = True
                break

            try:
                loader.load_order(order)
                loaded += 1
            except LoadError as e:
                failed += 1
                logger.warning(f"Failed to load order {order.external_id}: {e}")
            except Exception:
                failed += 1
                logger.exception(f"Unexpected error loading order {order.external_id}")

        # Refresh materialized views (only if completed successfully)
        if not shutdown.should_stop:
            try:
                loader.refresh_views()
            except Exception as e:
                logger.warning(f"Could not refresh views: {e}")

        # Save anomalies and log validation summary
        if not shutdown.should_stop:
            validator.save_anomalies()
            validator.log_summary()

    except KeyboardInterrupt:
        logger.warning("ETL interrupted by user")
        interrupted = True
    finally:
        # Ensure cleanup happens
        shutdown.cleanup()

    # Summary
    success_rate = (loaded / extracted * 100) if extracted > 0 else 0
    logger.info("=" * 50)
    if interrupted:
        logger.warning("ETL Interrupted!")
    else:
        logger.info("ETL Complete!")
    logger.info(f"  Extracted: {extracted}")
    logger.info(f"  Loaded: {loaded}")
    logger.info(f"  Failed: {failed}")
    logger.info(f"  Success rate: {success_rate:.1f}%")
    if interrupted:
        logger.info("  Status: INTERRUPTED (partial data loaded)")
    logger.info("=" * 50)

    return {"extracted": extracted, "loaded": loaded, "failed": failed, "interrupted": interrupted}


def main() -> None:
    """CLI entry point."""
    project_root = Path(__file__).parent.parent.parent
    load_dotenv(project_root / ".env")

    data_dir = project_root / "data"

    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    exit_code = 0
    try:
        result = run_etl(data_dir)
        if result["interrupted"]:
            exit_code = 130  # Standard exit code for SIGINT
        elif result["failed"] > 0:
            exit_code = 1
    except ETLError as e:
        print(f"ETL Error: {e}", file=sys.stderr)
        exit_code = 1
    except KeyboardInterrupt:
        print("\nETL cancelled by user", file=sys.stderr)
        exit_code = 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        exit_code = 1
    finally:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
