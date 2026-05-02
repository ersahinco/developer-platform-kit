import logging
import os

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


def _enabled(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


def configure_tracing(*, app: FastAPI, engine: Engine) -> None:
    """Enable OTLP traces only when explicitly configured."""
    if not _enabled(os.getenv("OTEL_TRACES_ENABLED")):
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    if not endpoint:
        logger.warning("OTEL_TRACES_ENABLED is true but no OTLP traces endpoint is set")
        return

    service_name = os.getenv("OTEL_SERVICE_NAME", "aws-sdlc-containers-api")
    environment = os.getenv("OTEL_DEPLOYMENT_ENVIRONMENT", "local")
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

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
