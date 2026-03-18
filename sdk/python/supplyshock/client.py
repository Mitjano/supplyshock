"""Sync and async HTTP clients for the SupplyShock API."""

from __future__ import annotations

from typing import Any

import httpx


class _CommoditiesMixin:
    """Namespace for commodity-related endpoints."""

    def __init__(self, requester):
        self._req = requester

    def prices(self, **params) -> dict[str, Any]:
        return self._req("GET", "/commodities/prices", params=params)


class _VoyagesMixin:
    """Namespace for voyage-related endpoints."""

    def __init__(self, requester):
        self._req = requester

    def list(self, **params) -> dict[str, Any]:
        return self._req("GET", "/voyages", params=params)


class _AlertsMixin:
    """Namespace for alert-related endpoints."""

    def __init__(self, requester):
        self._req = requester

    def list(self, **params) -> dict[str, Any]:
        return self._req("GET", "/alerts", params=params)


class _AsyncCommoditiesMixin:
    def __init__(self, requester):
        self._req = requester

    async def prices(self, **params) -> dict[str, Any]:
        return await self._req("GET", "/commodities/prices", params=params)


class _AsyncVoyagesMixin:
    def __init__(self, requester):
        self._req = requester

    async def list(self, **params) -> dict[str, Any]:
        return await self._req("GET", "/voyages", params=params)


class _AsyncAlertsMixin:
    def __init__(self, requester):
        self._req = requester

    async def list(self, **params) -> dict[str, Any]:
        return await self._req("GET", "/alerts", params=params)


class SupplyShockClient:
    """Synchronous SupplyShock API client.

    Usage::

        from supplyshock import SupplyShockClient

        client = SupplyShockClient(api_key="sk_...", base_url="https://api.supplyshock.io")
        prices = client.commodities.prices(commodity="oil")
        voyages = client.voyages.list(status="active")
        alerts = client.alerts.list()
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.supplyshock.io/api/v1",
        timeout: float = 30.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        self.commodities = _CommoditiesMixin(self._request)
        self.voyages = _VoyagesMixin(self._request)
        self.alerts = _AlertsMixin(self._request)

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        resp = self._client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AsyncSupplyShockClient:
    """Asynchronous SupplyShock API client.

    Usage::

        from supplyshock import AsyncSupplyShockClient

        async with AsyncSupplyShockClient(api_key="sk_...") as client:
            prices = await client.commodities.prices(commodity="oil")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.supplyshock.io/api/v1",
        timeout: float = 30.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        self.commodities = _AsyncCommoditiesMixin(self._request)
        self.voyages = _AsyncVoyagesMixin(self._request)
        self.alerts = _AsyncAlertsMixin(self._request)

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        resp = await self._client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
