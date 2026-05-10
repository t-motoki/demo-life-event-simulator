"""POST /download-pdf エンドポイント

受け取ったシナリオとキャッシュフロー一覧から WeasyPrint で PDF を生成し、
バイナリレスポンスとして返す。
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from src.api.schemas import (
    DownloadPdfRequest,
    to_domain_rows,
    to_domain_scenario,
)
from src.output.pdf_writer import PdfGenerationError, generate_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/download-pdf")
def download_pdf_endpoint(request: DownloadPdfRequest) -> Response:
    """シナリオとキャッシュフロー一覧を受け取り、PDF バイナリを返す

    エラーハンドリングの方針:
    - PdfGenerationError → HTTP 500
    - Pydantic ValidationError は FastAPI が自動で 422 に変換する
    """
    scenario = to_domain_scenario(request.scenario)
    rows = to_domain_rows(request.rows)

    try:
        pdf_bytes = generate_pdf(scenario, rows, fp_comment=request.fp_comment)
    except PdfGenerationError as e:
        logger.error("PDF 生成に失敗しました: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF 生成に失敗しました: {e}")
    except Exception as e:
        logger.error("PDF 生成中に予期しないエラーが発生しました: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    today = datetime.now().strftime("%Y%m%d")
    filename = f"cf_simulation_{today}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
