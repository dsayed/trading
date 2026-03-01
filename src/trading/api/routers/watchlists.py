"""Watchlist API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from trading.api.dependencies import get_watchlist_repo
from trading.api.schemas import (
    WatchlistCreateRequest,
    WatchlistResponse,
    WatchlistUpdateRequest,
)
from trading.core.repositories import WatchlistRepo

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])


def _to_response(wl: object) -> WatchlistResponse:
    return WatchlistResponse(
        id=wl.id,  # type: ignore[attr-defined]
        name=wl.name,  # type: ignore[attr-defined]
        symbols=wl.symbols,  # type: ignore[attr-defined]
        created_at=wl.created_at,  # type: ignore[attr-defined]
        updated_at=wl.updated_at,  # type: ignore[attr-defined]
    )


@router.get("", response_model=list[WatchlistResponse])
async def list_watchlists(
    repo: WatchlistRepo = Depends(get_watchlist_repo),
) -> list[WatchlistResponse]:
    return [_to_response(wl) for wl in repo.list_all()]


@router.post("", response_model=WatchlistResponse, status_code=201)
async def create_watchlist(
    body: WatchlistCreateRequest,
    repo: WatchlistRepo = Depends(get_watchlist_repo),
) -> WatchlistResponse:
    wl = repo.create(body.name, body.symbols)
    return _to_response(wl)


@router.get("/{watchlist_id}", response_model=WatchlistResponse)
async def get_watchlist(
    watchlist_id: int,
    repo: WatchlistRepo = Depends(get_watchlist_repo),
) -> WatchlistResponse:
    wl = repo.get(watchlist_id)
    if wl is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return _to_response(wl)


@router.put("/{watchlist_id}", response_model=WatchlistResponse)
async def update_watchlist(
    watchlist_id: int,
    body: WatchlistUpdateRequest,
    repo: WatchlistRepo = Depends(get_watchlist_repo),
) -> WatchlistResponse:
    wl = repo.update(watchlist_id, name=body.name, symbols=body.symbols)
    if wl is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return _to_response(wl)


@router.delete("/{watchlist_id}", status_code=204)
async def delete_watchlist(
    watchlist_id: int,
    repo: WatchlistRepo = Depends(get_watchlist_repo),
) -> None:
    if not repo.delete(watchlist_id):
        raise HTTPException(status_code=404, detail="Watchlist not found")
