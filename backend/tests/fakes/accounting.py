import asyncio
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from datetime import datetime
from typing import override
from uuid import UUID

from lumiere.application.ports.unit_of_work import UnitOfWorkFactory
from lumiere.application.use_cases.usage_admission import UsageAdmissionService
from lumiere.domain.access import CounterKey, UsagePolicy
from lumiere.domain.errors import SearchFailed
from tests.fakes.access import MemoryAccess, MemoryUow


@asynccontextmanager
async def running_accounting(factory: UnitOfWorkFactory, policy: UsagePolicy, now: datetime) -> AsyncGenerator[UsageAdmissionService]:
    service = UsageAdmissionService(factory, policy)
    await service.start(now)
    try:
        yield service
    finally:
        await service.close()


class ControlledAccess(MemoryAccess):
    def __init__(self) -> None:
        super().__init__()
        self.allow_flush = asyncio.Event()
        self.allow_flush.set()
        self.entered = asyncio.Event()
        self.attempts: list[int] = []
        self.failures = 0
        self.ambiguous_commits = 0
        self.opens = 0
        self.block_sequence: int | None = None

    @override
    def __call__(self) -> "ControlledUow":
        self.opens += 1
        return ControlledUow(self)


class ControlledUow(MemoryUow):
    def __init__(self, access: ControlledAccess) -> None:
        super().__init__(access)
        self.access = access
        self.is_flush = False

    @override
    async def flush_charges(self, writer_id: UUID, sequence: int, deltas: Mapping[CounterKey, int]) -> dict[CounterKey, int]:
        self.is_flush = True
        self.access.attempts.append(sequence)
        if sequence == self.access.block_sequence:
            self.access.allow_flush.clear()
        self.access.entered.set()
        await self.access.allow_flush.wait()
        if self.access.failures:
            self.access.failures -= 1
            raise SearchFailed("storage")
        return await super().flush_charges(writer_id, sequence, deltas)

    @override
    async def commit(self) -> None:
        await super().commit()
        if self.is_flush and self.access.ambiguous_commits:
            self.access.ambiguous_commits -= 1
            raise SearchFailed("storage")
