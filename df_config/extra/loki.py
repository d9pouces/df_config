"""Small wrapper around logging_loki to add some common labels."""

from queue import Queue
from typing import Optional, Tuple

from logging_loki import LokiQueueHandler, emitter

emitter.LokiEmitter.level_tag = "level"


class LokiHandler(LokiQueueHandler):
    """Log handler that sends log records to Loki."""

    def __init__(
        self,
        queue=None,
        url: Optional[str] = None,
        auth: Optional[Tuple[str, str]] = None,
    ):
        """Create new Loki logging handler."""
        from django.conf import settings

        if queue is None:
            queue = Queue(-1)
        tags = {"log_source": "django"}
        if hasattr(settings, "CURRENT_COMMAND_NAME"):
            tags["command"] = settings.CURRENT_COMMAND_NAME
        if hasattr(settings, "SERVER_NAME"):
            tags["application"] = settings.SERVER_NAME
        if hasattr(settings, "HOSTNAME"):
            tags["hostname"] = settings.HOSTNAME
        super().__init__(queue=queue, url=url, tags=tags, auth=auth, version="1")
