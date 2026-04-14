"""FastAPI アプリケーション定義

CUI（src/main.py）と並行して動作する Web API エントリポイント。
どちらも同じ simulate() を呼ぶことで、UI が変わっても計算結果が同一であることを保証する。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import health, simulate

app = FastAPI(
    title="ライフイベント家計シミュレーター API",
    description="FP が Next.js フロントエンドからシミュレーションを実行するための REST API",
    version="1.0.0",
)

# Next.js ローカル開発サーバーからのリクエストを許可する
# 将来別オリジンを追加する場合は allow_origins にリストで追記する
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(health.router)
app.include_router(simulate.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
