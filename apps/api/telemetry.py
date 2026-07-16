import logging

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

DEFAULT_EXCLUDED_TRACE_URLS = "/health,/metrics"


def configure_tracing(
    *,
    app: FastAPI,
    engine: Engine,
    enabled: bool,
    endpoint: str | None,
    service_name: str,
    environment: str,
) -> None:
    """Enable OTLP traces only when explicitly configured."""
    if not enabled:
        return

    if not endpoint:
        logger.warning("OTEL_TRACES_ENABLED is true but no OTLP traces endpoint is set")
        return

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": "aws-sdlc-containers",
            "deployment.environment": environment,
        }
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls=DEFAULT_EXCLUDED_TRACE_URLS,
    )
    SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
