from fastapi import APIRouter

from app.schemas import DeviceStatusSchema, ElderlyRecordSchema, OTTQuerySchema

router = APIRouter()


@router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "tms-agent-phase0-day1"}


@router.post("/api/v1/device-status", tags=["runtime-input"])
async def accept_device_status(payload: DeviceStatusSchema) -> dict[str, object]:
    return {"status": "accepted", "data": payload}


@router.post("/api/v1/elderly-records", tags=["runtime-input"])
async def accept_elderly_record(payload: ElderlyRecordSchema) -> dict[str, object]:
    return {"status": "accepted", "data": payload}


@router.post("/api/v1/ott-queries", tags=["runtime-input"])
async def accept_ott_query(payload: OTTQuerySchema) -> dict[str, object]:
    return {"status": "accepted", "data": payload}
