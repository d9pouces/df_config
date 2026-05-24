# ##############################################################################
#  This file is part of df_config                                              #
#                                                                              #
#  Copyright (C) 2020 Matthieu Gallet <df_config@19pouces.net>                    #
#  All Rights Reserved                                                         #
#                                                                              #
#  You may use, distribute and modify this code under the                      #
#  terms of the (BSD-like) CeCILL-B license.                                   #
#                                                                              #
#  You should have received a copy of the CeCILL-B license with                #
#  this file. If not, please visit:                                            #
#  https://cecill.info/licences/Licence_CeCILL-B_V1-en.txt (English)           #
#  or https://cecill.info/licences/Licence_CeCILL-B_V1-fr.txt (French)         #
#                                                                              #
# ##############################################################################
"""Provide a meaningful log configuration, depending on several options."""

import logging
import logging.handlers
import os
import platform
import re
import socket
import sys
import time
import warnings
from importlib.util import find_spec
from traceback import extract_stack
from typing import Any
from urllib.parse import ParseResult, urlparse

from django.core.checks import Warning
from django.core.management.color import color_style, no_style
from django.utils.log import AdminEmailHandler as BaseAdminEmailHandler

from df_config.checks import settings_check_results


class ColorizedFormatter(logging.Formatter):
    """Used in console for applying colors to log lines, corresponding to the log level."""

    def __init__(self, *args, use_color: bool = True, **kwargs):
        """Initialize the formatter."""
        self.style = color_style() if use_color else no_style()
        kwargs.setdefault("fmt", "%(asctime)s [%(name)s] [%(levelname)s] %(message)s")
        kwargs.setdefault("datefmt", "%Y-%m-%d %H:%M:%S")
        super().__init__(*args, **kwargs)

    def format(self, record):
        """Apply a log color, corresponding to the log level."""
        msg = record.msg
        level = record.levelno
        if level <= logging.DEBUG:
            msg = self.style.HTTP_SUCCESS(msg)
        elif level <= logging.INFO:
            msg = self.style.HTTP_NOT_MODIFIED(msg)
        elif level <= logging.WARNING:
            msg = self.style.WARNING(msg)
        else:
            msg = self.style.ERROR(msg)
        record.msg = msg
        return super().format(record)

    def formatStack(self, stack_info):
        """Colorize errors in red."""
        return self.style.ERROR(stack_info)


class ServerFormatter(logging.Formatter):
    """Formatter for the access logs."""

    def __init__(self, *args, use_color: bool = True, **kwargs):
        """Initialize the object."""
        self.style = color_style() if use_color else no_style()
        super().__init__(*args, **kwargs)

    def format(self, record):
        """Format an access, colorizing it depending on the status code."""
        msg = record.msg
        status_code = getattr(record, "status_code", 0)
        level = record.levelno
        if status_code:
            if 200 <= status_code < 300:
                # Put 2XX first, since it should be the common case
                msg = self.style.SUCCESS(msg)
            elif 100 <= status_code < 200:
                msg = self.style.HTTP_INFO(msg)
            elif status_code == 304:
                msg = self.style.HTTP_NOT_MODIFIED(msg)
            elif 300 <= status_code < 400:
                msg = self.style.HTTP_REDIRECT(msg)
            elif status_code == 404:
                msg = self.style.HTTP_NOT_FOUND(msg)
            elif 400 <= status_code < 500:
                msg = self.style.HTTP_BAD_REQUEST(msg)
            else:
                # Any 5XX, or any other status code
                msg = self.style.HTTP_SERVER_ERROR(msg)
        elif level <= logging.DEBUG:
            msg = self.style.HTTP_SUCCESS(msg)
        elif level <= logging.INFO:
            msg = self.style.HTTP_NOT_MODIFIED(msg)
        elif level <= logging.WARNING:
            msg = self.style.WARNING(msg)
        else:
            msg = self.style.ERROR(msg)

        if self.uses_server_time() and not hasattr(record, "server_time"):
            record.server_time = self.formatTime(record, self.datefmt)

        record.msg = msg
        return super().format(record)

    def uses_server_time(self):
        """Return true if the log format requires the response time."""
        return (self._fmt or "").find("%(server_time)") >= 0


# noinspection PyClassHasNoInit
class AdminEmailHandler(BaseAdminEmailHandler):
    """Enhance the AdminEmailHandler provided by Django.

    Does not try to send emails if `settings.EMAIL_HOST` is not set.
    Also limits the mail rates to avoid to spam the poor admins.
    """

    _previous_email_time = None
    min_interval = 600
    """min time (in seconds) between two successive sends"""

    def send_mail(self, subject, message, *args, **kwargs):
        """Check if email can be sent before applying the original method."""
        # noinspection PyPackageRequirements
        from django.conf import settings

        if self.can_send_email() and settings.EMAIL_HOST:
            try:
                super().send_mail(subject, message, *args, **kwargs)
            except Exception as e:
                print(
                    "Unable to send e-mail to admin. Please checks your e-mail settings [%r]."
                    % e
                )
                if settings.LOG_DIRECTORY:
                    print("Check logs in %s" % settings.LOG_DIRECTORY)

    def can_send_email(self):
        """Check the time of the previous email to allow the new one."""
        now = time.time()
        previous = AdminEmailHandler._previous_email_time
        AdminEmailHandler._previous_email_time = now
        can_send = True
        if previous and now - previous < self.min_interval:
            can_send = False
        return can_send


class RemoveDuplicateWarnings(logging.Filter):
    """Displays py.warnings messages unless the same warning was already sent."""

    def __init__(self, name=""):
        """Init function."""
        super().__init__(name=name)
        self.previous_records = set()

    def filter(self, record: logging.LogRecord):
        """Check if the message has already been sent from the same Python file."""
        record_value = hash("%r %r" % (record.pathname, record.args))
        result = record_value not in self.previous_records
        self.previous_records.add(record_value)
        return result


class SlowQueriesFilter(logging.Filter):
    """Filter slow queries and attach stack_info."""

    def __init__(self, name="", slow_query_duration_in_s=1.0):
        """Init function."""
        super().__init__(name=name)
        self.slow_query_duration_in_s = slow_query_duration_in_s

    def filter(self, record: logging.LogRecord):
        """Filter SQL queries depending on their duration."""
        duration = getattr(record, "duration", 0)
        if duration > self.slow_query_duration_in_s:
            # Same as in _log for when stack_info=True is used.
            # noinspection PyTypeChecker,PydanticTypeChecker
            fn, lno, func, sinfo = logging.Logger.findCaller(None, True)
            record.stack_info = sinfo
            return True
        return False


