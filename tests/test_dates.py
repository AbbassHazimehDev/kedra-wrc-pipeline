"""Tests for date validation and partitioning."""

from datetime import date

import pytest

from wrc_pipeline.utils.dates import generate_partitions, parse_date_range


def test_month_partitions_are_inclusive_and_contiguous():
    partitions = generate_partitions("2024-01-15", "2024-03-05")

    assert [(p.start_date, p.end_date, p.partition_date) for p in partitions] == [
        (date(2024, 1, 15), date(2024, 1, 31), "2024-01"),
        (date(2024, 2, 1), date(2024, 2, 29), "2024-02"),
        (date(2024, 3, 1), date(2024, 3, 5), "2024-03"),
    ]


def test_partition_months_can_group_months():
    partitions = generate_partitions("2023-12-20", "2024-05-04", 3)

    assert [(p.start_date, p.end_date) for p in partitions] == [
        (date(2023, 12, 20), date(2024, 2, 29)),
        (date(2024, 3, 1), date(2024, 5, 4)),
    ]


@pytest.mark.parametrize(
    "start,end",
    [(None, "2024-01-01"), ("2024-01-01", None), ("bad", "2024-01-01")],
)
def test_invalid_date_input_is_rejected(start, end):
    with pytest.raises(ValueError):
        parse_date_range(start, end)


def test_reversed_date_range_is_rejected():
    with pytest.raises(ValueError, match="on or before"):
        parse_date_range("2024-02-01", "2024-01-31")
