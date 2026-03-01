"""Position CRUD API router."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from trading.api.dependencies import get_position_repo
from trading.api.schemas import (
    AddTaxLotRequest,
    PositionCreateRequest,
    PositionResponse,
    PositionUpdateRequest,
    TaxLotResponse,
)
from trading.core.repositories import PositionRecord, PositionRepo

router = APIRouter(prefix="/api/positions", tags=["positions"])


def _to_response(rec: PositionRecord) -> PositionResponse:
    today = date.today()
    total_quantity = sum(lot["quantity"] for lot in rec.tax_lots)
    total_cost = sum(lot["quantity"] * lot["cost_basis"] for lot in rec.tax_lots)
    average_cost = total_cost / total_quantity if total_quantity > 0 else 0.0

    tax_lot_responses = []
    for lot in rec.tax_lots:
        purchase = date.fromisoformat(lot["purchase_date"])
        days_held = (today - purchase).days
        is_long = days_held >= 365
        days_to_lt = max(0, 365 - days_held)
        tax_lot_responses.append(
            TaxLotResponse(
                quantity=lot["quantity"],
                cost_basis=lot["cost_basis"],
                purchase_date=lot["purchase_date"],
                is_long_term=is_long,
                days_to_long_term=days_to_lt,
            )
        )

    return PositionResponse(
        id=rec.id,
        symbol=rec.symbol,
        asset_class=rec.asset_class,
        exchange=rec.exchange,
        total_quantity=total_quantity,
        average_cost=round(average_cost, 2),
        tax_lots=tax_lot_responses,
        notes=rec.notes,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


@router.get("", response_model=list[PositionResponse])
async def list_positions(
    repo: PositionRepo = Depends(get_position_repo),
) -> list[PositionResponse]:
    records = repo.list_all()
    return [_to_response(r) for r in records]


@router.post("", response_model=PositionResponse, status_code=201)
async def create_position(
    body: PositionCreateRequest,
    repo: PositionRepo = Depends(get_position_repo),
) -> PositionResponse:
    rec = repo.create(
        symbol=body.symbol.upper(),
        quantity=body.quantity,
        cost_basis=body.cost_basis,
        purchase_date=body.purchase_date,
        asset_class=body.asset_class,
        exchange=body.exchange,
        notes=body.notes,
    )
    return _to_response(rec)


@router.get("/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: int,
    repo: PositionRepo = Depends(get_position_repo),
) -> PositionResponse:
    rec = repo.get(position_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return _to_response(rec)


@router.post("/{position_id}/lots", response_model=PositionResponse)
async def add_tax_lot(
    position_id: int,
    body: AddTaxLotRequest,
    repo: PositionRepo = Depends(get_position_repo),
) -> PositionResponse:
    rec = repo.add_tax_lot(
        position_id,
        quantity=body.quantity,
        cost_basis=body.cost_basis,
        purchase_date=body.purchase_date,
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return _to_response(rec)


@router.put("/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: int,
    body: PositionUpdateRequest,
    repo: PositionRepo = Depends(get_position_repo),
) -> PositionResponse:
    rec = repo.update(position_id, notes=body.notes)
    if rec is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return _to_response(rec)


@router.delete("/{position_id}", status_code=204)
async def delete_position(
    position_id: int,
    repo: PositionRepo = Depends(get_position_repo),
) -> None:
    if not repo.delete(position_id):
        raise HTTPException(status_code=404, detail="Position not found")
