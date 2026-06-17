"""FastAPI アプリケーション定義

CUI（src/main.py）と並行して動作する Web API エントリポイント。
どちらも同じ simulate() を呼ぶことで、UI が変わっても計算結果が同一であることを保証する。
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import clients, comment, health, pdf, simulate

app = FastAPI(
    title="ライフイベント家計シミュレーター API",
    description="FP が Next.js フロントエンドからシミュレーションを実行するための REST API",
    version="1.0.0",
)

# CORS: 環境変数 LES_CORS_ORIGINS でカンマ区切りの複数オリジンを指定可能
cors_origins_str = os.environ.get("LES_CORS_ORIGINS", "http://localhost:3000")
cors_origins = [o.strip() for o in cors_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(health.router)
app.include_router(simulate.router)
app.include_router(comment.router)
app.include_router(pdf.router)
app.include_router(clients.router)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("LES_PORT", "49152"))
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=port, reload=True)
