"""教育費標準単価テーブルと年次計算モジュール

単価は文科省データを仮値として使用している。
TODO: FPに確認（仮値）- 実際の計算に使用する前にFPと合意が必要
"""

from src.domain.models import EducationEvent, SchoolType


# 教育費標準単価テーブル（年間・円）
# 出典: 文科省データを仮値として使用
# TODO: FPに確認（仮値）
EDUCATION_COST_TABLE: dict[str, dict[SchoolType, int]] = {
    "kindergarten": {
        SchoolType.PUBLIC: 160_000,
        SchoolType.PRIVATE: 308_000,
    },
    "elementary": {
        SchoolType.PUBLIC: 352_000,
        SchoolType.PRIVATE: 1_666_000,
    },
    "junior_high": {
        SchoolType.PUBLIC: 538_000,
        SchoolType.PRIVATE: 1_436_000,
    },
    "high_school": {
        SchoolType.PUBLIC: 512_000,
        SchoolType.PRIVATE: 1_054_000,
    },
    "university": {
        SchoolType.PUBLIC: 1_076_000,
        SchoolType.PRIVATE: 1_350_000,
    },
}

# 各就学段階の開始年齢と期間
# (開始年齢, 期間年数)
SCHOOL_STAGES: list[tuple[str, int, int]] = [
    ("kindergarten", 3, 3),   # 幼稚園: 3歳から3年間
    ("elementary",   6, 6),   # 小学校: 6歳から6年間
    ("junior_high",  12, 3),  # 中学校: 12歳から3年間
    ("high_school",  15, 3),  # 高校:   15歳から3年間
    ("university",   18, 4),  # 大学:   18歳から4年間
]


def get_education_cost(event: EducationEvent, year: int) -> int:
    """指定年の教育費を返す（円）

    子どもの年齢を算出し、どの就学段階にあるかを判定して費用を返す。

    Args:
        event: 教育イベント（子どもの生まれ年・各段階の公立/私立選択）
        year: 西暦年

    Returns:
        当該年の教育費（円）。就学年齢外は0。
    """
    child_age = year - event.child_birth_year  # その年の誕生日以降の年齢

    stage_type_map: dict[str, SchoolType] = {
        "kindergarten": event.kindergarten,
        "elementary":   event.elementary,
        "junior_high":  event.junior_high,
        "high_school":  event.high_school,
        "university":   event.university,
    }

    for stage_name, start_age, duration in SCHOOL_STAGES:
        if start_age <= child_age < start_age + duration:
            school_type = stage_type_map[stage_name]
            return EDUCATION_COST_TABLE[stage_name][school_type]

    return 0
