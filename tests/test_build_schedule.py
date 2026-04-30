from datetime import date
from scripts.build_schedule import (
    generate_dates_for_year,
    psalms_proverbs_cycle,
    cycle_ref_for_day_index,
)


class TestGenerateDates:
    def test_normal_year(self):
        dates = list(generate_dates_for_year(2025))
        assert len(dates) == 365
        assert dates[0] == date(2025, 1, 1)
        assert dates[-1] == date(2025, 12, 31)

    def test_leap_year(self):
        dates = list(generate_dates_for_year(2028))
        assert len(dates) == 366
        assert date(2028, 2, 29) in dates


class TestPsalmsProverbsCycle:
    def test_total_count(self):
        # 시편 150편 + 잠언 31장 = 181 entries
        cycle = psalms_proverbs_cycle()
        assert len(cycle) == 181

    def test_first_is_psalm_one(self):
        cycle = psalms_proverbs_cycle()
        assert cycle[0] == ("시편", 1)

    def test_psalm_150_then_proverbs(self):
        cycle = psalms_proverbs_cycle()
        assert cycle[149] == ("시편", 150)
        assert cycle[150] == ("잠언", 1)
        assert cycle[180] == ("잠언", 31)


class TestCycleRefForDayIndex:
    def test_first_day(self):
        # day_index 0 → 시편 1
        assert cycle_ref_for_day_index(0) == "시편 1"

    def test_wraps_around(self):
        # day_index 181 → wraps back to 시편 1
        assert cycle_ref_for_day_index(181) == "시편 1"
        assert cycle_ref_for_day_index(182) == "시편 2"

    def test_proverbs(self):
        # day_index 150 → 잠언 1
        assert cycle_ref_for_day_index(150) == "잠언 1"
