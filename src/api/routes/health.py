"""GET /health エンドポイント

フロントエンドがバックエンドの起動を確認するための疎通エンドポイント。
副作用なし・認証なし。
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
