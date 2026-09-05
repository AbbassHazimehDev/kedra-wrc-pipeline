"""Date parsing and inclusive monthly partitioning."""

from dataclasses import dataclass
from datetime import date

from dateutil.relativedelta import relativedelta


INPUT_DATE_FORMAT = "%Y-%m-%d"


@dataclass(frozen=True)
class DatePartition:
    """One inclusive date range sent to the WRC search page."""

    start_date: date
    end_date: date

    @property
    def partition_date(self) -> str:
        """Return the stable year-month label for this partition."""
        return self.start_date.strftime("%Y-%m")


def parse_iso_date(value: str) -> date:
    """Parse a date supplied in the public CLI format YYYY-MM-DD."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid date {value!r}; expected YYYY-MM-DD"
        ) from exc


def parse_date_range(start_date: str, end_date: str) -> tuple[date, date]:
    """Parse and validate an inclusive start/end date range."""
    if not start_date or not end_date:
        raise ValueError("Both start_date and end_date are required")
    start = parse_iso_date(start_date)
    end = parse_iso_date(end_date)
    if start > end:
        raise ValueError("start_date must be on or before end_date")
    return start, end


def generate_partitions(
    start_date: str | date,
    end_date: str | date,
    partition_months: int = 1,
) -> list[DatePartition]:
    """Create contiguous, inclusive partitions without date gaps or overlap."""
    if partition_months < 1:
        raise ValueError("partition_months must be at least 1")

    if isinstance(start_date, str) or isinstance(end_date, str):
        if not isinstance(start_date, str) or not isinstance(end_date, str):
            raise ValueError("start_date and end_date must use the same type")
        start, end = parse_date_range(start_date, end_date)
    else:
        start, end = start_date, end_date
        if start > end:
            raise ValueError("start_date must be on or before end_date")

    partitions = []
    current = start
    while current <= end:
        chunk_start = current.replace(day=1)
        chunk_end = chunk_start + relativedelta(months=partition_months, days=-1)
        partition_end = min(chunk_end, end)
        partitions.append(DatePartition(current, partition_end))
        current = partition_end + relativedelta(days=1)
    return partitions
