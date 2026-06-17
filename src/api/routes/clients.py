"""CRUD エンドポイント: /clients

クライアントデータの保存・呼び出し・更新・削除を提供する。
Repository が ValueError を送出 → HTTPException(404) に変換する。
"""

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_client_repository
from src.api.schemas import ClientListItem, ClientResponse, ClientSaveRequest
from src.db.client_repository import ClientRepository

router = APIRouter()


@router.post("/clients", response_model=ClientResponse, status_code=201)
def create_client(
    request: ClientSaveRequest,
    repo: ClientRepository = Depends(get_client_repository),
) -> ClientResponse:
    """クライアントを新規作成する。"""
    record = repo.create(request.name, request.scenario)
    return ClientResponse(
        id=record.id,
        name=record.name,
        scenario=record.scenario,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/clients", response_model=list[ClientListItem])
def list_clients(
    repo: ClientRepository = Depends(get_client_repository),
) -> list[ClientListItem]:
    """クライアント一覧を返す（scenario を含まない）。"""
    summaries = repo.list_all()
    return [
        ClientListItem(
            id=s.id,
            name=s.name,
            updated_at=s.updated_at,
        )
        for s in summaries
    ]


@router.get("/clients/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: int,
    repo: ClientRepository = Depends(get_client_repository),
) -> ClientResponse:
    """指定 ID のクライアントを返す。存在しなければ 404。"""
    record = repo.get(client_id)
    if record is None:
        raise HTTPException(status_code=404, detail="クライアントが見つかりません")
    return ClientResponse(
        id=record.id,
        name=record.name,
        scenario=record.scenario,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.put("/clients/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int,
    request: ClientSaveRequest,
    repo: ClientRepository = Depends(get_client_repository),
) -> ClientResponse:
    """指定 ID のクライアントを更新する。存在しなければ 404。"""
    try:
        record = repo.update(client_id, request.name, request.scenario)
    except ValueError:
        raise HTTPException(status_code=404, detail="クライアントが見つかりません")
    return ClientResponse(
        id=record.id,
        name=record.name,
        scenario=record.scenario,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.delete("/clients/{client_id}", status_code=204)
def delete_client(
    client_id: int,
    repo: ClientRepository = Depends(get_client_repository),
) -> None:
    """指定 ID のクライアントを削除する。存在しなければ 404。"""
    try:
        repo.delete(client_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="クライアントが見つかりません")
