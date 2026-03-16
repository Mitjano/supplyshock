"""Tests for vessel API endpoints (Issues #8, #9, #10)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from datetime import datetime, timezone


def _make_user(plan: str = "pro") -> dict:
    return {"sub": "user_123", "email": "test@example.com", "public_metadata": {"plan": plan}}


def _make_vessel_row(
    mmsi: int = 123456789,
    lat: float = 51.5,
    lng: float = -0.1,
    vessel_type: str = "tanker",
):
    """Create a mock DB row mapping."""
    return {
        "mmsi": mmsi,
        "imo": 9876543,
        "vessel_name": "TEST VESSEL",
        "vessel_type": vessel_type,
        "latitude": lat,
        "longitude": lng,
        "speed_knots": 12.5,
        "course": 180.0,
        "heading": 179.0,
        "destination": "Rotterdam",
        "eta": datetime(2026, 4, 1, tzinfo=timezone.utc),
        "draught": 10.2,
        "flag_country": "NL",
        "cargo_type": "70",
        "time": datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
    }


# ── Tests: GET /vessels (Issue #8) ──

@pytest.mark.asyncio
async def test_vessels_returns_bbox_filtered():
    """Vessel list endpoint should filter by bounding box."""
    from api.v1.vessels import list_vessels

    row = _make_vessel_row(lat=50.0, lng=5.0)
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [row]

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await list_vessels(
        bbox="-10,35,40,60",
        vessel_type=None,
        limit=500,
        user=_make_user(),
        db=mock_db,
    )

    assert "data" in response
    assert len(response["data"]) == 1
    assert response["data"][0]["mmsi"] == 123456789
    assert response["data"][0]["latitude"] == 50.0


@pytest.mark.asyncio
async def test_vessels_invalid_bbox():
    """Invalid bbox format should return 400."""
    from api.v1.vessels import list_vessels

    mock_db = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await list_vessels(bbox="invalid", vessel_type=None, limit=500, user=_make_user(), db=mock_db)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_vessels_type_filter():
    """Vessel list should accept vessel_type filter."""
    from api.v1.vessels import list_vessels

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await list_vessels(
        bbox=None, vessel_type="tanker", limit=100, user=_make_user(), db=mock_db,
    )

    assert response["data"] == []
    # Verify the query included vessel_type in params
    call_args = mock_db.execute.call_args
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
    assert params["vessel_type"] == "tanker"


# ── Tests: GET /vessels/{mmsi} (Issue #9) ──

@pytest.mark.asyncio
async def test_vessel_detail_found():
    """Vessel detail should return full data for known MMSI."""
    from api.v1.vessels import get_vessel_detail

    row = _make_vessel_row()
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = row

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await get_vessel_detail(mmsi=123456789, user=_make_user(), db=mock_db)

    assert response["data"]["mmsi"] == 123456789
    assert response["data"]["vessel_name"] == "TEST VESSEL"
    assert response["data"]["destination"] == "Rotterdam"


@pytest.mark.asyncio
async def test_vessel_detail_404():
    """Vessel detail should return 404 for unknown MMSI."""
    from api.v1.vessels import get_vessel_detail

    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await get_vessel_detail(mmsi=999999999, user=_make_user(), db=mock_db)

    assert exc_info.value.status_code == 404


# ── Tests: GET /vessels/{mmsi}/trail (Issue #10) ──

@pytest.mark.asyncio
async def test_vessel_trail_sorted():
    """Trail should return positions sorted chronologically."""
    from api.v1.vessels import get_vessel_trail

    rows = [
        {
            "mmsi": 123456789,
            "latitude": 51.0, "longitude": -0.1,
            "speed_knots": 10.0, "course": 90.0,
            "time": datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
        },
        {
            "mmsi": 123456789,
            "latitude": 51.5, "longitude": 0.0,
            "speed_knots": 12.0, "course": 95.0,
            "time": datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
        },
    ]

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = rows

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await get_vessel_trail(mmsi=123456789, hours=24, user=_make_user(), db=mock_db)

    assert len(response["data"]) == 2
    # Verify chronological order (oldest first)
    assert response["data"][0]["time"] < response["data"][1]["time"]


@pytest.mark.asyncio
async def test_vessel_trail_max_hours():
    """Trail should cap at 168 hours (enforced by Query param)."""
    # The FastAPI Query(le=168) enforces this at the framework level.
    # We just verify the function accepts the max value.
    from api.v1.vessels import get_vessel_trail

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await get_vessel_trail(mmsi=123456789, hours=168, user=_make_user(), db=mock_db)
    assert response["data"] == []
