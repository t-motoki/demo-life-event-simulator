"""POST /simulate エンドポイント

受け取ったシナリオを validate() でチェックしてから simulate() に渡す。
ドメインロジックは一切変更しない。
"""

import logging

from fastapi import APIRouter, HTTPException

from src.api.schemas import (
    CashFlowRowResponse,
    SimulateRequest,
    to_domain_scenario,
    to_response,
)
from src.domain.cashflow import simulate
from src.input.validator import validate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/simulate", response_model=list[CashFlowRowResponse])
def simulate_endpoint(request: SimulateRequest) -> list[CashFlowRowResponse]:
    """シナリオを受け取り、年次キャッシュフロー一覧を返す

    エラーハンドリングの方針:
    - Pydantic ValidationError: FastAPI が自動的に HTTP 422 に変換する
    - validator.py の ValueError: HTTPException(422) に変換する
    - その他の予期しない例外: HTTPException(500) に変換する
    """
    scenario = to_domain_scenario(request)

    # validator.py のビジネスルール検証（ValueError → 422）
    try:
        validate(scenario)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # ドメインロジック実行（予期しない例外 → 500）
    try:
        rows = simulate(scenario)
    except Exception as e:
        logger.error("シミュレーション中に予期しないエラーが発生しました: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return to_response(rows)
