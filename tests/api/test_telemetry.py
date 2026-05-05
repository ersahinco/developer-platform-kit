from __future__ import annotations

from fastapi import FastAPI

from aws_sdlc_api import telemetry


def test_configure_tracing_excludes_low_value_probe_urls_by_default(
    monkeypatch,
) -> None:
    calls: dict[str, object] = {}

    class _FakeProvider:
        def __init__(self, resource: object) -> None:
            calls["resource"] = resource

        def add_span_processor(self, processor: object) -> None:
            calls["processor"] = processor

    class _FakeExporter:
        def __init__(self, endpoint: str) -> None:
            calls["endpoint"] = endpoint

    class _FakeSpanProcessor:
        def __init__(self, exporter: object) -> None:
            calls["exporter"] = exporter

    class _FakeFastAPIInstrumentor:
        @staticmethod
        def instrument_app(app: FastAPI, **kwargs: object) -> None:
            calls["app"] = app
            calls["fastapi_kwargs"] = kwargs

    class _FakeSQLAlchemyInstrumentor:
        def instrument(self, **kwargs: object) -> None:
            calls["sqlalchemy_kwargs"] = kwargs

    monkeypatch.setenv("OTEL_TRACES_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://tempo/v1/traces")
    monkeypatch.delenv("OTEL_PYTHON_FASTAPI_EXCLUDED_URLS", raising=False)
    monkeypatch.setattr(telemetry, "TracerProvider", _FakeProvider)
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", _FakeExporter)
    monkeypatch.setattr(telemetry, "BatchSpanProcessor", _FakeSpanProcessor)
    monkeypatch.setattr(telemetry.trace, "set_tracer_provider", lambda provider: None)
    monkeypatch.setattr(telemetry, "FastAPIInstrumentor", _FakeFastAPIInstrumentor)
    monkeypatch.setattr(
        telemetry, "SQLAlchemyInstrumentor", _FakeSQLAlchemyInstrumentor
    )

    app = FastAPI()
    engine = object()
    telemetry.configure_tracing(app=app, engine=engine)  # type: ignore[arg-type]

    assert calls["endpoint"] == "http://tempo/v1/traces"
    assert calls["app"] is app
    fastapi_kwargs = calls["fastapi_kwargs"]
    assert isinstance(fastapi_kwargs, dict)
    assert fastapi_kwargs["excluded_urls"] == "/health,/metrics"
