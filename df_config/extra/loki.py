from queue import Queue
from typing import Optional, Tuple

from logging_loki import LokiQueueHandler, emitter

emitter.LokiEmitter.level_tag = "level"


class LokiHandler(LokiQueueHandler):
    def __init__(
        self, url: Optional[str] = None, auth: Optional[Tuple[str, str]] = None
    ):
        from django.conf import settings

        tags = {
            "application": settings.SERVER_NAME,
            "command": settings.CURRENT_COMMAND_NAME,
            "hostname": settings.HOSTNAME,
            "log_source": "django",
        }
        super().__init__(Queue(-1), url=url, tags=tags, auth=auth, version="1")
