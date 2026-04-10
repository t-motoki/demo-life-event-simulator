# 設計: 育休中の収入減

## 概要

`BirthEvent` に育休フィールドを追加し、育休取得年の給与収入に減額率を適用する。
年金収入には適用しない。育休期間は `BirthEvent.year` を起点に N 年間。

---

## 変更ファイル一覧

| ファイル | 変更種別 | 理由 |
| -------- | -------- | ---- |
| `src/domain/models.py` | 変更 | `BirthEvent` に育休フィールドを追加 |
| `src/domain/cashflow.py` | 変更 | `_calc_income` に育休減額を適用するロジックを追加 |
| `src/input/yaml_loader.py` | 変更 | `birth` イベントの parse で育休フィールドを読み込む |
| `src/input/validator.py` | 変更 | 育休フィールドの値域バリデーションを追加 |
| `tests/domain/test_cashflow_maternity.py` | 新規 | tester 作成済みの仕様を実装する（テストファイル本体） |

---

## データモデル

### `BirthEvent` の変更（`src/domain/models.py`）

```python
@dataclass
class BirthEvent(LifeEvent):
    child_count: int = 1
    client_maternity_rate: float = 1.0   # 本人育休中の収入率（1.0=取得しない）
    client_maternity_years: int = 0      # 本人育休期間（年数）
    spouse_maternity_rate: float = 1.0   # 配偶者育休中の収入率（1.0=取得しない）
    spouse_maternity_years: int = 0      # 配偶者育休期間（年数）
```

フィールド名の選択根拠:
- `client_maternity_rate` / `spouse_maternity_rate` は「誰の・何の率か」を 1 語で表す
- `_years` を分離するのは「率」と「期間」が独立して設定される概念であるため

---

## インターフェース

### `_calc_income` の変更（`src/domain/cashflow.py`）

現行シグネチャを変えず、呼び出し側で育休係数を乗算する方式を採用する。
`_calc_income` 自体はシンプルに「その年の基準給与収入」を返し続ける。

育休減額は `simulate` 内の収入計算ブロックで行う。

```python
def _maternity_rate(events: list[LifeEvent], target: str, year: int) -> float:
    """指定年に有効な育休減額率を返す。複数の BirthEvent がある場合は最小値を使う。

    Args:
        events: イベント一覧
        target: "client" または "spouse"
        year: 西暦年

    Returns:
        収入率（0.0〜1.0）。育休なしなら 1.0
    """
```

戻り値が 1.0 のとき「育休なし」なので既存挙動と一致する。

`simulate` 内の収入計算ブロックは以下のように変わる:

```python
# --- 収入計算 ---
client_rate = _maternity_rate(scenario.events, "client", year)
income = int(_calc_income(scenario.client, year, scenario.start_year) * client_rate)
income += _calc_pension(scenario.client, year, scenario.start_year)

if scenario.spouse is not None:
    spouse_rate = _maternity_rate(scenario.events, "spouse", year)
    income += int(_calc_income(scenario.spouse, year, scenario.start_year) * spouse_rate)
    income += _calc_pension(scenario.spouse, year, scenario.start_year)
```

`_calc_pension` には係数を乗算しない（仕様: 年金収入には育休減額を適用しない）。

---

## `_maternity_rate` の詳細ロジック

```
有効な育休 = BirthEvent.year <= year < BirthEvent.year + maternity_years
かつ maternity_rate < 1.0
```

複数の `BirthEvent` が同じ年に重なる場合（双子・連続出産など）は最小の率を採用する。
これは「最も収入が少なくなる」保守的な計算であり、FP 的に安全側の推計となる。

```python
def _maternity_rate(events: list[LifeEvent], target: str, year: int) -> float:
    rate = 1.0
    for event in events:
        if not isinstance(event, BirthEvent):
            continue
        if target == "client":
            m_rate = event.client_maternity_rate
            m_years = event.client_maternity_years
        else:
            m_rate = event.spouse_maternity_rate
            m_years = event.spouse_maternity_years
        if m_rate < 1.0 and event.year <= year < event.year + m_years:
            rate = min(rate, m_rate)
    return rate
```

---

## yaml_loader の変更（`src/input/yaml_loader.py`）

`_parse_event` の `birth` ブランチを以下に変更する:

```python
case "birth":
    return BirthEvent(
        year=year,
        child_count=data.get("child_count", 1),
        client_maternity_rate=data.get("client_maternity_rate", 1.0),
        client_maternity_years=data.get("client_maternity_years", 0),
        spouse_maternity_rate=data.get("spouse_maternity_rate", 1.0),
        spouse_maternity_years=data.get("spouse_maternity_years", 0),
    )
```

省略時はすべてデフォルト値になるので、既存の `scenario.yaml` は無変更で動作する（後方互換）。

