import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

_FORMATTER = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d | %H:%M:%S",
)


def get_logger(name, filename, level=logging.INFO, max_mb=5, backups=10, console=True):
    log = logging.getLogger(name)
    if log.handlers:          # avoid duplicate handlers on re-import
        return log

    log.setLevel(level)
    log.propagate = False

    file_handler = RotatingFileHandler(
        LOG_DIR / filename,
        maxBytes=max_mb * 1024 * 1024,
        backupCount=backups,
        encoding="utf-8",
    )
    file_handler.setFormatter(_FORMATTER)
    log.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(_FORMATTER)
        log.addHandler(console_handler)

    return log


logger = get_logger("web_error_log", "web_log.log")
db_logger = get_logger("web_error_log.db", "db.log")
audit_logger = get_logger("web_error_log.audit", "audit.log", backups=30, console=False)