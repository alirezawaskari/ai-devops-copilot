"""OpenTelemetry instrumentation setup.

Disabled by default (`OTEL_ENABLED=false`) so the app runs without an
OTLP collector present. When enabled, traces are exported via OTLP/gRPC.
"""

from fastapi import FastAPI

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def configure_telemetry(app: FastAPI) -> None:
    settings = get_settings()
    if not settings.otel_enabled:
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource(attributes={SERVICE_NAME: settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    logger.info("OpenTelemetry instrumentation enabled", extra={"otel_enabled": True})
