"""Tests for CDRService query construction."""

from datetime import datetime

import pytest

from app.services import cdr_service
from app.services.cdr_service import CDRService

# A Wednesday, so "this_week" starts two days earlier
FROZEN_NOW = datetime(2024, 6, 12, 15, 30, 0)


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def unique(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    """Captures the executed statement instead of hitting PostgreSQL."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return FakeResult(self.rows)

    @property
    def params(self) -> dict:
        return self.statements[-1].compile().params


@pytest.fixture
def frozen_now(monkeypatch):
    def _freeze(now: datetime = FROZEN_NOW):
        class FrozenDatetime(datetime):
            @classmethod
            def utcnow(cls):
                return now

        monkeypatch.setattr(cdr_service, "datetime", FrozenDatetime)

    _freeze()
    return _freeze


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "period,start,end",
    [
        ("today", datetime(2024, 6, 12), datetime(2024, 6, 13)),
        ("yesterday", datetime(2024, 6, 11), datetime(2024, 6, 12)),
        ("last_7_days", datetime(2024, 6, 5, 15, 30), FROZEN_NOW),
        ("last_30_days", datetime(2024, 5, 13, 15, 30), FROZEN_NOW),
        ("this_week", datetime(2024, 6, 10), datetime(2024, 6, 17)),
        ("this_month", datetime(2024, 6, 1), datetime(2024, 7, 1)),
        ("this_year", datetime(2024, 1, 1), datetime(2025, 1, 1)),
        pytest.param(None, datetime(2024, 6, 12, 14, 30), FROZEN_NOW, id="default-last-hour"),
        pytest.param("bogus", datetime(2024, 6, 12, 14, 30), FROZEN_NOW, id="unknown-last-hour"),
    ],
)
async def test_period_bounds(frozen_now, period, start, end):
    db = FakeSession()

    await CDRService.get_cdrs_by_period(db, "example.com", period)

    assert db.params == {
        "domain_name_1": "example.com",
        "start_stamp_1": start,
        "start_stamp_2": end,
    }


@pytest.mark.asyncio
async def test_this_month_rolls_over_year_in_december(frozen_now):
    frozen_now(datetime(2024, 12, 31, 23, 0))
    db = FakeSession()

    await CDRService.get_cdrs_by_period(db, "example.com", "this_month")

    assert db.params["start_stamp_1"] == datetime(2024, 12, 1)
    assert db.params["start_stamp_2"] == datetime(2025, 1, 1)


@pytest.mark.asyncio
async def test_period_query_is_scoped_to_domain_and_ordered_newest_first(frozen_now):
    db = FakeSession()

    await CDRService.get_cdrs_by_period(db, "example.com", "today")

    sql = str(db.statements[-1])
    assert "v_xml_cdr.domain_name = :domain_name_1" in sql
    assert "ORDER BY v_xml_cdr.start_stamp DESC" in sql
    assert db.params["domain_name_1"] == "example.com"


@pytest.mark.asyncio
async def test_period_query_returns_rows_as_list(frozen_now, make_cdr):
    rows = [make_cdr(), make_cdr()]

    result = await CDRService.get_cdrs_by_period(FakeSession(rows), "example.com")

    assert result == rows


@pytest.mark.asyncio
async def test_date_range_includes_end_bound():
    db = FakeSession()
    start, end = datetime(2024, 1, 1), datetime(2024, 1, 31, 23, 59, 59)

    await CDRService.get_cdrs_by_date_range(db, "example.com", start, end)

    sql = str(db.statements[-1])
    assert "v_xml_cdr.start_stamp >= :start_stamp_1" in sql
    assert "v_xml_cdr.start_stamp <= :start_stamp_2" in sql
    assert db.params == {
        "domain_name_1": "example.com",
        "start_stamp_1": start,
        "start_stamp_2": end,
    }


@pytest.mark.asyncio
async def test_cdr_count_returns_zero_when_empty():
    class CountSession(FakeSession):
        async def execute(self, stmt):
            self.statements.append(stmt)

            class _Result:
                def scalar(self):
                    return None

            return _Result()

    db = CountSession()

    assert await CDRService.get_cdr_count(db, "example.com") == 0
    assert db.params == {"domain_name_1": "example.com"}
