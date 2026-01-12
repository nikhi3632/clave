"""Custom exceptions for the ETL pipeline."""


class ETLError(Exception):
    """Base exception for all ETL errors."""

    pass


class ExtractionError(ETLError):
    """Error during data extraction from a source."""

    def __init__(self, source: str, message: str):
        self.source = source
        super().__init__(f"[{source}] {message}")


class TransformationError(ETLError):
    """Error during data transformation."""

    def __init__(self, order_id: str, message: str):
        self.order_id = order_id
        super().__init__(f"Order {order_id}: {message}")


class LoadError(ETLError):
    """Error during data loading to database."""

    def __init__(self, table: str, message: str):
        self.table = table
        super().__init__(f"[{table}] {message}")


class ValidationError(ETLError):
    """Error during data validation."""

    def __init__(self, field: str, value: str, message: str):
        self.field = field
        self.value = value
        super().__init__(f"Invalid {field}='{value}': {message}")


class MatchError(ETLError):
    """Error during fuzzy matching."""

    def __init__(self, input_value: str, match_type: str, message: str):
        self.input_value = input_value
        self.match_type = match_type
        super().__init__(f"Failed to match {match_type} '{input_value}': {message}")
