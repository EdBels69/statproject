import json
import logging
import os
import sys
from typing import Any, Dict

from app.core.config import settings

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger("stat_analyzer")
    return logger

logger = setup_logging()


def log_audit_event(event: Dict[str, Any]) -> None:
    try:
        path = settings.AUDIT_LOG_PATH
        if not path:
            return
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        return
