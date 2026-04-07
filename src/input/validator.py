"""入力バリデーションモジュール"""

from src.domain.models import HousingEvent, Scenario


def validate(scenario: Scenario) -> None:
    """シナリオの入力値を検証する

    Args:
        scenario: 検証対象のシナリオ

    Raises:
        ValueError: バリデーションエラーが発生した場合
    """
    client = scenario.client

    # クライアントの年齢チェック
    if not (0 <= client.age <= 100):
        raise ValueError(
            f"本人の年齢が不正です（値: {client.age}）。0〜100の範囲で入力してください。"
        )

    # end_ageのチェック
    if scenario.end_age <= client.age:
        raise ValueError(
            f"シミュレーション終了年齢（{scenario.end_age}）は"
            f"本人の現在年齢（{client.age}）より大きい値を指定してください。"
        )

    # 貯蓄初期値チェック
    if scenario.savings_initial < 0:
        raise ValueError(
            f"貯蓄初期残高が不正です（値: {scenario.savings_initial}）。0以上の値を入力してください。"
        )

    # 配偶者の年齢チェック
    if scenario.spouse is not None:
        spouse_age = scenario.spouse.age
        if not (0 <= spouse_age <= 100):
            raise ValueError(
                f"配偶者の年齢が不正です（値: {spouse_age}）。0〜100の範囲で入力してください。"
            )

    # 住宅ローンのチェック
    for event in scenario.events:
        if isinstance(event, HousingEvent):
            if event.down_payment >= event.price:
                raise ValueError(
                    f"頭金（{event.down_payment:,}円）が物件価格（{event.price:,}円）以上になっています。"
                    "頭金は物件価格未満の値を指定してください。"
                )
            if not (0 <= event.interest_rate <= 1):
                raise ValueError(
                    f"住宅ローン金利が不正です（値: {event.interest_rate}）。0〜1の範囲で入力してください。"
                )
            if not (1 <= event.loan_years <= 50):
                raise ValueError(
                    f"住宅ローン借入期間が不正です（値: {event.loan_years}年）。1〜50の範囲で入力してください。"
                )
            # ローン完済年齢チェック
            age_at_purchase = client.age + (event.year - scenario.start_year)
            age_at_payoff = age_at_purchase + event.loan_years
            if age_at_payoff >= client.retirement_age:
                raise ValueError(
                    f"住宅ローンの完済年齢（{age_at_payoff}歳）が"
                    f"退職年齢（{client.retirement_age}歳）以上になっています。"
                    "ローン年数を短くするか、退職年齢を引き上げてください。"
                )
