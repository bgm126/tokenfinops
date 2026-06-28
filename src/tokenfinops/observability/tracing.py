import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

# Setup tracer provider
resource = Resource.create(attributes={"service.name": "tokenfinops-gateway"})
provider = TracerProvider(resource=resource)

# ConsoleExporter is useful for portfolio local demo verification
processor = BatchSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)

trace.set_tracer_provider(provider)
tracer = trace.get_tracer("tokenfinops.tracer")

def get_tracer():
    return tracer