---

## validator の変更（`src/input/validator.py`）

`BirthEvent` をインポートし、以下のチェックを追加する:

```python
from src.domain.models import BirthEvent, HousingEvent, Scenario

# validate() 内
for event in scenario.events:
    if isinstance(event, BirthEvent):
        for attr, label in [
            ("client_maternity_rate", "本人育休収入率"),
            ("spouse_maternity_rate", "配偶者育休収入率"),
        ]:
            rate = getattr(event, attr)
            if not (0.0 <= rate <= 1.0):
                raise ValueError(
                    f"{label}が不正です（値: {rate}）。0.0〜1.0の範囲で入力してください。"
                )
        for attr, label in [
            ("client_maternity_years", "本人育休期間"),
            ("spouse_maternity_years", "配偶者育休期間"),
        ]:
            years = getattr(event, attr)
            if years < 0:
                raise ValueError(
                    f"{label}が不正です（値: {years}年）。0以上の値を入力してください。"
                )
```

---

## `scenario.yaml` の変更案

育休を使う場合の `birth` イベント記述例:

```yaml
events:
  - type: birth
    year: 2026
    child_count: 1
    # 育休フィールドはすべて省略可能（デフォルト: 取得しない）
    client_maternity_rate: 0.5     # 本人: 出産年から収入50%
    client_maternity_years: 1      # 本人: 1年間
    spouse_maternity_rate: 0.6     # 配偶者: 出産年から収入60%
    spouse_maternity_years: 2      # 配偶者: 2年間
```

育休を取らない場合（従来どおり）:

```yaml
  - type: birth
    year: 2026
    child_count: 1
    # 育休フィールドは省略する（rate=1.0, years=0 が暗黙で設定される）
```

`rate=1.0` と書いても動作するが、「取得しない」という意図は省略の方が明確に伝わる。

---

## 依存関係

```
yaml_loader.py  -->  models.py (BirthEvent の新フィールドを参照)
validator.py    -->  models.py (BirthEvent をインポート追加)
cashflow.py     -->  models.py (BirthEvent の新フィールドを参照)
```

依存の方向は既存と変わらない（インフラ → ドメイン）。

---

## 設計判断の根拠

### 判断1: `_calc_income` のシグネチャを変えない

育休係数を `_calc_income` の引数に追加する案もある。しかしこの関数は「クライアントの基準給与収入を計算する」責務を持ち、育休は「その年に外部から加えられる減額」である。関数の責務を分離するため、係数は呼び出し側（`simulate`）で乗算する設計を選んだ。

### 判断2: 新しい関数 `_maternity_rate` を切り出す

`simulate` 内にインラインで書くことも可能だが、テストのターゲットが「育休なし=1.0を返す」「複数BirthEventで最小値」など複数あるため、テスト可能な単独関数として切り出す。

### 判断3: `BirthEvent` に直接フィールドを追加する（別イベントにしない）

`MaternityLeaveEvent` を新設する案は、出産との関係が YAML 上で暗黙になりバグを生みやすい（どの出産に対応するか管理が複雑）。育休は出産と 1:1 で結びつくため `BirthEvent` の属性として持つのが最もシンプル。

### 判断4: デフォルト rate=1.0, years=0

「取得しない」を「rate=0.0」ではなく「rate=1.0」で表現するのは、「1.0 × 収入 = 変化なし」という計算上の自然さによる。`years=0` のとき範囲条件 `year < event.year + 0` が常に偽になるため、`rate` の値にかかわらず育休が発動しない。

---

## 実装者へのノート

1. `_maternity_rate` の条件は `m_rate < 1.0 and event.year <= year < event.year + m_years` の順で評価する。`m_years=0` のとき後半の条件が常に偽になるので `m_rate` の確認は不要だが、ショートサーキット評価で先に書く方が意図が明確。

2. `int()` の切り捨て誤差: `_calc_income` がすでに `int()` を使っており（`RAISE_RATE` ブランチ）、育休率の乗算でも `int()` で切り捨てる。FP 計算では円未満の誤差は許容範囲。`round()` に変えると既存テストが壊れる可能性があるため、`int()` で統一する。

3. テストケース「rate=1.0 は取得しない扱い」の実装: `_maternity_rate` が 1.0 を返すとき、`int(income * 1.0)` は `income` と一致する（浮動小数点誤差が出ないよう、テストは小さい整数値で書くことを推奨）。

4. 複数の `BirthEvent` を持つシナリオは現行テストには含まれないが、`_maternity_rate` は複数イベントに対応している。将来テストを追加する際の留意点として、最小率を返すのが正しい挙動。

5. `validator.py` へのインポート追加を忘れると `isinstance` チェックが通らず、バリデーションが無音でスキップされる。必ず `BirthEvent` を import リストに加えること。