class MaxLevelFilter(logging.Filter):
    """Filter log records that are above a maximum level.

    This filter is used to split log output between multiple handlers,
    for example to send records below ERROR to stdout and ERROR+ to stderr.
    Only records whose level is strictly below ``max_level`` are kept.
    """

    def __init__(self, name="", max_level=logging.NOTSET):
        """Init function."""
        super().__init__(name=name)
        self.max_level: int = max_level

    def filter(self, record: logging.LogRecord):
        """Only keep messages that are below the max level."""
        return record.levelno < self.max_level


class HTTPAccessRecordFilter(logging.Filter):
    """Filter log records to keep (or exclude) HTTP access messages.

    HTTP access records are identified either by the logger name being in
    ``LoggingConfiguration.access_loggers``, or by the record coming from
    ``django.channels.server`` and containing a ``client`` key in its args.

    :param keep_access: when ``True`` (default) only HTTP access records pass
        through; when ``False`` only non-access records pass through.
    """

    def __init__(self, name="", keep_access: bool = True):
        """Init function."""
        super().__init__(name=name)
        self.keep_access = keep_access

    def filter(self, record: logging.LogRecord):
        """Only keep messages that comes from an HTTP access."""
        if record.name == "django.channels.server":
            r = isinstance(record.args, dict) and "client" in record.args
        elif record.name in LoggingConfiguration.access_loggers:
            r = True
        else:
            r = False
        return not (r ^ self.keep_access)


