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
import re
import sys
import time
import warnings
from traceback import extract_stack
from urllib.parse import urlparse

from django.core.checks import Warning
from django.core.management import color_style
from django.utils.log import AdminEmailHandler as BaseAdminEmailHandler

from df_config.checks import settings_check_results


class ColorizedFormatter(logging.Formatter):
    """Used in console for applying colors to log lines, corresponding to the log level."""

    def __init__(self, *args, **kwargs):
        """Initialize the formatter."""
        self.style = color_style()
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

    def __init__(self, *args, **kwargs):
        """Initialize the object."""
        self.style = color_style()
        super().__init__(*args, **kwargs)

    def format(self, record):
        """Format an access, colorizing it depending on the status code."""
        msg = record.msg
        status_code = getattr(record, "status_code", None)
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
        return self._fmt.find("%(server_time)") >= 0


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

    def filter(self, record):
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

    def filter(self, record):
        """Filter SQL queries depending on their duration."""
        duration = getattr(record, "duration", 0)
        if duration > self.slow_query_duration_in_s:
            # Same as in _log for when stack_info=True is used.
            # noinspection PyTypeChecker
            fn, lno, func, sinfo = logging.Logger.findCaller(None, True)
            record.stack_info = sinfo
            return True
        return False


# noinspection PyMethodMayBeStatic
class LogConfiguration:
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
        "django.server": _level_access,
        "django.channels.server": _level_access,
        "geventwebsocket.handler": _level_access,
        "gunicorn.access": _level_access,
        "uvicorn.access": _level_access,
    }

    problem_loggers = {
        "django": _level_up,
        "django.db": _level_up,
        "django.db.backends.schema": _level_up,
        "django.db.backends": {
            "DEBUG": "DEBUG",
            "INFO": "DEBUG",
            "WARNING": "DEBUG",
            "ERROR": "ERROR",
            "CRITICAL": "CRITICAL",
        },
        "django.request": {},
        "django.security": {},
        "df_websockets.signals": {},
        "gunicorn.error": {},
        "uvicorn.error": {},
        "pip.vcs": _level_up,
        "py.warnings": _level_up,
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

    def __call__(self, settings_dict, argv=None):
        """Create the log configuration during the setting computation."""
        if argv is None:
            argv = sys.argv
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
            self.add_handler("ROOT", "stdout", level=log_level, formatter="colorized")
            for logger in self.access_loggers:
                self.add_handler(
                    logger, "stderr", formatter="django.server", level=log_level
                )
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
        if scheme == "syslog" or scheme == "syslog+tcp":
            address, facility, socktype = self.parse_syslog_url(
                parsed_log_url, scheme, device, facility_name
            )
            kwargs = {
                "address": address,
                "facility": facility,
                "socktype": socktype,
                "formatter": "nocolor",
            }
            self.add_handler("ROOT", "syslog", level=level, **kwargs)
            if log_remote_access:
                for logger in self.access_loggers:
                    self.add_handler(logger, "syslog", level="DEBUG", **kwargs)
            has_handler = True
        elif scheme == "loki" or scheme == "lokis":
            url = f"http://{parsed_log_url.hostname}"
            if scheme == "lokis":
                url = f"https://{parsed_log_url.hostname}"
            if parsed_log_url.port:
                url += f":{parsed_log_url.port}"
            if parsed_log_url.path:
                url += parsed_log_url.path
            if parsed_log_url.query:
                url += f"?{parsed_log_url}"
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
        socktype = socket.SOCK_DGRAM if scheme == "syslog" else socket.SOCK_STREAM
        # noinspection PyUnresolvedReferences
        facility = logging.handlers.SysLogHandler.facility_names.get(
            facility_name, syslog.LOG_USER
        )
        return address, facility, socktype

    @property
    def fmt_stderr(self):
        """Return the valid formatter for stderr (if it's a TTY)."""
        return "colorized" if self.stderr.isatty() else None

    @property
    def fmt_stdout(self):
        """Return the valid formatter for stderr (if it's a TTY)."""
        return "colorized" if self.stdout.isatty() else None

    def get_default_formatters(self):
        """Return some default formatters."""
        name = "%s:%s" % (self.server_name, self.server_port)
        return {
            "django.server": {
                "()": "df_config.guesses.log.ServerFormatter",
                "format": "%(asctime)s [{}] %(message)s".format(name),
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
    ):
        """Add a handler to a logger.

        The name of the added handler is unique, so the definition of the handler is also add if required.
        You can use "ROOT" as logger name to target the root logger.

        filename: can be a filename or one of the following special values: "stderr", "stdout", "logd", "syslog"
        """
        if filename == "stderr":
            handler, handler_name = self.add_handler_stderr(filename, formatter, level)
        elif filename == "stdout":
            handler, handler_name = self.add_handler_stdout(filename, formatter, level)
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
            return
        if handler_name not in self.handlers:
            self.handlers[handler_name] = handler
        if logger == "ROOT":
            target = self.root
        else:
            target = self.loggers[logger]
        if handler_name not in target["handlers"]:
            target["handlers"].append(handler_name)

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

    def add_handler_logd(self, logger, filename, level, kwargs):
        """Add a logd (systemd) handler when required and possible."""
        try:
            # noinspection PyUnresolvedReferences,PyPackageRequirements
            import systemd.journal
        except ImportError:
            warning = Warning(
                "Unable to import systemd.journal (required to log with journlad)",
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
        basename = f"{self.log_suffix}-{filename}.log"
        log_filename = os.path.join(log_directory, basename)
        try:
            remove = not os.path.exists(log_filename)
            open(log_filename, "a").close()  # ok, we can write
            if (
                remove
            ):  # but if this file did not exist, we remove it to avoid lot of empty log files...
                os.remove(log_filename)
        except PermissionError:
            warning_ = Warning(
                f"Unable to write logs in '{log_directory}' (unsufficient rights?).",
                hint=None,
                obj="configuration",
                id="df_config.W009",
            )
            settings_check_results.append(warning_)
            self.add_handler(logger, "stdout", level=level, **kwargs)
            return None, None
        handler_name = "%s.%s" % (self.log_suffix, filename)
        handler = {
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": 1000000,
            "backupCount": 3,
            "formatter": "nocolor",
            "filename": log_filename,
            "level": level,
            "delay": True,
        }
        return handler, handler_name

    def add_handler_stdout(self, filename, formatter, level):
        """Add an handler for stdout."""
        handler_name = f"{filename}.{level.lower()}"
        if formatter in ("django.server", "colorized") and not self.stdout.isatty():
            formatter = None
        elif formatter:
            handler_name += f".{formatter}"
        handler = {
            "class": "logging.StreamHandler",
            "level": level,
            "stream": "ext://sys.stdout",
            "formatter": formatter,
        }
        return handler, handler_name

    def add_handler_stderr(self, filename, formatter, level):
        """Add an handler for stderr."""
        handler_name = f"{filename}.{level.lower()}"
        if formatter in ("django.server", "colorized") and not self.stderr.isatty():
            formatter = None
        elif formatter:
            handler_name += f".{formatter}"
        handler = {
            "class": "logging.StreamHandler",
            "level": level,
            "stream": "ext://sys.stderr",
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


log_configuration = LogConfiguration()
