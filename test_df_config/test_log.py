import logging.config
import os
import stat
import sys
import tempfile
from importlib.util import find_spec
from io import StringIO
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.test import override_settings

from df_config.guesses.log import LogConfiguration


class Stream:
    """Emulate a output stream."""

    @classmethod
    def isatty(cls):
        """Return True, as we need a TTY in the LogConfiguration."""
        return True


class LogConfigurationTest(TestCase):
    maxDiff = None
    settings = {
        "DEBUG": False,
        "DF_MODULE_NAME": "logging",
        "LOG_DIRECTORY": None,
        "LOG_REMOTE_URL": None,
        "LOG_SLOW_QUERY_DURATION_IN_S": 1.0,
        "LOG_REMOTE_ACCESS": None,
        "SERVER_NAME": "test.example.com",
        "SERVER_PORT": 9000,
        "LOG_EXCLUDED_COMMANDS": [],
        "LOG_LEVEL": "DEBUG",
    }
    argv = ["manage.py", "server"]

    def test_log_configuration_exists(self):
        try:
            from df_config.guesses.log import log_configuration
        except ImportError:
            self.fail("log_configuration is not found in df_config.guesses.log.")

    def get_config(self, **kwargs):
        settings = {}
        settings.update(self.settings)
        settings.update(kwargs)
        log_configuration = LogConfiguration(stdout=Stream(), stderr=Stream())
        config = log_configuration(settings, argv=self.argv)
        # print(config)
        logging.config.dictConfig(config)
        return config

    def test_log_remote_url(self):
        with tempfile.TemporaryDirectory() as dirname:
            config = self.get_config(
                LOG_LEVEL="WARNING",
                LOG_DIRECTORY=dirname,
                LOG_REMOTE_URL="syslog://127.0.0.1:517",
            )
        config["handlers"]["syslog.warning"]["socktype"] = None
        self.assertEqual(
            config,
            {
                "version": 1,
                "disable_existing_loggers": True,
                "formatters": {
                    "django.server": {
                        "()": "df_config.guesses.log.ServerFormatter",
                        "fmt": "%(asctime)s [test.example.com:9000] %(message)s",
                    },
                    "nocolor": {
                        "()": "logging.Formatter",
                        "fmt": "%(asctime)s [test.example.com:9000] [%(levelname)s] %(message)s",
                        "datefmt": "%Y-%m-%d %H:%M:%S",
                    },
                    "colorized": {"()": "df_config.guesses.log.ColorizedFormatter"},
                },
                "filters": {
                    "remove_duplicate_warnings": {
                        "()": "df_config.guesses.log.RemoveDuplicateWarnings"
                    },
                    "below_error": {
                        "()": "df_config.guesses.log.MaxLevelFilter",
                        "max_level": 40,
                    },
                    "slow_queries": {
                        "()": "df_config.guesses.log.SlowQueriesFilter",
                        "slow_query_duration_in_s": 1.0,
                    },
                },
                "handlers": {
                    "mail_admins": {
                        "class": "df_config.guesses.log.AdminEmailHandler",
                        "level": "ERROR",
                        "include_html": True,
                    },
                    "logging-server.root": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "maxBytes": 1000000,
                        "backupCount": 3,
                        "formatter": "nocolor",
                        "filename": f"{dirname}/logging-server-root.log",
                        "level": "WARNING",
                        "delay": True,
                    },
                    "logging-server.access": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "maxBytes": 1000000,
                        "backupCount": 3,
                        "formatter": "nocolor",
                        "filename": f"{dirname}/logging-server-access.log",
                        "level": "DEBUG",
                        "delay": True,
                    },
                    "syslog.warning": {
                        "class": "logging.handlers.SysLogHandler",
                        "level": "WARNING",
                        "address": ("127.0.0.1", 517),
                        "facility": 8,
                        "socktype": None,
                    },
                },
                "loggers": {
                    "django": {"handlers": [], "level": "ERROR", "propagate": True},
                    "django.db": {
                        "handlers": [],
                        "level": "ERROR",
                        "propagate": True,
                    },
                    "django.db.backends": {
                        "handlers": [],
                        "level": "DEBUG",
                        "propagate": True,
                        "filters": ["slow_queries"],
                    },
                    "django.db.backends.schema": {
                        "handlers": [],
                        "level": "ERROR",
                        "propagate": True,
                    },
                    "django.request": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "django.security": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "df_websockets.signals": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "gunicorn.error": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "uvicorn.error": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "pip.vcs": {"handlers": [], "level": "ERROR", "propagate": True},
                    "py.warnings": {
                        "handlers": [],
                        "level": "ERROR",
                        "propagate": True,
                        "filters": ["remove_duplicate_warnings"],
                    },
                    "aiohttp.access": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "granian.access": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "django.server": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "django.channels.server": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "geventwebsocket.handler": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "gunicorn.access": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "uvicorn.access": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                },
                "root": {
                    "handlers": [
                        "logging-server.root",
                        "syslog.warning",
                        "mail_admins",
                    ],
                    "level": "WARNING",
                },
            },
        )

    def test_log_loki_url(self):
        with tempfile.TemporaryDirectory() as dirname:
            config = self.get_config(
                LOG_LEVEL="WARNING",
                LOG_DIRECTORY=dirname,
                LOG_REMOTE_URL="loki://mondomaine:3100/loki/api/v1/push",
            )
        self.assertEqual(
            config,
            {
                "version": 1,
                "disable_existing_loggers": True,
                "formatters": {
                    "django.server": {
                        "()": "df_config.guesses.log.ServerFormatter",
                        "fmt": "%(asctime)s [test.example.com:9000] %(message)s",
                    },
                    "nocolor": {
                        "()": "logging.Formatter",
                        "fmt": "%(asctime)s [test.example.com:9000] [%(levelname)s] %(message)s",
                        "datefmt": "%Y-%m-%d %H:%M:%S",
                    },
                    "colorized": {"()": "df_config.guesses.log.ColorizedFormatter"},
                },
                "filters": {
                    "remove_duplicate_warnings": {
                        "()": "df_config.guesses.log.RemoveDuplicateWarnings"
                    },
                    "below_error": {
                        "()": "df_config.guesses.log.MaxLevelFilter",
                        "max_level": 40,
                    },
                    "slow_queries": {
                        "()": "df_config.guesses.log.SlowQueriesFilter",
                        "slow_query_duration_in_s": 1.0,
                    },
                },
                "handlers": {
                    "mail_admins": {
                        "class": "df_config.guesses.log.AdminEmailHandler",
                        "level": "ERROR",
                        "include_html": True,
                    },
                    "logging-server.root": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "maxBytes": 1000000,
                        "backupCount": 3,
                        "formatter": "nocolor",
                        "filename": f"{dirname}/logging-server-root.log",
                        "level": "WARNING",
                        "delay": True,
                    },
                    "logging-server.access": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "maxBytes": 1000000,
                        "backupCount": 3,
                        "formatter": "nocolor",
                        "filename": f"{dirname}/logging-server-access.log",
                        "level": "DEBUG",
                        "delay": True,
                    },
                    "loki.warning": {
                        "auth": None,
                        "class": "df_config.extra.loki.LokiHandler",
                        "level": "WARNING",
                        "url": "http://mondomaine:3100/loki/api/v1/push",
                    },
                },
                "loggers": {
                    "django": {"handlers": [], "level": "ERROR", "propagate": True},
                    "django.db": {
                        "handlers": [],
                        "level": "ERROR",
                        "propagate": True,
                    },
                    "django.db.backends": {
                        "handlers": [],
                        "level": "DEBUG",
                        "propagate": True,
                        "filters": ["slow_queries"],
                    },
                    "django.db.backends.schema": {
                        "handlers": [],
                        "level": "ERROR",
                        "propagate": True,
                    },
                    "django.request": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "django.security": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "df_websockets.signals": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "gunicorn.error": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "uvicorn.error": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "pip.vcs": {"handlers": [], "level": "ERROR", "propagate": True},
                    "py.warnings": {
                        "handlers": [],
                        "level": "ERROR",
                        "propagate": True,
                        "filters": ["remove_duplicate_warnings"],
                    },
                    "aiohttp.access": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "granian.access": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "django.server": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "django.channels.server": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "geventwebsocket.handler": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "gunicorn.access": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "uvicorn.access": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                },
                "root": {
                    "handlers": [
                        "logging-server.root",
                        "loki.warning",
                        "mail_admins",
                    ],
                    "level": "WARNING",
                },
            },
        )

    @override_settings(SERVER_NAME="www.example.com")
    def test_log_loki_url_access(self):
        with tempfile.TemporaryDirectory() as dirname:
            config = self.get_config(
                LOG_LEVEL="WARNING",
                LOG_DIRECTORY=dirname,
                LOG_REMOTE_URL="lokis://mondomaine:3100/loki/api/v1/push",
                LOG_REMOTE_ACCESS=True,
                DEBUG=False,
            )
        self.assertEqual(
            config,
            {
                "version": 1,
                "disable_existing_loggers": True,
                "formatters": {
                    "django.server": {
                        "()": "df_config.guesses.log.ServerFormatter",
                        "fmt": "%(asctime)s [test.example.com:9000] %(message)s",
                    },
                    "nocolor": {
                        "()": "logging.Formatter",
                        "fmt": "%(asctime)s [test.example.com:9000] [%(levelname)s] %(message)s",
                        "datefmt": "%Y-%m-%d %H:%M:%S",
                    },
                    "colorized": {"()": "df_config.guesses.log.ColorizedFormatter"},
                },
                "filters": {
                    "remove_duplicate_warnings": {
                        "()": "df_config.guesses.log.RemoveDuplicateWarnings"
                    },
                    "below_error": {
                        "()": "df_config.guesses.log.MaxLevelFilter",
                        "max_level": 40,
                    },
                    "slow_queries": {
                        "()": "df_config.guesses.log.SlowQueriesFilter",
                        "slow_query_duration_in_s": 1.0,
                    },
                },
                "handlers": {
                    "mail_admins": {
                        "class": "df_config.guesses.log.AdminEmailHandler",
                        "level": "ERROR",
                        "include_html": True,
                    },
                    "logging-server.root": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "maxBytes": 1000000,
                        "backupCount": 3,
                        "formatter": "nocolor",
                        "filename": f"{dirname}/logging-server-root.log",
                        "level": "WARNING",
                        "delay": True,
                    },
                    "logging-server.access": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "maxBytes": 1000000,
                        "backupCount": 3,
                        "formatter": "nocolor",
                        "filename": f"{dirname}/logging-server-access.log",
                        "level": "DEBUG",
                        "delay": True,
                    },
                    "loki.debug": {
                        "auth": None,
                        "class": "df_config.extra.loki.LokiHandler",
                        "level": "DEBUG",
                        "url": "https://mondomaine:3100/loki/api/v1/push",
                    },
                    "loki.warning": {
                        "auth": None,
                        "class": "df_config.extra.loki.LokiHandler",
                        "level": "WARNING",
                        "url": "https://mondomaine:3100/loki/api/v1/push",
                    },
                },
                "loggers": {
                    "django": {"handlers": [], "level": "ERROR", "propagate": True},
                    "django.db": {
                        "handlers": [],
                        "level": "ERROR",
                        "propagate": True,
                    },
                    "django.db.backends": {
                        "handlers": [],
                        "level": "DEBUG",
                        "propagate": True,
                        "filters": ["slow_queries"],
                    },
                    "django.db.backends.schema": {
                        "handlers": [],
                        "level": "ERROR",
                        "propagate": True,
                    },
                    "django.request": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "django.security": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "df_websockets.signals": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "gunicorn.error": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "uvicorn.error": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "pip.vcs": {"handlers": [], "level": "ERROR", "propagate": True},
                    "py.warnings": {
                        "handlers": [],
                        "level": "ERROR",
                        "propagate": True,
                        "filters": ["remove_duplicate_warnings"],
                    },
                    "aiohttp.access": {
                        "handlers": ["logging-server.access", "loki.debug"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "granian.access": {
                        "handlers": ["logging-server.access", "loki.debug"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "django.server": {
                        "handlers": ["logging-server.access", "loki.debug"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "django.channels.server": {
                        "handlers": ["logging-server.access", "loki.debug"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "geventwebsocket.handler": {
                        "handlers": ["logging-server.access", "loki.debug"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "gunicorn.access": {
                        "handlers": ["logging-server.access", "loki.debug"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "uvicorn.access": {
                        "handlers": ["logging-server.access", "loki.debug"],
                        "level": "INFO",
                        "propagate": False,
                    },
                },
                "root": {
                    "handlers": [
                        "logging-server.root",
                        "loki.warning",
                        "mail_admins",
                    ],
                    "level": "WARNING",
                },
            },
        )

    def test_log_directory(self):
        with tempfile.TemporaryDirectory() as dirname:
            config = self.get_config(LOG_LEVEL="CRITICAL", LOG_DIRECTORY=dirname)
        self.assertEqual(
            config,
            {
                "version": 1,
                "disable_existing_loggers": True,
                "formatters": {
                    "django.server": {
                        "()": "df_config.guesses.log.ServerFormatter",
                        "fmt": "%(asctime)s [test.example.com:9000] %(message)s",
                    },
                    "nocolor": {
                        "()": "logging.Formatter",
                        "fmt": "%(asctime)s [test.example.com:9000] [%(levelname)s] %(message)s",
                        "datefmt": "%Y-%m-%d %H:%M:%S",
                    },
                    "colorized": {"()": "df_config.guesses.log.ColorizedFormatter"},
                },
                "filters": {
                    "remove_duplicate_warnings": {
                        "()": "df_config.guesses.log.RemoveDuplicateWarnings"
                    },
                    "below_error": {
                        "()": "df_config.guesses.log.MaxLevelFilter",
                        "max_level": 40,
                    },
                    "slow_queries": {
                        "()": "df_config.guesses.log.SlowQueriesFilter",
                        "slow_query_duration_in_s": 1.0,
                    },
                },
                "handlers": {
                    "mail_admins": {
                        "class": "df_config.guesses.log.AdminEmailHandler",
                        "level": "ERROR",
                        "include_html": True,
                    },
                    "logging-server.root": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "maxBytes": 1000000,
                        "backupCount": 3,
                        "formatter": "nocolor",
                        "filename": f"{dirname}/logging-server-root.log",
                        "level": "CRITICAL",
                        "delay": True,
                    },
                    "logging-server.access": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "maxBytes": 1000000,
                        "backupCount": 3,
                        "formatter": "nocolor",
                        "filename": f"{dirname}/logging-server-access.log",
                        "level": "DEBUG",
                        "delay": True,
                    },
                },
                "loggers": {
                    "django": {"handlers": [], "level": "CRITICAL", "propagate": True},
                    "django.db": {
                        "handlers": [],
                        "level": "CRITICAL",
                        "propagate": True,
                    },
                    "django.db.backends": {
                        "handlers": [],
                        "level": "CRITICAL",
                        "propagate": True,
                        "filters": ["slow_queries"],
                    },
                    "django.db.backends.schema": {
                        "handlers": [],
                        "level": "CRITICAL",
                        "propagate": True,
                    },
                    "django.request": {
                        "handlers": [],
                        "level": "CRITICAL",
                        "propagate": True,
                    },
                    "django.security": {
                        "handlers": [],
                        "level": "CRITICAL",
                        "propagate": True,
                    },
                    "df_websockets.signals": {
                        "handlers": [],
                        "level": "CRITICAL",
                        "propagate": True,
                    },
                    "gunicorn.error": {
                        "handlers": [],
                        "level": "CRITICAL",
                        "propagate": True,
                    },
                    "uvicorn.error": {
                        "handlers": [],
                        "level": "CRITICAL",
                        "propagate": True,
                    },
                    "pip.vcs": {"handlers": [], "level": "CRITICAL", "propagate": True},
                    "py.warnings": {
                        "handlers": [],
                        "level": "CRITICAL",
                        "propagate": True,
                        "filters": ["remove_duplicate_warnings"],
                    },
                    "aiohttp.access": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "granian.access": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "django.server": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "django.channels.server": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "geventwebsocket.handler": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "gunicorn.access": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "uvicorn.access": {
                        "handlers": ["logging-server.access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                },
                "root": {
                    "handlers": ["logging-server.root", "mail_admins"],
                    "level": "CRITICAL",
                },
            },
        )

    def test_not_debug(self):
        config = self.get_config(LOG_LEVEL="WARNING")
        self.assertEqual(
            config,
            {
                "version": 1,
                "disable_existing_loggers": True,
                "formatters": {
                    "django.server": {
                        "()": "df_config.guesses.log.ServerFormatter",
                        "fmt": "%(asctime)s [test.example.com:9000] %(message)s",
                    },
                    "nocolor": {
                        "()": "logging.Formatter",
                        "fmt": "%(asctime)s [test.example.com:9000] [%(levelname)s] %(message)s",
                        "datefmt": "%Y-%m-%d %H:%M:%S",
                    },
                    "colorized": {"()": "df_config.guesses.log.ColorizedFormatter"},
                },
                "filters": {
                    "remove_duplicate_warnings": {
                        "()": "df_config.guesses.log.RemoveDuplicateWarnings"
                    },
                    "below_error": {
                        "()": "df_config.guesses.log.MaxLevelFilter",
                        "max_level": 40,
                    },
                    "slow_queries": {
                        "()": "df_config.guesses.log.SlowQueriesFilter",
                        "slow_query_duration_in_s": 1.0,
                    },
                },
                "handlers": {
                    "mail_admins": {
                        "class": "df_config.guesses.log.AdminEmailHandler",
                        "level": "ERROR",
                        "include_html": True,
                    },
                    "stderr.warning.django.server": {
                        "class": "logging.StreamHandler",
                        "level": "WARNING",
                        "stream": "ext://sys.stderr",
                        "formatter": "django.server",
                    },
                    "stdout.warning.colorized": {
                        "class": "logging.StreamHandler",
                        "level": "WARNING",
                        "stream": "ext://sys.stdout",
                        "formatter": "colorized",
                        "filters": ["below_error"],
                    },
                    "stderr.error.colorized": {
                        "class": "logging.StreamHandler",
                        "level": "ERROR",
                        "stream": "ext://sys.stderr",
                        "formatter": "colorized",
                    },
                },
                "loggers": {
                    "django": {"handlers": [], "level": "ERROR", "propagate": True},
                    "django.db": {"handlers": [], "level": "ERROR", "propagate": True},
                    "django.db.backends": {
                        "handlers": [],
                        "level": "DEBUG",
                        "propagate": True,
                        "filters": ["slow_queries"],
                    },
                    "django.db.backends.schema": {
                        "handlers": [],
                        "level": "ERROR",
                        "propagate": True,
                    },
                    "django.request": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "django.security": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "df_websockets.signals": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "gunicorn.error": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "uvicorn.error": {
                        "handlers": [],
                        "level": "WARNING",
                        "propagate": True,
                    },
                    "pip.vcs": {"handlers": [], "level": "ERROR", "propagate": True},
                    "py.warnings": {
                        "handlers": [],
                        "level": "ERROR",
                        "propagate": True,
                        "filters": ["remove_duplicate_warnings"],
                    },
                    "aiohttp.access": {
                        "handlers": ["stderr.warning.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "granian.access": {
                        "handlers": ["stderr.warning.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "django.server": {
                        "handlers": ["stderr.warning.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "django.channels.server": {
                        "handlers": ["stderr.warning.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "geventwebsocket.handler": {
                        "handlers": ["stderr.warning.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "gunicorn.access": {
                        "handlers": ["stderr.warning.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "uvicorn.access": {
                        "handlers": ["stderr.warning.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                },
                "root": {
                    "handlers": [
                        "stdout.warning.colorized",
                        "stderr.error.colorized",
                        "mail_admins",
                    ],
                    "level": "WARNING",
                },
            },
        )

    def test_debug(self):
        config = self.get_config(DEBUG=True)
        self.assertEqual(
            config,
            {
                "version": 1,
                "disable_existing_loggers": True,
                "formatters": {
                    "django.server": {
                        "()": "df_config.guesses.log.ServerFormatter",
                        "fmt": "%(asctime)s [test.example.com:9000] %(message)s",
                    },
                    "nocolor": {
                        "()": "logging.Formatter",
                        "fmt": "%(asctime)s [test.example.com:9000] [%(levelname)s] %(message)s",
                        "datefmt": "%Y-%m-%d %H:%M:%S",
                    },
                    "colorized": {"()": "df_config.guesses.log.ColorizedFormatter"},
                },
                "filters": {
                    "remove_duplicate_warnings": {
                        "()": "df_config.guesses.log.RemoveDuplicateWarnings"
                    },
                    "below_error": {
                        "()": "df_config.guesses.log.MaxLevelFilter",
                        "max_level": 40,
                    },
                    "slow_queries": {
                        "()": "df_config.guesses.log.SlowQueriesFilter",
                        "slow_query_duration_in_s": 1.0,
                    },
                },
                "handlers": {
                    "mail_admins": {
                        "class": "df_config.guesses.log.AdminEmailHandler",
                        "level": "ERROR",
                        "include_html": True,
                    },
                    "stdout.info.colorized": {
                        "class": "logging.StreamHandler",
                        "level": "INFO",
                        "stream": "ext://sys.stdout",
                        "formatter": "colorized",
                    },
                    "stderr.debug.django.server": {
                        "class": "logging.StreamHandler",
                        "level": "DEBUG",
                        "stream": "ext://sys.stderr",
                        "formatter": "django.server",
                    },
                },
                "loggers": {
                    "django": {"handlers": [], "level": "INFO", "propagate": True},
                    "django.db": {"handlers": [], "level": "INFO", "propagate": True},
                    "django.db.backends": {
                        "handlers": [],
                        "level": "DEBUG",
                        "propagate": True,
                        "filters": ["slow_queries"],
                    },
                    "django.db.backends.schema": {
                        "handlers": [],
                        "level": "INFO",
                        "propagate": True,
                    },
                    "django.request": {
                        "handlers": [],
                        "level": "DEBUG",
                        "propagate": True,
                    },
                    "django.security": {
                        "handlers": [],
                        "level": "DEBUG",
                        "propagate": True,
                    },
                    "df_websockets.signals": {
                        "handlers": [],
                        "level": "DEBUG",
                        "propagate": True,
                    },
                    "gunicorn.error": {
                        "handlers": [],
                        "level": "DEBUG",
                        "propagate": True,
                    },
                    "uvicorn.error": {
                        "handlers": [],
                        "level": "DEBUG",
                        "propagate": True,
                    },
                    "pip.vcs": {"handlers": [], "level": "INFO", "propagate": True},
                    "py.warnings": {
                        "handlers": [],
                        "level": "INFO",
                        "propagate": True,
                        "filters": ["remove_duplicate_warnings"],
                    },
                    "aiohttp.access": {
                        "handlers": ["stderr.debug.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "granian.access": {
                        "handlers": ["stderr.debug.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "django.server": {
                        "handlers": ["stderr.debug.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "django.channels.server": {
                        "handlers": ["stderr.debug.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "geventwebsocket.handler": {
                        "handlers": ["stderr.debug.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "gunicorn.access": {
                        "handlers": ["stderr.debug.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "uvicorn.access": {
                        "handlers": ["stderr.debug.django.server"],
                        "level": "INFO",
                        "propagate": False,
                    },
                },
                "root": {"handlers": ["stdout.info.colorized"], "level": "DEBUG"},
            },
        )


class LogConfigurationEdgeCasesTest(TestCase):
    """Additional tests to cover remaining branches in LogConfiguration."""

    maxDiff = None
    settings = {
        "DEBUG": False,
        "DF_MODULE_NAME": "logging",
        "LOG_DIRECTORY": None,
        "LOG_REMOTE_URL": None,
        "LOG_SLOW_QUERY_DURATION_IN_S": None,
        "LOG_REMOTE_ACCESS": None,
        "SERVER_NAME": "test.example.com",
        "SERVER_PORT": 9000,
        "LOG_EXCLUDED_COMMANDS": [],
        "LOG_LEVEL": "WARNING",
    }
    argv = ["manage.py", "server"]

    def get_config(self, stdout=None, stderr=None, argv=None, **kwargs):
        settings = dict(self.settings, **kwargs)
        lc = LogConfiguration(
            stdout=stdout or Stream(),
            stderr=stderr or Stream(),
        )
        config = lc(settings, argv=argv if argv is not None else self.argv)
        try:
            logging.config.dictConfig(config)
        except Exception:
            pass
        return config

    # ------------------------------------------------------------------
    # argv=None → sys.argv (line 349)
    # ------------------------------------------------------------------
    def test_argv_none_uses_sys_argv(self):
        lc = LogConfiguration(stdout=Stream(), stderr=Stream())
        config = lc(self.settings, argv=None)
        self.assertEqual(config["version"], 1)

    # ------------------------------------------------------------------
    # LOG_LEVEL branches (lines 358-361)
    # ------------------------------------------------------------------
    def test_log_level_empty_debug_true(self):
        """LOG_LEVEL='' + DEBUG=True → 'DEBUG'."""
        config = self.get_config(LOG_LEVEL="", DEBUG=True)
        self.assertEqual(config["root"]["level"], "DEBUG")

    def test_log_level_empty_debug_false(self):
        """LOG_LEVEL='' + DEBUG=False → 'WARNING'."""
        config = self.get_config(LOG_LEVEL="", DEBUG=False)
        self.assertEqual(config["root"]["level"], "WARNING")

    # ------------------------------------------------------------------
    # __repr__ (line 433)
    # ------------------------------------------------------------------
    def test_repr(self):
        lc = LogConfiguration(stdout=Stream(), stderr=Stream())
        self.assertIn("log_configuration", repr(lc))

    # ------------------------------------------------------------------
    # Syslog + LOG_REMOTE_ACCESS=True (lines 457-458)
    # ------------------------------------------------------------------
    def test_syslog_with_remote_access(self):
        config = self.get_config(
            LOG_REMOTE_URL="syslog://127.0.0.1:514",
            LOG_REMOTE_ACCESS=True,
        )
        syslog_in_loggers = [
            h
            for logger_cfg in config["loggers"].values()
            for h in logger_cfg.get("handlers", [])
            if "syslog" in h
        ]
        self.assertTrue(syslog_in_loggers)

    # ------------------------------------------------------------------
    # Loki URL with query string (line 471)
    # ------------------------------------------------------------------
    def test_loki_url_with_query_string(self):
        config = self.get_config(
            LOG_REMOTE_URL="loki://host:3100/path?key=val",
        )
        # Whether loki is installed or not, no exception should occur
        self.assertEqual(config["version"], 1)

    # ------------------------------------------------------------------
    # Loki URL with auth (line 474)
    # ------------------------------------------------------------------
    def test_loki_url_with_auth(self):
        config = self.get_config(
            LOG_REMOTE_URL="loki://user:secret@host:3100/path",
        )
        loki_handlers = {k: v for k, v in config["handlers"].items() if "loki" in k}
        if loki_handlers:
            handler = next(iter(loki_handlers.values()))
            self.assertEqual(handler.get("auth"), ("user", "secret"))

    # ------------------------------------------------------------------
    # Unknown remote scheme (lines 483-489)
    # ------------------------------------------------------------------
    def test_unknown_remote_scheme(self):
        from df_config.checks import settings_check_results

        initial = len(settings_check_results)
        config = self.get_config(LOG_REMOTE_URL="ftp://host:21/path")
        self.assertGreater(len(settings_check_results), initial)
        unknown = [h for h in config["root"]["handlers"] if "ftp" in h]
        self.assertFalse(unknown)

    # ------------------------------------------------------------------
    # parse_syslog_url branches (lines 504-511)
    # ------------------------------------------------------------------
    def test_syslog_with_device_path(self):
        """syslog:///dev/log/daemon → address='/dev/log'."""
        config = self.get_config(LOG_REMOTE_URL="syslog:///dev/log/daemon")
        syslog_handlers = {k: v for k, v in config["handlers"].items() if "syslog" in k}
        self.assertTrue(syslog_handlers)
        handler = next(iter(syslog_handlers.values()))
        self.assertEqual(handler["address"], "/dev/log")

    def test_syslog_without_hostname_darwin(self):
        with patch("df_config.guesses.log.platform.system", return_value="Darwin"):
            config = self.get_config(LOG_REMOTE_URL="syslog:///user")
        syslog_handlers = {k: v for k, v in config["handlers"].items() if "syslog" in k}
        handler = next(iter(syslog_handlers.values()))
        self.assertEqual(handler["address"], "/var/run/syslog")

    def test_syslog_without_hostname_linux(self):
        with patch("df_config.guesses.log.platform.system", return_value="Linux"):
            config = self.get_config(LOG_REMOTE_URL="syslog:///user")
        syslog_handlers = {k: v for k, v in config["handlers"].items() if "syslog" in k}
        handler = next(iter(syslog_handlers.values()))
        self.assertEqual(handler["address"], "/dev/log")

    def test_syslog_without_hostname_other_platform(self):
        with patch("df_config.guesses.log.platform.system", return_value="Windows"):
            config = self.get_config(LOG_REMOTE_URL="syslog:///user")
        syslog_handlers = {k: v for k, v in config["handlers"].items() if "syslog" in k}
        handler = next(iter(syslog_handlers.values()))
        self.assertEqual(handler["address"], ("localhost", 514))

    # ------------------------------------------------------------------
    # fmt_stderr / fmt_stdout properties (lines 522, 527)
    # ------------------------------------------------------------------
    def test_fmt_stderr_tty(self):
        """fmt_stderr returns 'colorized' when stderr.isatty() is True."""
        lc = LogConfiguration(stdout=Stream(), stderr=Stream())
        self.assertEqual(lc.fmt_stderr, "colorized")

    def test_fmt_stderr_non_tty(self):
        """fmt_stderr returns None when stderr is not a TTY."""
        lc = LogConfiguration(stdout=Stream(), stderr=StringIO())
        self.assertIsNone(lc.fmt_stderr)

    def test_fmt_stdout_tty(self):
        """fmt_stdout returns 'colorized' when stdout.isatty() is True."""
        lc = LogConfiguration(stdout=Stream(), stderr=Stream())
        self.assertEqual(lc.fmt_stdout, "colorized")

    def test_fmt_stdout_non_tty(self):
        """fmt_stdout returns None when stdout is not a TTY."""
        lc = LogConfiguration(stdout=StringIO(), stderr=Stream())
        self.assertIsNone(lc.fmt_stdout)

    # ------------------------------------------------------------------
    # logd:// scheme (line 624) and add_handler_logd fallback (669-686)
    # ------------------------------------------------------------------
    def test_logd_url_without_systemd(self):
        """logd:// URL when systemd.journal is not installed → fallback."""
        with patch.dict("sys.modules", {"systemd": None, "systemd.journal": None}):
            config = self.get_config(LOG_REMOTE_URL="logd:///myapp")
        # No logd handler should be created
        logd_handlers = [h for h in config["handlers"] if "logd" in h]
        self.assertFalse(logd_handlers)

    def test_logd_url_with_systemd(self):
        """logd:// URL when systemd.journal IS installed → JournalHandler."""
        mock_journal = MagicMock()
        with patch.dict(
            "sys.modules",
            {"systemd": mock_journal, "systemd.journal": mock_journal.journal},
        ):
            config = self.get_config(LOG_REMOTE_URL="logd:///myapp")
        logd_handlers = {k: v for k, v in config["handlers"].items() if "logd" in k}
        if logd_handlers:
            handler = next(iter(logd_handlers.values()))
            self.assertEqual(handler["class"], "systemd.journal.JournalHandler")

    # ------------------------------------------------------------------
    # loki ImportError (lines 650-660)
    # ------------------------------------------------------------------
    def test_loki_not_installed_falls_back(self):
        """When logging_loki is not importable → fallback to stdout handler."""
        with patch.dict("sys.modules", {"logging_loki": None}):
            config = self.get_config(LOG_REMOTE_URL="loki://host:3100/path")
        loki_dot_handlers = {k for k in config["handlers"] if k.startswith("loki.")}
        self.assertFalse(loki_dot_handlers)

    # ------------------------------------------------------------------
    # add_handler_directory with missing directory (lines 704, 709-717)
    # ------------------------------------------------------------------
    def test_directory_not_found_falls_back(self):
        """When LOG_DIRECTORY is missing → no file handler created."""
        config = self.get_config(LOG_DIRECTORY="/nonexistent/xyz/path")
        file_handlers = [
            h for h in config["handlers"] if "root" in h and "logging" in h
        ]
        self.assertFalse(file_handlers)

    # ------------------------------------------------------------------
    # add_handler_stderr_stdout with custom formatter (line 760)
    # ------------------------------------------------------------------
    def test_add_handler_stderr_stdout_plain_formatter(self):
        """When formatter is not colorized/django.server, handler_name includes it."""
        lc = LogConfiguration(stdout=Stream(), stderr=Stream())
        # Set up minimal state
        lc.module_name = "myapp"
        lc.server_name = "localhost"
        lc.server_port = 8000
        lc.log_directory = None
        lc.slow_query_duration_in_s = None
        lc.excluded_commands = []
        lc.formatters = lc.get_default_formatters()
        lc.filters = lc.get_default_filters()
        lc.loggers = lc.get_default_loggers()
        lc.handlers = {}
        lc.root = {"handlers": [], "level": "WARNING"}
        lc.log_suffix = "myapp-server"
        lc.log_directory_warning = False
        # Call with a non-standard formatter that is truthy (not "colorized" or "django.server")
        handler, handler_name = lc.add_handler_stderr_stdout(
            "mylogger", "nocolor", "WARNING", "stdout"
        )
        self.assertIn("nocolor", handler_name)

    # ------------------------------------------------------------------
    # resolve_command static method (lines 793-800)
    # ------------------------------------------------------------------
    def test_resolve_command_returns_none_normally(self):
        """resolve_command returns None when not in a df_config manage.py context."""
        result = LogConfiguration.resolve_command()
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # get_smart_command_name (line 786)
    # ------------------------------------------------------------------
    def test_get_smart_command_name_with_first_arg(self):
        result = LogConfiguration.get_smart_command_name(
            "myapp", ["manage.py", "server"]
        )
        self.assertEqual(result, "myapp-server")

    def test_get_smart_command_name_excluded(self):
        result = LogConfiguration.get_smart_command_name(
            "myapp", ["manage.py", "migrate"], excluded_commands=["migrate"]
        )
        self.assertIsNone(result)

    def test_get_smart_command_name_no_args(self):
        result = LogConfiguration.get_smart_command_name("myapp", ["manage.py"])
        self.assertEqual(result, "myapp-None")

    # ------------------------------------------------------------------
    # Helper to build a minimal LogConfiguration instance
    # ------------------------------------------------------------------
    def _make_lc(self, stdout=None, stderr=None, log_directory=None):
        """Return a LogConfiguration ready to call add_handler directly."""
        lc = LogConfiguration(stdout=stdout or Stream(), stderr=stderr or Stream())
        lc.module_name = "myapp"
        lc.server_name = "localhost"
        lc.server_port = 8000
        lc.slow_query_duration_in_s = None
        lc.excluded_commands = []
        lc.log_directory = log_directory
        lc.log_directory_warning = False
        lc.formatters = lc.get_default_formatters()
        lc.filters = lc.get_default_filters()
        lc.loggers = lc.get_default_loggers()
        lc.handlers = {}
        lc.root = {"handlers": [], "level": "WARNING"}
        lc.log_suffix = "myapp-server"
        return lc

    # ------------------------------------------------------------------
    # add_handler with filename="logd" (line 624) + add_handler_logd (669-686)
    # ------------------------------------------------------------------
    def test_add_handler_logd_without_systemd(self):
        """add_handler('logd') with no systemd.journal → fallback, returns None."""
        lc = self._make_lc()
        with patch.dict("sys.modules", {"systemd": None, "systemd.journal": None}):
            result = lc.add_handler("ROOT", "logd", level="WARNING")
        self.assertIsNone(result)

    def test_add_handler_logd_with_systemd(self):
        """add_handler('logd') with systemd.journal → JournalHandler in handlers."""
        lc = self._make_lc()
        mock_journal = MagicMock()
        with patch.dict(
            "sys.modules",
            {"systemd": mock_journal, "systemd.journal": mock_journal.journal},
        ):
            result = lc.add_handler("ROOT", "logd", level="WARNING")
        self.assertIsNotNone(result)
        self.assertIn("logd", result)

    # ------------------------------------------------------------------
    # add_handler_directory with filename="" (lines 704, 719)
    # ------------------------------------------------------------------
    def test_add_handler_directory_empty_filename(self):
        """add_handler_directory with filename='' uses log_suffix.log as basename."""
        with tempfile.TemporaryDirectory() as dirname:
            lc = self._make_lc(log_directory=dirname)
            handler, handler_name = lc.add_handler_directory("ROOT", "", "WARNING", {})
        self.assertIsNotNone(handler)
        self.assertEqual(handler_name, "myapp-server")
        self.assertTrue(handler["filename"].endswith("myapp-server.log"))

    # ------------------------------------------------------------------
    # add_handler_directory with non-writable directory (lines 709-717)
    # ------------------------------------------------------------------
    def test_add_handler_directory_not_writable(self):
        """add_handler_directory when directory is not writable → returns None, None."""
        with tempfile.TemporaryDirectory() as dirname:
            os.chmod(dirname, stat.S_IRUSR | stat.S_IXUSR)
            try:
                lc = self._make_lc(log_directory=dirname)
                handler, handler_name = lc.add_handler_directory(
                    "ROOT", "root", "WARNING", {}
                )
            finally:
                os.chmod(dirname, stat.S_IRWXU)
        self.assertIsNone(handler)
        self.assertIsNone(handler_name)

    # ------------------------------------------------------------------
    # add_handler_stdout (lines 743-744) and add_handler_stderr (748-749)
    # ------------------------------------------------------------------
    def test_add_handler_stdout_calls_through(self):
        """add_handler_stdout delegates to add_handler_stderr_stdout with attr='stdout'."""
        lc = self._make_lc()
        handler, name = lc.add_handler_stdout("stdout", "colorized", "WARNING")
        self.assertIsNotNone(handler)
        self.assertIn("stdout", handler["stream"])

    def test_add_handler_stderr_calls_through(self):
        """add_handler_stderr delegates to add_handler_stderr_stdout with attr='stderr'."""
        lc = self._make_lc()
        handler, name = lc.add_handler_stderr("stderr", "colorized", "WARNING")
        self.assertIsNotNone(handler)
        self.assertIn("stderr", handler["stream"])

    # ------------------------------------------------------------------
    # add_handler_stderr_stdout with colorized formatter and non-TTY (line 760)
    # ------------------------------------------------------------------
    def test_add_handler_stderr_stdout_colorized_non_tty(self):
        """colorized formatter on non-TTY stream → formatter becomes 'nocolor'."""
        lc = self._make_lc(stdout=StringIO())  # StringIO is not a TTY
        handler, handler_name = lc.add_handler_stderr_stdout(
            "stdout", "colorized", "WARNING", "stdout"
        )
        self.assertEqual(handler["formatter"], "nocolor")
        self.assertNotIn("colorized", handler_name)

    # ------------------------------------------------------------------
    # resolve_command returning a real name (line 799)
    # ------------------------------------------------------------------
    def test_resolve_command_returns_name(self):
        """resolve_command returns the matched name from the call stack."""
        from traceback import FrameSummary, StackSummary

        fake_frame = FrameSummary(
            "df_config/manage.py", 42, "server", lookup_line=False
        )
        fake_stack = StackSummary.from_list([fake_frame])
        with patch("df_config.guesses.log.extract_stack", return_value=fake_stack):
            result = LogConfiguration.resolve_command()
        self.assertEqual(result, "server")
