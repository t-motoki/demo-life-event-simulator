"""POST /generate-comment エンドポイント

受け取ったシナリオとキャッシュフロー一覧から Claude API でFPコメントを生成する。
anthropic への直接依存はこのルーターには持たせず、comment_generator に閉じ込める。
"""

import logging

from fastapi import APIRouter, HTTPException

from src.api.schemas import (
    GenerateCommentRequest,
    GenerateCommentResponse,
    to_domain_rows,
    to_domain_scenario,
)
from src.output.comment_generator import CommentGenerationError, generate_comment

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate-comment", response_model=GenerateCommentResponse)
def generate_comment_endpoint(request: GenerateCommentRequest) -> GenerateCommentResponse:
    """シナリオとキャッシュフロー一覧を受け取り、FP コメントを返す

    エラーハンドリングの方針:
    - CommentGenerationError: Claude API 障害 → HTTP 503
    - その他の予期しない例外 → HTTP 500
    """
    scenario = to_domain_scenario(request.scenario)
    rows = to_domain_rows(request.rows)

    try:
        comment = generate_comment(scenario, rows)
    except CommentGenerationError as e:
        logger.warning("Claude API 呼び出しに失敗しました: %s", e)
        raise HTTPException(status_code=503, detail=f"コメント生成サービスが利用できません: {e}")
    except Exception as e:
        logger.error("コメント生成中に予期しないエラーが発生しました: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return GenerateCommentResponse(comment=comment)
