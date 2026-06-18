from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas import DeviceStatusSchema, ElderlyRecordSchema, OTTQuerySchema

NOW = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)


def valid_device_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "device_id": "device-001",
        "region": "south_china",
        "android_version": "11",
        "firmware_version": "2.4.1",
        "online": True,
        "error_code": None,
        "failure_rate_7d": 0.05,
        "last_seen_at": NOW,
    }
    data.update(overrides)
    return data


def test_device_status_accepts_valid_data() -> None:
    schema = DeviceStatusSchema(**valid_device_data(error_code="OTA_TIMEOUT"))

    assert schema.device_id == "device-001"
    assert schema.error_code == "OTA_TIMEOUT"


@pytest.mark.parametrize("failure_rate", [0.0, 1.0])
def test_device_status_accepts_failure_rate_boundaries(failure_rate: float) -> None:
    schema = DeviceStatusSchema(**valid_device_data(failure_rate_7d=failure_rate))

    assert schema.failure_rate_7d == failure_rate


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("device_id", "ab"),
        ("region", "   "),
        ("failure_rate_7d", -0.01),
        ("failure_rate_7d", 1.01),
        ("online", "true"),
    ],
)
def test_device_status_rejects_invalid_data(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        DeviceStatusSchema(**valid_device_data(**{field: value}))


def test_elderly_record_accepts_valid_data() -> None:
    schema = ElderlyRecordSchema(
        elder_id="elder-001",
        age=78,
        systolic_bp=135,
        diastolic_bp=82,
        has_chronic_disease=True,
        latest_alert="blood_pressure_high",
        updated_at=NOW,
    )

    assert schema.age == 78


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("elder_id", " "),
        ("age", 121),
        ("systolic_bp", -1),
        ("diastolic_bp", -1),
    ],
)
def test_elderly_record_rejects_invalid_data(field: str, value: object) -> None:
    data: dict[str, object] = {
        "elder_id": "elder-001",
        "age": 78,
        "systolic_bp": 135,
        "diastolic_bp": 82,
        "has_chronic_disease": True,
        "latest_alert": None,
        "updated_at": NOW,
    }
    data[field] = value

    with pytest.raises(ValidationError):
        ElderlyRecordSchema(**data)


def test_ott_query_accepts_valid_data_and_boundary() -> None:
    schema = OTTQuerySchema(
        query_id="query-001",
        tenant_id="tenant-001",
        query_text="直播频道持续卡顿",
        channel="tv",
        include_history=True,
        max_results=20,
    )

    assert schema.max_results == 20


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tenant_id", ""),
        ("query_text", "卡顿"),
        ("channel", "phone"),
        ("max_results", 0),
        ("max_results", 21),
    ],
)
def test_ott_query_rejects_invalid_data(field: str, value: object) -> None:
    data: dict[str, object] = {
        "query_id": "query-001",
        "tenant_id": "tenant-001",
        "query_text": "直播频道持续卡顿",
        "channel": "web",
        "include_history": False,
        "max_results": 5,
    }
    data[field] = value

    with pytest.raises(ValidationError):
        OTTQuerySchema(**data)


def test_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        DeviceStatusSchema(**valid_device_data(unexpected_field="not-allowed"))


def test_schema_rejects_missing_required_field() -> None:
    data = valid_device_data()
    del data["device_id"]

    with pytest.raises(ValidationError):
        DeviceStatusSchema(**data)
