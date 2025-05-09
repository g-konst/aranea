import sys
from typing import Any, Optional

from loguru import logger

from app.config import settings


def setup_logger(extra: Optional[dict[str, Any]] = None) -> None:
    logger.remove()

    config = settings.logging
    logger.add(
        sink=sys.stdout,
        format=config.format,
        level=config.level,
        enqueue=config.enqueue,
        backtrace=config.backtrace,
        diagnose=config.diagnose,
    )

    if extra:
        logger.configure(extra=extra)

    logger.catch(onerror=lambda _: sys.exit(1))


log = logger
