"""Import API router — CSV upload, preview, and bulk position import."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from trading.api.dependencies import get_position_repo
from trading.api.schemas import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportedPositionPreview,
    ImportPreviewResponse,
    ImportSummary,
    PositionResponse,
    TaxLotResponse,
)
from trading.core.repositories import PositionRepo
from trading.importers.registry import detect_and_parse

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import(
    file: UploadFile = File(...),
    position_repo: PositionRepo = Depends(get_position_repo),
) -> ImportPreviewResponse:
    """Upload CSV, auto-detect broker, return preview of positions to import."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files accepted")

    content = (await file.read()).decode("utf-8")

    try:
        broker_name, parsed = detect_and_parse(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Build preview with duplicate/warning detection
    previews = []
    new_count = 0
    dup_count = 0
    warn_count = 0

    for pos in parsed:
        warnings: list[str] = []
        status = "new"

        # Check for existing position with same symbol
        existing = position_repo.get_by_symbol(pos.symbol, pos.asset_class)
        if existing:
            status = "duplicate"
            dup_count += 1

        # Validation warnings
        if pos.quantity <= 0:
            warnings.append("Quantity is zero or negative")
            status = "warning"
        if pos.cost_basis <= 0:
            warnings.append("Cost basis is zero or negative")
            status = "warning"

        if status == "warning":
            warn_count += 1
        elif status == "new":
            new_count += 1

        previews.append(
            ImportedPositionPreview(
                symbol=pos.symbol,
                quantity=pos.quantity,
                cost_basis=pos.cost_basis,
                purchase_date=pos.purchase_date,
                asset_class=pos.asset_class,
                account=pos.account,
                description=pos.description,
                status=status,
                warnings=warnings,
            )
        )

    return ImportPreviewResponse(
        broker_detected=broker_name,
        positions=previews,
        summary=ImportSummary(
            total=len(previews),
            new=new_count,
            duplicates=dup_count,
            warnings=warn_count,
        ),
    )


@router.post("/commit", response_model=ImportCommitResponse)
async def commit_import(
    body: ImportCommitRequest,
    position_repo: PositionRepo = Depends(get_position_repo),
) -> ImportCommitResponse:
    """Commit previewed positions to database."""
    created = []

    for pos in body.positions:
        existing = position_repo.get_by_symbol(pos.symbol, pos.asset_class)
        if existing:
            # Add as new tax lot to existing position
            record = position_repo.add_tax_lot(
                position_id=existing.id,
                quantity=pos.quantity,
                cost_basis=pos.cost_basis,
                purchase_date=pos.purchase_date,
            )
        else:
            record = position_repo.create(
                symbol=pos.symbol,
                quantity=pos.quantity,
                cost_basis=pos.cost_basis,
                purchase_date=pos.purchase_date,
                asset_class=pos.asset_class,
            )

        if record:
            from datetime import date

            domain = position_repo.to_domain(record)
            tax_lots = [
                TaxLotResponse(
                    quantity=lot.quantity,
                    cost_basis=lot.cost_basis,
                    purchase_date=lot.purchase_date.isoformat(),
                    is_long_term=lot.is_long_term(date.today()),
                    days_to_long_term=lot.days_to_long_term(date.today()),
                )
                for lot in domain.tax_lots
            ]
            created.append(
                PositionResponse(
                    id=record.id,
                    symbol=record.symbol,
                    asset_class=record.asset_class,
                    exchange=record.exchange,
                    total_quantity=domain.total_quantity,
                    average_cost=round(domain.average_cost, 2),
                    tax_lots=tax_lots,
                    notes=record.notes,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                )
            )

    return ImportCommitResponse(
        imported=len(created),
        positions=created,
    )