# noinspection PyMethodMayBeStatic
class LogConfiguration:
    # noinspection SpellCheckingInspection
    """Generate a log configuration depending on a few parameters.

    * the debug mode (if `DEBUG == True`, everything is printed to the console and lower log level are applied),
    * the log directory (if set, everything is output to several rotated log files),
    * the log remote URL (to send data to syslog or logd),
    * script name (for determining the log filename).

    Required values in the `settings_dict`:

    * `DEBUG`: `True` or `False`
    * `DF_MODULE_NAME`: your project name, used to determine log filenames,
    * `LOG_DIRECTORY`: dirname where log files are written (!),
    * `LOG_LEVEL`: one of "debug", "info", "warning", "error", "critical"
    * `LOG_REMOTE_URL`: examples: "syslog+tcp://localhost:514/user", "syslog:///local7"
         "syslog:///dev/log/daemon", "logd:///project_name"
    * `LOG_REMOTE_ACCESS`: also send HTTP requests to syslog/journald
    * `LOG_SLOW_QUERY_DURATION_IN_S`: log requests that takes more than this time
    * `SERVER_NAME`: the public name of the server (like "www.example.com")
    * `SERVER_PORT`: the public port (probably 80 or 443)
    * `LOG_EXCLUDED_COMMANDS`: Django commands that do not write logs
    """

    required_settings = [
        "DEBUG",
        "DF_MODULE_NAME",
        "LOG_DIRECTORY",
        "LOG_REMOTE_URL",
        "LOG_SLOW_QUERY_DURATION_IN_S",
        "LOG_REMOTE_ACCESS",
        "SERVER_NAME",
        "SERVER_PORT",
        "LOG_EXCLUDED_COMMANDS",
        "LOG_LEVEL",
    ]
    # for loggers that only show INFO in debug mode, or WARNING in INFO, and so on:
    _level_up = {
        "DEBUG": "INFO",
        "INFO": "WARNING",
        "WARNING": "ERROR",
        "ERROR": "CRITICAL",
    }
    # set of always INFO loggers that are not propagated to root
    _level_access = {
        "DEBUG": "INFO",
        "WARNING": "INFO",
        "ERROR": "INFO",
        "CRITICAL": "INFO",
    }
    access_loggers = {
        "aiohttp.access": _level_access,
        "django.channels.server": _level_access,
        "django.server": _level_access,
        "geventwebsocket.handler": _level_access,
        "granian.access": _level_access,
        "gunicorn.access": _level_access,
        "uvicorn.access": _level_access,
    }

    problem_loggers = {
        "df_websockets.signals": {},
        "django": _level_up,
        "django.db": _level_up,
        "django.db.backends": {
            "DEBUG": "DEBUG",
            "INFO": "DEBUG",
            "WARNING": "DEBUG",
            "ERROR": "ERROR",
            "CRITICAL": "CRITICAL",
        },
        "django.db.backends.schema": _level_up,
        "django.request": {},
        "django.security": {},
        "gunicorn.error": {},
        "pip.vcs": _level_up,
        "py.warnings": _level_up,
        "uvicorn.error": {},
    }
    compat_log_levels = {
        "WARN": "WARNING",
        "CRIT": "CRITICAL",
        "EMERGENCY": "CRITICAL",
        "ALERT": "CRITICAL",
        "NOTICE": "INFO",
    }

    # all loggers that will be defined
    # values are dict to map chosen log level (by the admin) to the log level

    def __init__(self, stdout=None, stderr=None):
        """Init function."""
        self.formatters = {}
        self.filters = {}
        self.loggers = {}
        self.handlers = {}
        self.root = {}
        self.log_suffix = None
        self.module_name = None
        self.log_directory = None
        self.server_name = None
        self.log_level = None
        self.server_port = None
        self.slow_query_duration_in_s = None
        self.excluded_commands = {}
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.log_directory_warning = False  # True when a warning has been emitted

    def __call__(self, settings_dict, argv: list[str] | None = None):
        """Create the log configuration during the setting computation."""
        warning = Warning(
            "LogConfiguration is deprecated and will be removed in df_config 1.5. Use LoggingConfiguration instead.",
            hint=None,
            obj="configuration",
            id="df_config.W011",
        )
        settings_check_results.append(warning)
        if argv is None:
            argv = sys.argv
        argv: list[str]
        self.module_name = settings_dict["DF_MODULE_NAME"]
        self.server_name = settings_dict["SERVER_NAME"]
        self.server_port = settings_dict["SERVER_PORT"]
        self.slow_query_duration_in_s = settings_dict["LOG_SLOW_QUERY_DURATION_IN_S"]
        self.excluded_commands = settings_dict["LOG_EXCLUDED_COMMANDS"]
        if settings_dict["LOG_LEVEL"]:
            log_level = settings_dict["LOG_LEVEL"].upper()
        elif settings_dict["DEBUG"]:
            log_level = "DEBUG"
        else:
            log_level = "WARNING"
        log_level = self.compat_log_levels.get(log_level, log_level)
        self.formatters = self.get_default_formatters()
        self.filters = self.get_default_filters()
        self.loggers = self.get_default_loggers()
        self.handlers = self.get_default_handlers()
        self.root = self.get_default_root()
        self.log_suffix = self.get_smart_command_name(
            self.module_name,
            argv,
            self.excluded_commands,
        )
        self.log_directory = settings_dict["LOG_DIRECTORY"]
        config = {
            "version": 1,
            "disable_existing_loggers": True,
            "formatters": self.formatters,
            "filters": self.filters,
            "handlers": self.handlers,
            "loggers": self.loggers,
            "root": self.root,
        }
        self.root["level"] = log_level
        for logger, levels in self.problem_loggers.items():
            self.loggers[logger]["level"] = levels.get(log_level, log_level)
        for logger, levels in self.access_loggers.items():
            self.loggers[logger]["level"] = levels.get(log_level, log_level)
        if settings_dict["DEBUG"]:
            warnings.simplefilter("always", DeprecationWarning)
            logging.captureWarnings(True)
            self.add_handler("ROOT", "stdout", level="INFO", formatter="colorized")
            for logger in self.access_loggers:
                self.add_handler(
                    logger, "stderr", level="DEBUG", formatter="django.server"
                )
            return config

        has_handler = False

        if self.log_directory and self.log_suffix:
            self.add_handler("ROOT", "root", level=log_level)
            for logger in self.access_loggers:
                self.add_handler(logger, "access", level="DEBUG", formatter="nocolor")
            has_handler = True

        has_handler = (
            self.add_remote_collector(
                settings_dict["LOG_REMOTE_URL"],
                settings_dict["LOG_REMOTE_ACCESS"],
                level=log_level,
            )
            or has_handler
        )
        if not has_handler or not self.log_suffix:
            # (no file or interactive command) and no logd/syslog => we print to the console (like the debug mode)
            name = self.add_handler(
                "ROOT", "stdout", level=log_level, formatter="colorized"
            )
            if name:
                # noinspection PyTypeChecker
                self.handlers[name].setdefault("filters", []).append("below_error")
            self.add_handler("ROOT", "stderr", level="ERROR", formatter="colorized")
            for logger in self.access_loggers:
                self.add_handler(
                    logger, "stderr", formatter="django.server", level=log_level
                )
        # noinspection PyUnresolvedReferences
        self.root["handlers"].append("mail_admins")
        return config

    def __repr__(self):
        """Return a valid representation."""
        return "%s.%s" % (self.__module__, "log_configuration")

    def add_remote_collector(self, log_remote_url, log_remote_access, level="WARNING"):
        """Add a remote collector, like syslog or loki."""
        has_handler = False
        if not log_remote_url:
            return has_handler
        parsed_log_url = urlparse(log_remote_url)
        scheme = parsed_log_url.scheme
        device, sep, facility_name = parsed_log_url.path.rpartition("/")
        # noinspection SpellCheckingInspection
        if scheme == "syslog" or scheme == "syslog+tcp":
            address, facility, sock_type = self.parse_syslog_url(
                parsed_log_url, scheme, device, facility_name
            )
            # noinspection SpellCheckingInspection
            kwargs = {
                "address": address,
                "facility": facility,
                "socktype": sock_type,
                "formatter": "nocolor",
            }
            self.add_handler("ROOT", "syslog", level=level, **kwargs)
            if log_remote_access:
                for logger in self.access_loggers:
                    self.add_handler(logger, "syslog", level="DEBUG", **kwargs)
            has_handler = True
        elif scheme == "loki" or scheme == "lokis":
            # noinspection HttpUrlsUsage
            url = f"http://{parsed_log_url.hostname}"
            # noinspection SpellCheckingInspection
            if scheme == "lokis":
                url = f"https://{parsed_log_url.hostname}"
            if parsed_log_url.port:
                url += f":{parsed_log_url.port}"
            if parsed_log_url.path:
                url += parsed_log_url.path
            if parsed_log_url.query:
                url += f"?{parsed_log_url.query}"
            auth = None
            if parsed_log_url.username and parsed_log_url.password:
                auth = (parsed_log_url.username, parsed_log_url.password)
            kwargs = {"url": url, "auth": auth}
            self.add_handler("ROOT", "loki", level=level, **kwargs)
            if log_remote_access:
                for logger in self.access_loggers:
                    self.add_handler(logger, "loki", level="DEBUG", **kwargs)
            has_handler = True
        else:
            # noinspection SpellCheckingInspection
            warning = Warning(
                "The only known schemes for remote logging are syslog, syslog+tcp, loki or lokis.",
                hint=None,
                obj="configuration",
                id="df_config.W005",
            )
            settings_check_results.append(warning)
        return has_handler

    def parse_syslog_url(self, parsed_log_url, scheme, device, facility_name):
        """Parse a syslog URL and return valid parameters."""
        import platform
        import socket
        import syslog

        if (
            parsed_log_url.hostname
            and parsed_log_url.port
            and re.match(r"^\d+$", str(parsed_log_url.port))
        ):
            address = (parsed_log_url.hostname, int(parsed_log_url.port))
        elif device:
            address = device
        elif platform.system() == "Darwin":
            address = "/var/run/syslog"
        elif platform.system() == "Linux":
            address = "/dev/log"
        else:
            address = ("localhost", 514)
        sock_type = socket.SOCK_DGRAM if scheme == "syslog" else socket.SOCK_STREAM
        # noinspection PyUnresolvedReferences
        facility = logging.handlers.SysLogHandler.facility_names.get(
            facility_name, syslog.LOG_USER
        )
        return address, facility, sock_type

    @property
    def fmt_stderr(self):
        """Return the valid formatter for stderr (if it's a TTY)."""
        return "colorized" if self.stderr.isatty() else None

    @property
    def fmt_stdout(self):
        """Return the valid formatter for stdout (if it's a TTY)."""
        return "colorized" if self.stdout.isatty() else None

    def get_default_formatters(self):
        """Return some default formatters."""
        name = "%s:%s" % (self.server_name, self.server_port)
        return {
            "django.server": {
                "()": "df_config.guesses.log.ServerFormatter",
                "fmt": "%(asctime)s [{}] %(message)s".format(name),
            },
            "nocolor": {
                "()": "logging.Formatter",
                "fmt": "%(asctime)s [{}] [%(levelname)s] %(message)s".format(name),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "colorized": {"()": "df_config.guesses.log.ColorizedFormatter"},
        }

    def get_default_handlers(self):
        """Return default handlers."""
        return {
            "mail_admins": {
                "class": "df_config.guesses.log.AdminEmailHandler",
                "level": "ERROR",
                "include_html": True,
            }
        }

    def get_default_filters(self):
        """Return default filters."""
        filters = {
            "remove_duplicate_warnings": {
                "()": "df_config.guesses.log.RemoveDuplicateWarnings"
            },
            "below_error": {
                "()": "df_config.guesses.log.MaxLevelFilter",
                "max_level": logging.ERROR,
            },
        }
        if self.slow_query_duration_in_s:
            filters["slow_queries"] = {
                "()": "df_config.guesses.log.SlowQueriesFilter",
                "slow_query_duration_in_s": self.slow_query_duration_in_s,
            }

        return filters

    def get_default_root(self):
        """Return the default log root."""
        return {"handlers": [], "level": "WARNING"}

    def get_default_loggers(self):
        """Return the default loggers."""
        loggers = {}
        for logger in self.problem_loggers:
            loggers[logger] = {"handlers": [], "level": "DEBUG", "propagate": True}
        if self.slow_query_duration_in_s:
            loggers["django.db.backends"]["filters"] = ["slow_queries"]
        loggers["py.warnings"]["filters"] = ["remove_duplicate_warnings"]
        for logger in self.access_loggers:
            loggers[logger] = {"handlers": [], "level": "DEBUG", "propagate": False}
        return loggers

    def add_handler(
        self,
        logger: str,
        filename: str,
        level: str = "WARNING",
        formatter=None,
        **kwargs,
    ) -> str | None:
        # noinspection SpellCheckingInspection
        """Add a handler to a logger.

        The name of the added handler is unique, so the definition of the handler is also add if required.
        You can use "ROOT" as logger name to target the root logger.

        filename: can be a filename or one of the following special values: "stderr", "stdout", "logd", "syslog"
        """
        # noinspection SpellCheckingInspection
        if filename == "stderr":
            handler, handler_name = self.add_handler_stderr_stdout(
                filename, formatter, level, "stderr"
            )
        elif filename == "stdout":
            handler, handler_name = self.add_handler_stderr_stdout(
                filename, formatter, level, "stdout"
            )
        elif filename == "loki":
            handler, handler_name = self.add_handler_loki(
                logger, filename, level, kwargs
            )
        elif filename == "syslog":
            handler_name = f"{filename}.{level.lower()}"
            handler = {"class": "logging.handlers.SysLogHandler", "level": level}
            handler.update(kwargs)
        elif filename == "logd":
            handler, handler_name = self.add_handler_logd(
                logger, filename, level, kwargs
            )
        elif self.log_directory:  # basename of a plain-text log
            handler, handler_name = self.add_handler_directory(
                logger, filename, level, kwargs
            )
        else:
            handler, handler_name = None, None
        if not handler_name:
            return None
        if handler_name not in self.handlers:
            self.handlers[handler_name] = handler
        if logger == "ROOT":
            target = self.root
        else:
            target = self.loggers[logger]
        if handler_name not in target["handlers"]:
            target["handlers"].append(handler_name)
        return handler_name

    def add_handler_loki(self, logger, filename, level, kwargs):
        """Add a loki handler when required and possible."""
        try:
            # noinspection PyUnresolvedReferences,PyPackageRequirements
            import logging_loki
        except ImportError:
            warning = Warning(
                "Unable to import logging_loki (required to log to Loki)",
                hint=None,
                obj="configuration",
                id="df_config.W006",
            )
            settings_check_results.append(warning)
            # replace loki by writing to a plain-text log
            self.add_handler(logger, level.lower(), level=level)
            return None, None
        handler_name = f"{filename}.{level.lower()}"
        handler = {"class": "df_config.extra.loki.LokiHandler", "level": level}
        handler.update(kwargs)
        return handler, handler_name

    # noinspection SpellCheckingInspection
    def add_handler_logd(self, logger: str, filename: str, level: str, kwargs: dict):
        """Add a logd (systemd) handler when required and possible."""
        try:
            # noinspection PyUnresolvedReferences,PyPackageRequirements
            import systemd.journal
        except ImportError:
            warning = Warning(
                "Unable to import systemd.journal (required to log with journald)",
                hint=None,
                obj="configuration",
                id="df_config.W007",
            )
            settings_check_results.append(warning)
            # replace logd by writing to a plain-text log
            self.add_handler(logger, level.lower(), level=level)
            return None, None
        handler_name = f"{filename}.{level.lower()}"
        handler = {"class": "systemd.journal.JournalHandler", "level": level}
        handler.update(kwargs)
        return handler, handler_name

    def add_handler_directory(self, logger, filename, level, kwargs):
        """Add a log handler when a log directory is defined and writeable."""
        log_directory = os.path.normpath(self.log_directory)
        if not os.path.isdir(log_directory):
            if not self.log_directory_warning:
                warning = Warning(
                    f"Missing directory '{log_directory}'.",
                    hint=None,
                    obj="configuration",
                    id="df_config.W008",
                )
                settings_check_results.append(warning)
                self.log_directory_warning = True
            self.add_handler(logger, "stdout", level=level, **kwargs)
            return None, None
        if filename == "":
            basename = f"{self.log_suffix}.log"
        else:
            basename = f"{self.log_suffix}-{filename}.log"
        log_filename = os.path.join(log_directory, basename)
        if not os.access(log_directory, os.W_OK):
            warning_ = Warning(
                f"Unable to write logs in '{log_directory}' (unsufficient rights?).",
                hint=None,
                obj="configuration",
                id="df_config.W009",
            )
            settings_check_results.append(warning_)
            self.add_handler(logger, "stdout", level=level, **kwargs)
            return None, None
        if filename == "":
            handler_name = self.log_suffix
        else:
            handler_name = f"{self.log_suffix}.{filename}"
        handler = {
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": self.get_logfile_maxsize(),
            "backupCount": self.get_logfile_backup_count(),
            "formatter": "nocolor",
            "filename": log_filename,
            "level": level,
            "delay": True,
        }
        return handler, handler_name

    def get_logfile_backup_count(self):
        """Return the number of log files to keep before deleting the oldest one."""
        return 3

    def get_logfile_maxsize(self):
        """Return the maximum size of a log file before rotating it."""
        return 1000000

    def add_handler_stdout(self, filename, formatter, level):
        """Add a handler for stdout."""
        attr_name = "stdout"
        return self.add_handler_stderr_stdout(filename, formatter, level, attr_name)

    def add_handler_stderr(self, filename, formatter, level):
        """Add a handler for stderr."""
        attr_name = "stderr"
        return self.add_handler_stderr_stdout(filename, formatter, level, attr_name)

    def add_handler_stderr_stdout(
        self, filename, formatter, level, attr_name: str
    ) -> tuple[dict[str, str | Any], str]:
        """Add a handler for stderr or stdout."""
        handler_name = f"{filename}.{level.lower()}"
        if (
            formatter in ("django.server", "colorized")
            and not getattr(self, attr_name).isatty()
        ):
            formatter = "nocolor"
        elif formatter:
            handler_name += f".{formatter}"
        handler = {
            "class": "logging.StreamHandler",
            "level": level,
            "stream": f"ext://sys.{attr_name}",
            "formatter": formatter,
        }
        return handler, handler_name

    @staticmethod
    def get_smart_command_name(module_name, argv, excluded_commands=None):
        """Return a "smart" name for the current command line.

        If it's an interactive Django command (think to "migrate"), returns None
        Otherwise, add the Django command in the name.

        :param module_name:
        :param argv:
        :param excluded_commands:
        :return:
        """
        # command_name = LogConfiguration.resolve_command()
        first_arg = argv[1] if len(argv) >= 2 else None
        if excluded_commands and first_arg in excluded_commands:
            return None
        log_suffix = "%s-%s" % (module_name, first_arg)
        return log_suffix

    @staticmethod
    def resolve_command():
        """Extract the command name in stack traces."""
        f = extract_stack()
        for filename, line_number, name, text in f:
            if filename.endswith("df_config/manage.py") and name in (
                "celery",
                "server",
            ):
                return name
        return None


class LoggingConfiguration:
    # noinspection SpellCheckingInspection
    """Generate a Django ``LOGGING`` configuration dictionary from high-level parameters.

    This is the modern replacement for :class:`LogConfiguration` (which is
    deprecated).  It follows the same general approach — determine where log
    records should be written, at what level, and in what format — but
    separates concerns more cleanly into prepare_* / add_* methods so that
    subclasses can override only what they need.

    Supported output destinations (configured via ``LOG_REMOTE_URL``):

    * **Console** – stdout / stderr streams (always available as fallback).
    * **Rotating file** – written to ``LOG_DIRECTORY`` when that setting is
      defined and the directory is writable.
    * **Syslog** – ``syslog://`` or ``syslog+tcp://`` URLs.
    * **journald (logd)** – ``logd://`` URL; requires *systemd* Python package.
    * **Loki** – ``loki://`` or ``lokis://`` URLs; requires *logging-loki*.

    Access logs (HTTP requests) are routed to separate handlers so that they
    can be written to a dedicated ``*-access.log`` file without polluting the
    main log.

    Required keys in ``settings_dict`` (see ``required_settings``):

    * ``DEBUG`` – enables verbose console output and DeprecationWarnings.
    * ``DF_MODULE_NAME`` – project name used to build log file names.
    * ``LOG_DIRECTORY`` – directory for rotating log files (empty = disabled).
    * ``LOG_LEVEL`` – one of DEBUG / INFO / WARNING / ERROR / CRITICAL.
    * ``LOG_REMOTE_URL`` – URL of a remote syslog / logd / loki endpoint.
    * ``LOG_REMOTE_ACCESS`` – also forward HTTP-access records to the remote.
    * ``LOG_SLOW_QUERY_DURATION_IN_S`` – threshold (seconds) for slow-query
      logging; ``None`` or ``0`` disables the feature.
    * ``SERVER_NAME`` / ``SERVER_PORT`` – included in the log format string.
    * ``LOG_EXCLUDED_COMMANDS`` – Django management commands that suppress
      file-based logging (e.g. interactive one-shot commands like *migrate*).
    """

    required_settings = [
        "DEBUG",
        "DF_MODULE_NAME",
        "LOG_DIRECTORY",
        "LOG_REMOTE_URL",
        "LOG_SLOW_QUERY_DURATION_IN_S",
        "LOG_REMOTE_ACCESS",
        "SERVER_NAME",
        "SERVER_PORT",
        "LOG_EXCLUDED_COMMANDS",
        "LOG_LEVEL",
    ]
    _level_up = {
        "DEBUG": "INFO",
        "INFO": "WARNING",
        "WARNING": "ERROR",
        "ERROR": "CRITICAL",
    }
    access_loggers = {
        "aiohttp.access",
        "django.channels.server",
        "django.server",
        "geventwebsocket.handler",
        "granian.access",
        "gunicorn.access",
        "uvicorn.access",
    }
    other_level_loggers = {
        "django": _level_up,
        "django.db": _level_up,
        "django.db.backends.schema": _level_up,
        "pip.vcs": _level_up,
        "py.warnings": _level_up,
    }
    disabled_loggers = set()

    def __init__(self, stdout=None, stderr=None):
        """Init function."""
        self.argv = []
        self.current_django_command: str = ""
        self.access_handlers = {}
        self.default_handlers = {}
        self.filters = {}
        self.formatters = {}
        self.log_directory = None
        self.debug = False
        self.log_directory_warning = False  # True when a warning has been emitted
        self.log_level: str = "NOTSET"
        self.log_remote_url = None
        self.log_remote_access = False
        self.loggers = {}
        self.root = {}
        self.handlers = {}
        self.server_name = "localhost"
        self.server_port = "8000"
        self.project_name = "application"
        self.disable_existing_loggers = False
        self.slow_query_duration_in_s = None
        self.stderr = stderr or sys.stderr
        self.stdout = stdout or sys.stdout
        self.ignored_django_commands: set[str] = set()

    def __call__(self, settings_dict, argv=None):
        """Create the log configuration during the setting computation."""
        # read and load config parameters
        self.clean_log_configuration()
        self.read_settings(settings_dict, argv)
        self.prepare_configuration()
        config = {
            "version": 1,
            "disable_existing_loggers": self.disable_existing_loggers,
            "formatters": self.formatters,
            "filters": self.filters,
            "handlers": self.handlers,
            "loggers": self.loggers,
            "root": self.root,
        }
        return config

    def clean_log_configuration(self):
        """Remove any existing handlers and reset their level to NOTSET."""
        for logger in logging.Logger.manager.loggerDict.values():
            if isinstance(logger, logging.Logger):
                handlers = list(logger.handlers)
                for handler in handlers:
                    logger.removeHandler(handler)
                    handler.close()
                logger.setLevel(self.log_level)

    def read_settings(self, settings_dict, argv):
        """Read and store all relevant values from *settings_dict* and *argv*.

        Translates ``LOG_LEVEL`` (with ``DEBUG`` as a fallback) into a
        canonical upper-case string such as ``"WARNING"``, and stores every
        setting that later prepare_* methods will need.

        :param settings_dict: the merged Django settings dictionary produced
            by the :class:`~df_config.config.merger.SettingMerger`.
        :param argv: the command-line argument list; defaults to ``sys.argv``
            when ``None``.
        """
        self.argv = argv or sys.argv
        self.read_django_command()
        if settings_dict["LOG_LEVEL"]:
            log_level = settings_dict["LOG_LEVEL"].upper()
        elif settings_dict["DEBUG"]:
            log_level = "DEBUG"
        else:
            log_level = "WARNING"
        self.debug = settings_dict["DEBUG"]
        self.project_name = settings_dict["DF_MODULE_NAME"]
        self.server_name = settings_dict["SERVER_NAME"]
        self.server_port = settings_dict["SERVER_PORT"]
        self.log_level = log_level
        self.log_remote_access = settings_dict["LOG_REMOTE_ACCESS"]
        self.ignored_django_commands = settings_dict["LOG_EXCLUDED_COMMANDS"]
        self.slow_query_duration_in_s = settings_dict["LOG_SLOW_QUERY_DURATION_IN_S"]
        if self.current_django_command not in self.ignored_django_commands:
            self.log_directory = settings_dict["LOG_DIRECTORY"]
            self.log_remote_url = settings_dict["LOG_REMOTE_URL"]

    def read_django_command(self):
        """Extract the Django management command name from ``self.argv``.

        Sets ``self.current_django_command`` to ``argv[1]`` (e.g. ``"server"``,
        ``"runserver"``) or to an empty string when no sub-command is present.
        """
        self.current_django_command = self.argv[1] if len(self.argv) > 1 else ""

    def prepare_configuration(self):
        """Orchestrate all prepare_* calls in the correct order.

        Formatters → filters → default handlers → access handlers → root →
        loggers → per-logger filters.  After this method returns,
        ``self.formatters``, ``self.filters``, ``self.handlers``,
        ``self.loggers``, and ``self.root`` are fully populated and can be
        merged into the Django ``LOGGING`` dict.
        """
        self.prepare_formatters()
        self.prepare_filters()
        self.prepare_default_handlers()
        self.prepare_access_handlers()
        self.prepare_root()
        self.create_loggers()
        self.add_filters_to_loggers()

    def prepare_formatters(self):
        """Prepare formatters that can be used by any handler or logger."""
        name = f"{self.server_name}:{self.server_port}"
        self.formatters |= {
            "access.nocolor": {
                "()": "df_config.guesses.log.ServerFormatter",
                "fmt": "%(asctime)s [{}] %(message)s".format(name),
                "use_color": False,
            },
            "access.color": {
                "()": "df_config.guesses.log.ServerFormatter",
                "fmt": "%(asctime)s [{}] %(message)s".format(name),
                "use_color": True,
            },
            "plain.nocolor": {
                "()": "df_config.guesses.log.ColorizedFormatter",
                "use_color": False,
            },
            "plain.color": {
                "()": "df_config.guesses.log.ColorizedFormatter",
                "use_color": True,
            },
        }

    @staticmethod
    def get_colored_formatter(formatter: str, stream: str | None = None) -> str:
        """Return the full formatter name with the appropriate color suffix.

        Appends ``.color`` when *stream* refers to a TTY, or ``.nocolor``
        otherwise.  This ensures that ANSI escape codes are only emitted when
        the output device actually supports them.

        :param formatter: base formatter name, e.g. ``"plain"`` or ``"access"``.
        :param stream: name of the ``sys`` attribute to inspect (``"stdout"``
            or ``"stderr"``), or ``None`` to always use the nocolor variant.
        :returns: one of ``"<formatter>.color"`` or ``"<formatter>.nocolor"``.
        """
        if (
            stream is not None
            and hasattr(getattr(sys, stream), "isatty")
            and getattr(sys, stream).isatty()
        ):
            return f"{formatter}.color"
        return f"{formatter}.nocolor"

    def add_stdout_stderr_handler(
        self,
        handlers: dict[str, dict],
        log_suffix: str,
        level: str,
        formatter: str,
        filters: list[str],
    ):
        """Register a pair of stdout / stderr stream handlers in *handlers*.

        Records below ERROR are routed to stdout (through the ``below_error``
        filter); ERROR and above go to stderr.  Both handlers share the same
        *formatter* and extra *filters*.

        :param handlers: the handler dict to populate (mutated in place).
        :param log_suffix: suffix appended to the handler key to make it
            unique, e.g. ``"-access"`` or ``"-default"``.
        :param level: minimum log level for the stdout handler, e.g.
            ``"INFO"`` or ``"WARNING"``.
        :param formatter: base formatter name (``"plain"`` or ``"access"``);
            the color variant is resolved automatically via
            :meth:`get_colored_formatter`.
        :param filters: list of filter keys to attach to both handlers.
        """
        handler = {
            "class": "logging.StreamHandler",
            "filters": ["below_error"],
            "stream": f"ext://sys.stdout",
        }
        self.finalize_handler(
            handlers,
            handler,
            f"stdout{log_suffix}",
            level,
            formatter,
            "stdout",
            filters,
        )
        handler = {
            "class": "logging.StreamHandler",
            "stream": f"ext://sys.stderr",
        }
        self.finalize_handler(
            handlers,
            handler,
            f"stderr{log_suffix}",
            "ERROR",
            formatter,
            "stderr",
            filters,
        )

    def add_file_handler(
        self,
        handlers: dict[str, dict],
        log_suffix: str,
        level: str,
        formatter: str,
        filters: list[str],
    ):
        """Add a log handler when a log directory is defined and writeable."""
        log_directory = os.path.normpath(self.log_directory)
        basename = f"{self.project_name}{log_suffix}.log"
        full_path = os.path.join(log_directory, basename)
        if not os.path.isdir(log_directory):
            if not self.log_directory_warning:
                warning_ = Warning(
                    f"Missing log directory '{log_directory}'.",
                    hint=None,
                    obj="configuration",
                    id="df_config.W008",
                )
                settings_check_results.append(warning_)
                self.log_directory_warning = True
            self.add_stdout_stderr_handler(
                handlers, log_suffix, level, formatter, filters
            )
            return
        elif (
            os.path.isfile(full_path) and not os.access(full_path, os.W_OK)
        ) or not os.access(log_directory, os.W_OK):
            if not self.log_directory_warning:
                warning_ = Warning(
                    f"Unable to write logs to '{log_directory}'.",
                    hint=None,
                    obj="configuration",
                    id="df_config.W009",
                )
                settings_check_results.append(warning_)
                self.log_directory_warning = True
            self.add_stdout_stderr_handler(
                handlers, log_suffix, level, formatter, filters
            )
            return
        handler = {
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": self.get_logfile_maxsize(),
            "backupCount": self.get_logfile_backup_count(),
            "filename": full_path,
            "delay": True,
        }
        self.finalize_handler(
            handlers,
            handler,
            f"file.{log_suffix}",
            level,
            formatter,
            None,
            filters,
        )

    @classmethod
    def parse_syslog_url(
        cls, parsed_log_url: ParseResult, scheme: str, device: str, facility_name: str
    ):
        """Parse a syslog URL and return valid parameters."""
        import syslog

        if (
            parsed_log_url.hostname
            and parsed_log_url.port
            and re.match(r"^\d+$", str(parsed_log_url.port))
        ):
            # noinspection PyTypeChecker
            address = (parsed_log_url.hostname, int(parsed_log_url.port))
        elif device:
            address = device
        elif platform.system() == "Darwin":
            address = "/var/run/syslog"
        elif platform.system() == "Linux":
            address = "/dev/log"
        else:
            address = ("localhost", 514)
        sock_type = socket.SOCK_DGRAM if scheme == "syslog" else socket.SOCK_STREAM
        # noinspection PyUnresolvedReferences
        facility = logging.handlers.SysLogHandler.facility_names.get(
            facility_name, syslog.LOG_USER
        )
        return address, facility, sock_type

    def add_remote_collector(
        self,
        handlers,
        name,
        log_remote_url: str,
        level: str,
        formatter: str,
        filters: list[str],
    ):
        """Add a remote collector, like syslog or loki."""
        parsed_log_url: ParseResult = urlparse(log_remote_url)
        scheme = parsed_log_url.scheme
        # noinspection SpellCheckingInspection
        if scheme == "syslog" or scheme == "syslog+tcp":
            device, sep, facility_name = parsed_log_url.path.rpartition("/")
            address, facility, sock_type = self.parse_syslog_url(
                parsed_log_url, scheme, device, facility_name
            )
            # noinspection SpellCheckingInspection
            kwargs = {"address": address, "facility": facility, "socktype": sock_type}
            self.add_handler_syslog(
                handlers, f"{name}-remote", level, formatter, filters, **kwargs
            )
        elif scheme == "logd":
            self.add_logd_handler(
                handlers,
                f"{name}-remote",
                level,
                formatter,
                filters,
            )
        elif scheme == "loki" or scheme == "lokis":
            url = f"{scheme.replace('loki', 'http')}://{parsed_log_url.hostname}"
            if parsed_log_url.port:
                url += f":{parsed_log_url.port}"
            if parsed_log_url.path:
                url += parsed_log_url.path
            if parsed_log_url.query:
                url += f"?{parsed_log_url.query}"
            auth = None
            if parsed_log_url.username and parsed_log_url.password:
                auth = (parsed_log_url.username, parsed_log_url.password)
            kwargs = {"url": url, "auth": auth}
            self.add_handler_loki(
                handlers, f"{name}-remote", level, formatter, filters, **kwargs
            )
        else:
            # noinspection SpellCheckingInspection
            warning = Warning(
                "The only known schemes for remote logging are logd, syslog, syslog+tcp, loki or lokis.",
                hint=None,
                obj="configuration",
                id="df_config.W005",
            )
            settings_check_results.append(warning)

    # noinspection SpellCheckingInspection
    def add_logd_handler(
        self,
        handlers: dict[str, dict],
        log_suffix: str,
        level: str,
        formatter: str,
        filters: list[str],
        **kwargs,
    ):
        """Add a LOGD (systemd) handler when required and possible."""
        if find_spec("systemd.journal") is None:
            warning = Warning(
                "Unable to import systemd.journal (required to log with journald)",
                hint=None,
                obj="configuration",
                id="df_config.W007",
            )
            settings_check_results.append(warning)
            self.add_stdout_stderr_handler(
                handlers, log_suffix, level, formatter, filters
            )
            return
        handler = {"class": "systemd.journal.JournalHandler", **kwargs}
        # noinspection SpellCheckingInspection
        self.finalize_handler(
            handlers,
            handler,
            f"logd.{log_suffix}",
            level,
            formatter,
            None,
            filters,
        )

    def add_handler_loki(
        self,
        handlers: dict[str, dict],
        log_suffix: str,
        level: str,
        formatter: str,
        filters: list[str],
        **kwargs,
    ):
        """Add a loki handler when required and possible."""
        if find_spec("logging_loki") is None:
            warning = Warning(
                "Unable to import logging_loki (required to log to Loki)",
                hint=None,
                obj="configuration",
                id="df_config.W006",
            )
            settings_check_results.append(warning)
            # replace loki by writing to a plain-text log
            self.add_stdout_stderr_handler(
                handlers, log_suffix, level, formatter, filters
            )
            return
        handler = {"class": "df_config.extra.loki.LokiHandler", **kwargs}
        self.finalize_handler(
            handlers,
            handler,
            f"loki.{log_suffix}",
            level,
            formatter,
            None,
            filters,
        )

    def add_handler_syslog(
        self,
        handlers: dict[str, dict],
        log_suffix: str,
        level: str,
        formatter: str,
        filters: list[str],
        **kwargs,
    ):
        """Add a syslog handler when required and possible."""
        handler = {"class": "logging.handlers.SysLogHandler", **kwargs}
        self.finalize_handler(
            handlers,
            handler,
            f"syslog.{log_suffix}",
            level,
            formatter,
            None,
            filters,
        )

    def finalize_handler(
        self,
        handlers,
        handler,
        name: str,
        level: str | None,
        formatter: str,
        stream: str | None,
        filters: list[str],
    ):
        """Apply common fields to *handler* and register it in *handlers*.

        Sets ``level``, ``formatter`` (color-aware), and ``filters`` on the
        handler dict, then stores it under *name* in *handlers* (skipping the
        registration if *name* is already present, so shared handlers are not
        duplicated).

        :param handlers: the handler dict to populate (mutated in place).
        :param handler: partially built handler dict (class already set by the
            caller).
        :param name: unique key for the handler entry.
        :param level: log level string (e.g. ``"WARNING"``), or ``None`` to
            leave the handler's own default.
        :param formatter: base formatter name passed to
            :meth:`get_colored_formatter`.
        :param stream: stream name (``"stdout"`` / ``"stderr"``) used to
            detect TTY, or ``None`` for non-stream handlers.
        :param filters: list of filter keys to append to the handler.
        """
        if level is not None:
            handler["level"] = level
        handler["formatter"] = self.get_colored_formatter(formatter, stream)
        handler.setdefault("filters", [])
        if filters is not None:
            handler["filters"] += filters
        if name not in handlers:
            handlers[name] = handler

    # noinspection PyMethodMayBeStatic
    def get_logfile_maxsize(self) -> int:
        """Return the maximum size (bytes) of a log file before it is rotated.

        Override in a subclass to change the rotation threshold.
        Default: 100 MB.
        """
        return 100_000_000

    # noinspection PyMethodMayBeStatic
    def get_logfile_backup_count(self) -> int:
        """Return the number of rotated log files to keep before deletion.

        Override in a subclass to change the retention count.
        Default: 5 files.
        """
        return 5

    def prepare_access_handlers(self):
        """Prepare handlers used by access loggers."""
        if self.log_directory:
            self.add_file_handler(
                self.access_handlers,
                "-access",
                "INFO",
                "access",
                filters=["http_access"],
            )
        if (
            self.debug
            or not self.log_directory
            or self.current_django_command == "runserver"
        ):
            self.add_stdout_stderr_handler(
                self.access_handlers,
                "-access",
                "INFO",
                "access",
                filters=["http_access"],
            )
        if self.log_remote_url and self.log_remote_access:
            self.add_remote_collector(
                self.access_handlers,
                "remote.access",
                self.log_remote_url,
                "INFO",
                "access",
                filters=["http_access"],
            )
        self.handlers |= self.access_handlers

    def prepare_default_handlers(self):
        """Prepare handlers used by default loggers."""
        default_handlers_at_level = {}
        if not self.debug:
            default_handlers_at_level["mail_admins"] = {
                "class": "df_config.guesses.log.AdminEmailHandler",
                "level": "ERROR",
                "include_html": True,
                "filters": ["not_http_access"],
            }
        if self.log_directory:
            self.add_file_handler(
                default_handlers_at_level,
                "",
                self.log_level,
                "plain",
                filters=["not_http_access"],
            )
            if self.debug:
                self.add_stdout_stderr_handler(
                    default_handlers_at_level,
                    "-debug",
                    "ERROR",
                    "plain",
                    filters=["not_http_access"],
                )
        else:
            self.add_stdout_stderr_handler(
                default_handlers_at_level,
                "-default",
                self.log_level,
                "plain",
                filters=["not_http_access"],
            )
        if self.log_remote_url:
            self.add_remote_collector(
                default_handlers_at_level,
                "remote.default",
                self.log_remote_url,
                self.log_level,
                "plain",
                filters=["not_http_access"],
            )
        self.default_handlers |= default_handlers_at_level
        self.handlers |= default_handlers_at_level

    def prepare_filters(self):
        """Prepare filters that can be used by any handler or logger."""
        self.filters |= {
            "remove_duplicate_warnings": {
                "()": "df_config.guesses.log.RemoveDuplicateWarnings"
            },
            "below_error": {
                "()": "df_config.guesses.log.MaxLevelFilter",
                "max_level": logging.ERROR,
            },
            "http_access": {
                "()": "df_config.guesses.log.HTTPAccessRecordFilter",
                "keep_access": True,
            },
            "not_http_access": {
                "()": "df_config.guesses.log.HTTPAccessRecordFilter",
                "keep_access": False,
            },
        }
        if self.slow_query_duration_in_s:
            self.filters["slow_queries"] = {
                "()": "df_config.guesses.log.SlowQueriesFilter",
                "slow_query_duration_in_s": self.slow_query_duration_in_s,
            }

    def prepare_root(self):
        """Return the default log root."""
        self.root |= {"handlers": [], "level": self.log_level}

    def set_logger(
        self,
        logger,
        level: str = "NOTSET",
        propagate: bool = True,
        disabled: bool = False,
    ):
        """Add a logger entry to the configuration.

        Creates the logger dict with the given *level*, an empty handler list,
        and optional ``propagate`` / ``disabled`` flags.  If the logger is
        already registered, the existing entry is returned unchanged.

        :param logger: dotted logger name (e.g. ``"django.db.backends"``).
        :param level: minimum log level string; defaults to ``"NOTSET"``
            (i.e. inherit from the root logger).
        :param propagate: when ``False``, records are not forwarded to parent
            loggers.  Useful for access loggers that have their own handlers.
        :param disabled: when ``True``, the logger is explicitly disabled.
        :returns: the logger configuration dict (new or already existing).
        """
        if logger not in self.loggers:
            self.loggers[logger] = {
                "level": level or self.log_level,
                "handlers": [],
                "filters": [],
            }
            if not propagate:
                self.loggers[logger]["propagate"] = False
            if disabled:
                self.loggers[logger]["disabled"] = True
        return self.loggers[logger]

    def create_loggers(self):
        """Create all loggers and add handlers to them."""
        default_handlers = list(self.default_handlers)
        access_handlers = list(self.access_handlers)
        self.root["handlers"] += default_handlers
        for logger, levels in self.other_level_loggers.items():
            new_level = levels.get(self.log_level, self.log_level)
            self.set_logger(logger, level=new_level)
        for logger in self.disabled_loggers:
            self.set_logger(logger, level="CRITICAL", propagate=False, disabled=True)
        if self.slow_query_duration_in_s:
            self.set_logger("django.db.backends", level="INFO")
        self.set_logger("py.warnings", level=self.log_level)
        for logger in self.access_loggers:
            self.set_logger(logger, level="INFO")
            self.loggers[logger]["handlers"] += access_handlers

    def add_filters_to_loggers(self):
        """Attach specialized filters to specific loggers after creation.

        * ``django.db.backends`` receives the ``slow_queries`` filter when
          ``LOG_SLOW_QUERY_DURATION_IN_S`` is configured, so that only
          database queries exceeding the threshold are logged.
        * ``py.warnings`` receives the ``remove_duplicate_warnings`` filter
          to suppress repeated identical Python warnings.
        """
        if self.slow_query_duration_in_s:
            self.loggers["django.db.backends"]["filters"] = ["slow_queries"]
        self.loggers["py.warnings"]["filters"] = ["remove_duplicate_warnings"]


log_configuration = LoggingConfiguration()
