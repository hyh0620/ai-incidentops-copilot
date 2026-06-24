import contextvars
import logging

from app.core.config import get_settings


request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
_FACTORY_CONFIGURED = False


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "-"
        return True


def configure_logging() -> None:
    global _FACTORY_CONFIGURED
    settings = get_settings()
    if not _FACTORY_CONFIGURED:
        previous_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = previous_factory(*args, **kwargs)
            if not hasattr(record, "request_id"):
                record.request_id = request_id_ctx.get() or "-"
            return record

        logging.setLogRecordFactory(record_factory)
        _FACTORY_CONFIGURED = True
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format='{"ts":"%(asctime)s","level":"%(levelname)s","request_id":"%(request_id)s","logger":"%(name)s","message":"%(message)s"}',
    )
    logging.getLogger().addFilter(RequestIdFilter())
