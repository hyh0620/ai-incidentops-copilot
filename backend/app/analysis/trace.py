from collections.abc import Callable
from contextlib import contextmanager
from time import perf_counter
from typing import Iterator
from uuid import uuid4

from app.analysis.contracts import AnalysisStageTrace
from app.core.time import utc_now


class StageSpan:
    def __init__(self) -> None:
        self.status = "success"
        self.error: str | None = None
        self.output_summary: str | None = None

    def degrade(self, reason: str) -> None:
        if self.status != "failed":
            self.status = "degraded"
            self.error = reason

    def skip(self, reason: str) -> None:
        if self.status != "failed":
            self.status = "skipped"
            self.error = reason

    def output(self, value: str) -> None:
        self.output_summary = value


class TraceRecorder:
    def __init__(self, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or uuid4().hex
        self.stages: list[AnalysisStageTrace] = []

    @contextmanager
    def stage(
        self,
        name: str,
        provider: str | None = None,
        input_summary: str | None = None,
        output: Callable[[], str | None] | None = None,
    ) -> Iterator[StageSpan]:
        started_at = utc_now()
        started = perf_counter()
        span = StageSpan()
        try:
            yield span
        except Exception as exc:
            span.status = "failed"
            span.error = str(exc)
            raise
        finally:
            ended_at = utc_now()
            output_summary = output() if output else span.output_summary
            self.stages.append(
                AnalysisStageTrace(
                    name=name,
                    status=span.status,  # type: ignore[arg-type]
                    provider=provider,
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    input_summary=input_summary,
                    output_summary=output_summary,
                    error=span.error,
                )
            )
