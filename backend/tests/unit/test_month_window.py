"""Unit tests for the current-month window helpers.

The same December-rollover logic exists in the usage route and the token
usage repository; both are covered here so a regression in either copy
is caught.
"""

from datetime import datetime

import pytest

from app.adapters.database_repo import _current_month_bounds
from app.api.routes.usage import _current_month_window


@pytest.mark.parametrize("window", [_current_month_window, _current_month_bounds])
class TestCurrentMonthWindow:
    def test_mid_month_is_truncated_to_month_boundaries(self, window):
        start, end = window(datetime(2026, 6, 15, 13, 45, 30, 123456))

        assert start == datetime(2026, 6, 1, 0, 0, 0)
        assert end == datetime(2026, 7, 1, 0, 0, 0)

    def test_first_instant_of_month_keeps_same_window(self, window):
        start, end = window(datetime(2026, 6, 1, 0, 0, 0))

        assert start == datetime(2026, 6, 1, 0, 0, 0)
        assert end == datetime(2026, 7, 1, 0, 0, 0)

    def test_last_instant_of_month_stays_in_current_window(self, window):
        start, end = window(datetime(2026, 6, 30, 23, 59, 59, 999999))

        assert start == datetime(2026, 6, 1, 0, 0, 0)
        assert end == datetime(2026, 7, 1, 0, 0, 0)

    def test_december_rolls_over_to_next_year(self, window):
        start, end = window(datetime(2026, 12, 31, 23, 59, 59))

        assert start == datetime(2026, 12, 1, 0, 0, 0)
        assert end == datetime(2027, 1, 1, 0, 0, 0)

    def test_defaults_to_now_when_no_reference_is_given(self, window):
        start, end = window()

        assert start.day == 1
        assert (start.hour, start.minute, start.second) == (0, 0, 0)
        assert end > start
