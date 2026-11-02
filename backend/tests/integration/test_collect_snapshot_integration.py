"""Integration tests for CollectSnapshot through the composition root.

Verifies the complete production collection flow:
build_container() → real CPU/Memory adapters → CollectSnapshot → REST /api/v1/snapshot
"""

import pytest
from httpx import ASGITransport, AsyncClient

from monitor.composition import build_container
from monitor.config import Settings
from monitor.presentation.api.app import create_app
from monitor.presentation.api.deps import get_snapshot_provider
from monitor.presentation.api.schemas import SnapshotResponse
from monitor.presentation.ws.protocol import GroupStateOk, GroupStateUnavailable

pytestmark = pytest.mark.integration


class TestCollectSnapshotIntegration:
    """Integration tests for the real adapter → CollectSnapshot → REST flow."""

    async def test_snapshot_endpoint_with_real_adapters(self) -> None:
        """The snapshot endpoint works with real CPU/memory adapters wired through composition."""
        container = build_container(Settings())
        app = create_app()
        app.dependency_overrides[get_snapshot_provider] = lambda: container.snapshot_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/snapshot")

        # HTTP layer verification
        assert response.status_code == 200

        # Schema validation via Pydantic response model
        snapshot = SnapshotResponse(**response.json())

        # Response structure validation
        assert snapshot.ts >= 0
        assert "cpu" in snapshot.groups
        assert "memory" in snapshot.groups

        # CPU group structure validation (ok or unavailable)
        cpu_group = snapshot.groups["cpu"]
        assert isinstance(cpu_group, (GroupStateOk, GroupStateUnavailable))
        if isinstance(cpu_group, GroupStateOk):
            assert cpu_group.status == "ok"
            assert "value" in cpu_group.model_dump()
            value = cpu_group.value
            if value is not None:
                assert "cpu_total" in value
                assert 0 <= value["cpu_total"] <= 100  # CPU percentage
                assert "load_average" in value
                assert "core_count" in value
                assert value["core_count"] >= 1
        else:
            assert cpu_group.status == "unavailable"
            assert cpu_group.kind is not None
            assert cpu_group.reason is not None

        # Memory group structure validation (ok or unavailable)
        memory_group = snapshot.groups["memory"]
        assert isinstance(memory_group, (GroupStateOk, GroupStateUnavailable))
        if isinstance(memory_group, GroupStateOk):
            assert memory_group.status == "ok"
            assert "value" in memory_group.model_dump()
            value = memory_group.value
            if value is not None:
                assert "total" in value
                assert "available" in value
                assert "used_percent" in value
                assert value["total"] >= 0
                assert value["available"] >= 0
                assert 0 <= value["used_percent"] <= 100
        else:
            assert memory_group.status == "unavailable"
            assert memory_group.kind is not None
            assert memory_group.reason is not None

    async def test_snapshot_endpoint_timestamps_are_valid(self) -> None:
        """Snapshot timestamps conform to the REST contract."""
        container = build_container(Settings())
        app = create_app()
        app.dependency_overrides[get_snapshot_provider] = lambda: container.snapshot_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/snapshot")

        assert response.status_code == 200
        snapshot = SnapshotResponse(**response.json())

        # Unix epoch milliseconds, positive
        assert snapshot.ts > 0
