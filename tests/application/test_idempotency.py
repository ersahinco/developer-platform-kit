from __future__ import annotations

from application.idempotency import (
    IdempotencyBeginResult,
    begin_idempotent_request,
)


class _Repo:
    def __init__(self, results: list[IdempotencyBeginResult]) -> None:
        self._results = results
        self.calls = 0

    def begin(self, *, key: str, request_hash: str) -> IdempotencyBeginResult:
        self.calls += 1
        if self.calls <= len(self._results):
            return self._results[self.calls - 1]
        return self._results[-1]

    def complete(
        self,
        *,
        key: str,
        response_status_code: int,
        response_payload: dict[str, object],
    ) -> None:
        return None

    def fail(self, *, key: str, error: str) -> None:
        return None


def test_begin_idempotent_request_retries_processing_until_terminal(
    monkeypatch,
) -> None:
    repo = _Repo(
        [
            IdempotencyBeginResult(status="processing"),
            IdempotencyBeginResult(status="processing"),
            IdempotencyBeginResult(status="started"),
        ]
    )
    sleeps: list[float] = []
    monotonic_values = iter([10.0, 10.1, 10.2])

    monkeypatch.setattr("application.idempotency.time.sleep", sleeps.append)
    monkeypatch.setattr(
        "application.idempotency.time.monotonic",
        lambda: next(monotonic_values),
    )

    result = begin_idempotent_request(
        idempotency=repo,
        key="key",
        request_hash="hash",
        timeout_seconds=5.0,
        retry_interval_seconds=0.25,
    )

    assert result.status == "started"
    assert repo.calls == 3
    assert sleeps == [0.25, 0.25]


def test_begin_idempotent_request_returns_processing_at_timeout(monkeypatch) -> None:
    repo = _Repo([IdempotencyBeginResult(status="processing")])
    sleeps: list[float] = []
    monotonic_values = iter([20.0, 25.0])

    monkeypatch.setattr("application.idempotency.time.sleep", sleeps.append)
    monkeypatch.setattr(
        "application.idempotency.time.monotonic",
        lambda: next(monotonic_values),
    )

    result = begin_idempotent_request(
        idempotency=repo,
        key="key",
        request_hash="hash",
        timeout_seconds=5.0,
        retry_interval_seconds=0.25,
    )

    assert result.status == "processing"
    assert repo.calls == 1
    assert sleeps == []
