"""教育費計算のテスト"""

import pytest

from src.domain.education import EDUCATION_COST_TABLE, get_education_cost
from src.domain.models import EducationEvent, SchoolType


def _make_event(child_birth_year: int, **kwargs) -> EducationEvent:
    defaults = dict(
        year=child_birth_year,
        child_birth_year=child_birth_year,
        kindergarten=SchoolType.PUBLIC,
        elementary=SchoolType.PUBLIC,
        junior_high=SchoolType.PUBLIC,
        high_school=SchoolType.PUBLIC,
        university=SchoolType.PUBLIC,
    )
    defaults.update(kwargs)
    return EducationEvent(**defaults)


class TestKindergarten:
    def test_kindergarten_starts_at_age_3(self):
        """幼稚園入学年（3歳）に教育費が発生する"""
        # 2020年生まれ → 2023年に3歳
        event = _make_event(child_birth_year=2020)
        cost = get_education_cost(event, 2023)
        assert cost == EDUCATION_COST_TABLE["kindergarten"][SchoolType.PUBLIC]

    def test_kindergarten_ends_at_age_5(self):
        """幼稚園は5歳まで（5歳の年は費用あり、6歳では次の段階）"""
        event = _make_event(child_birth_year=2020)
        assert get_education_cost(event, 2025) == EDUCATION_COST_TABLE["kindergarten"][SchoolType.PUBLIC]

    def test_kindergarten_private_vs_public(self):
        """私立幼稚園の単価は公立より高い"""
        birth_year = 2020
        public_event = _make_event(birth_year, kindergarten=SchoolType.PUBLIC)
        private_event = _make_event(birth_year, kindergarten=SchoolType.PRIVATE)
        year = 2023  # 3歳
        assert get_education_cost(private_event, year) > get_education_cost(public_event, year)


class TestElementary:
    def test_elementary_starts_at_age_6(self):
        """小学校入学年（6歳）に教育費が発生する"""
        event = _make_event(child_birth_year=2020)
        cost = get_education_cost(event, 2026)  # 6歳
        assert cost == EDUCATION_COST_TABLE["elementary"][SchoolType.PUBLIC]

    def test_elementary_private_cost(self):
        """私立小学校の単価を確認"""
        event = _make_event(child_birth_year=2020, elementary=SchoolType.PRIVATE)
        cost = get_education_cost(event, 2026)
        assert cost == EDUCATION_COST_TABLE["elementary"][SchoolType.PRIVATE]


class TestJuniorHigh:
    def test_junior_high_starts_at_age_12(self):
        """中学校入学年（12歳）に教育費が発生する"""
        event = _make_event(child_birth_year=2020)
        cost = get_education_cost(event, 2032)  # 12歳
        assert cost == EDUCATION_COST_TABLE["junior_high"][SchoolType.PUBLIC]


class TestHighSchool:
    def test_high_school_starts_at_age_15(self):
        """高校入学年（15歳）に教育費が発生する"""
        event = _make_event(child_birth_year=2020)
        cost = get_education_cost(event, 2035)  # 15歳
        assert cost == EDUCATION_COST_TABLE["high_school"][SchoolType.PUBLIC]


class TestUniversity:
    def test_university_starts_at_age_18(self):
        """大学入学年（18歳）に教育費が発生する"""
        event = _make_event(child_birth_year=2020)
        cost = get_education_cost(event, 2038)  # 18歳
        assert cost == EDUCATION_COST_TABLE["university"][SchoolType.PUBLIC]

    def test_university_ends_at_age_21(self):
        """大学は21歳まで（21歳の年は費用あり）"""
        event = _make_event(child_birth_year=2020)
        cost = get_education_cost(event, 2041)  # 21歳
        assert cost == EDUCATION_COST_TABLE["university"][SchoolType.PUBLIC]

    def test_university_private_cost(self):
        """私立大学の単価"""
        event = _make_event(child_birth_year=2020, university=SchoolType.PRIVATE)
        cost = get_education_cost(event, 2038)
        assert cost == EDUCATION_COST_TABLE["university"][SchoolType.PRIVATE]


class TestGraduated:
    def test_no_cost_after_university(self):
        """大学卒業後（22歳以降）は教育費が0"""
        event = _make_event(child_birth_year=2020)
        cost_age22 = get_education_cost(event, 2042)  # 22歳
        assert cost_age22 == 0

    def test_no_cost_before_kindergarten(self):
        """幼稚園入学前（2歳以下）は教育費が0"""
        event = _make_event(child_birth_year=2020)
        cost_age2 = get_education_cost(event, 2022)  # 2歳
        assert cost_age2 == 0


class TestCostTable:
    def test_private_costs_higher_than_public(self):
        """全ての段階で私立費用 >= 公立費用"""
        for stage in ["kindergarten", "elementary", "junior_high", "high_school", "university"]:
            public_cost = EDUCATION_COST_TABLE[stage][SchoolType.PUBLIC]
            private_cost = EDUCATION_COST_TABLE[stage][SchoolType.PRIVATE]
            assert private_cost >= public_cost, f"{stage}: 私立費用が公立以下になっています"
