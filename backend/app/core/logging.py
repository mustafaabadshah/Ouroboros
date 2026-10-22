import logging
import sys
from app.core.config import settings

from collections import deque

log_ring_buffer = deque(maxlen=300)

class RingBufferHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            log_ring_buffer.append({
                "timestamp": self.formatter.formatTime(record, "%Y-%m-%d %H:%M:%S") if self.formatter else "",
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "formatted": msg
            })
        except Exception:
            pass

def setup_logger(name: str = "ouroboros") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        level_str = getattr(settings, "LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_str, logging.INFO)
        logger.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        ring_handler = RingBufferHandler()
        ring_handler.setLevel(level)
        ring_handler.setFormatter(formatter)
        logger.addHandler(ring_handler)

        logger.propagate = False
    return logger

logger = setup_logger("ouroboros")

