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
        tags = {}
        if hasattr(settings, "LOG_LOKI_EXTRA_TAGS"):
            tags = settings.LOG_LOKI_EXTRA_TAGS
        super().__init__(queue=queue, url=url, tags=tags, auth=auth, version="1")
