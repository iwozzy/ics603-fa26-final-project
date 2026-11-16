import asyncio
import logging
from collections import Counter
from datetime import UTC, datetime
from uuid import uuid4

from lumiere.application.minute_limits import MinuteLimiter, minute_window
from lumiere.application.ports.unit_of_work import UnitOfWorkFactory
from lumiere.domain.access import (
    CounterKey,
    GuestContext,
    UsagePolicy,
)
from lumiere.domain.errors import SearchFailed


def admission_limits(context: GuestContext, now: datetime, policy: UsagePolicy) -> dict[CounterKey, int]:
    limits: dict[CounterKey, int] = {}
    # Preserve existing SESSION_* configuration names for the per-guest caps.
    for scope, subject, policy_scope in (("global", "all", "global"), ("guest", str(context.profile_id), "session"), ("ip", context.ip_key, "ip")):
        limits[CounterKey(scope, subject, "people_request", minute_window(now))] = getattr(policy, f"{policy_scope}_requests_per_minute")
        limits[CounterKey(scope, subject, "people_provider", now.astimezone(UTC).date().isoformat())] = getattr(policy, f"{policy_scope}_provider_daily")
        limits[CounterKey(scope, subject, "people_provider", "total")] = getattr(policy, f"{policy_scope}_provider_total")
    return limits


class UsageAdmissionService:
    """Single-process admission with bounded, idempotent asynchronous persistence."""

    def __init__(self, uow_factory: UnitOfWorkFactory, policy: UsagePolicy, *, max_pending: int = 1_024, batch_size: int = 64, flush_timeout: float = 5, retry_delay: float = 1, shutdown_timeout: float = 5, minute_limiter: MinuteLimiter | None = None) -> None:
        if min(max_pending, batch_size, flush_timeout, retry_delay, shutdown_timeout) <= 0:
            raise ValueError("accounting bounds must be positive")
        self.uow_factory = uow_factory
        self.policy = policy
        self.max_pending = max_pending
        self.batch_size = batch_size
        self.flush_timeout = flush_timeout
        self.retry_delay = retry_delay
        self.shutdown_timeout = shutdown_timeout
        self.minutes = minute_limiter if minute_limiter is not None else MinuteLimiter()
        self._confirmed: dict[CounterKey, int] = {}
        self._pending: Counter[CounterKey] = Counter()
        self._queue: asyncio.Queue[tuple[CounterKey, ...]] = asyncio.Queue(maxsize=max_pending)
        self._outstanding = 0
        self._worker: asyncio.Task[None] | None = None
        self._accepting = False
        self._closed = False
        self._writer_id = uuid4()
        self._sequence = 0
        self._day = ""

    async def start(self, now: datetime) -> None:
        if self._worker is not None or self._closed:
            raise RuntimeError("accounting already started or closed")
        day = now.astimezone(UTC).date().isoformat()
        async with asyncio.timeout(self.flush_timeout):
            async with self.uow_factory() as uow:
                counts = await uow.usage.load_counts(day)
        self._confirmed = counts
        self._day = day
        self._worker = asyncio.create_task(self._run_writer(), name="usage-accounting")
        self._accepting = True

    def check_ready(self) -> None:
        if not self._accepting or self._worker is None or self._worker.done() or self._outstanding >= self.max_pending:
            raise SearchFailed("storage")

    async def admit_and_charge(self, context: GuestContext, now: datetime) -> None:
        # No await: checking all caps, charging and enqueueing are one event-loop turn.
        self.check_ready()
        self._roll_day(now)
        limits = admission_limits(context, now, self.policy)
        persistent = {key: cap for key, cap in limits.items() if key.feature == "people_provider"}
        if any(self._confirmed.get(key, 0) + self._pending[key] >= cap for key, cap in persistent.items()):
            raise SearchFailed("quota")
        self.minutes.admit({key: cap for key, cap in limits.items() if key.feature == "people_request"}, now)
        keys = tuple(persistent)
        self._pending.update(keys)
        self._outstanding += 1
        self._queue.put_nowait(keys)

    def _roll_day(self, now: datetime) -> None:
        day = now.astimezone(UTC).date().isoformat()
        if day != self._day:
            self._confirmed = {key: count for key, count in self._confirmed.items() if key.window in ("total", day) or self._pending[key]}
            self._day = day

    async def _run_writer(self) -> None:
        while True:
            batch = [await self._queue.get()]
            while len(batch) < self.batch_size and not self._queue.empty():
                batch.append(self._queue.get_nowait())
            deltas = Counter(key for keys in batch for key in keys)
            self._sequence += 1
            counts = await self._persist(deltas)
            # Publish only after commit and UoW exit, without dropping newer charges.
            for key, delta in deltas.items():
                self._pending[key] -= delta
                if not self._pending[key]:
                    del self._pending[key]
                if key.window in ("total", self._day) or self._pending[key]:
                    self._confirmed[key] = counts[key]
                else:
                    self._confirmed.pop(key, None)
            self._outstanding -= len(batch)
            for _ in batch:
                self._queue.task_done()

    async def _persist(self, deltas: Counter[CounterKey]) -> dict[CounterKey, int]:
        while True:
            try:
                async with asyncio.timeout(self.flush_timeout):
                    return await self._flush(deltas)
            except (SearchFailed, TimeoutError):
                logging.getLogger(__name__).warning("Usage counter flush failed; retrying")
                await asyncio.sleep(self.retry_delay)

    async def _flush(self, deltas: Counter[CounterKey]) -> dict[CounterKey, int]:
        async with self.uow_factory() as uow:
            counts = await uow.usage.flush_charges(self._writer_id, self._sequence, deltas)
            await uow.commit()
        return counts

    async def drain(self) -> None:
        await self._queue.join()

    async def close(self) -> None:
        self._accepting = False
        self._closed = True
        if self._worker is None:
            return
        try:
            async with asyncio.timeout(self.shutdown_timeout):
                await self.drain()
        except TimeoutError:
            logging.getLogger(__name__).warning("Usage counter shutdown timed out; pending charges discarded")
        finally:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
