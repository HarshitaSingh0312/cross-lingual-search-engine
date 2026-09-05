import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Routes both structlog-native calls and every existing `logging.getLogger(__name__)`
    call site (cache_service.py, search.py, ...) through the same JSON formatter, so the
    whole app gets structured logs without rewriting any existing logger.warning()/exception()
    call - they're wrapped, not replaced.
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # uvicorn's own access log duplicates what the request-logging middleware already emits
    # (method/path/status) - quieted so every request produces one structured line, not two.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
