import logging.config
import tempfile
from unittest import TestCase

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
                        "format": "%(asctime)s [test.example.com:9000] %(message)s",
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
                        "format": "%(asctime)s [test.example.com:9000] %(message)s",
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
                        "format": "%(asctime)s [test.example.com:9000] %(message)s",
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
                        "format": "%(asctime)s [test.example.com:9000] %(message)s",
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
                        "format": "%(asctime)s [test.example.com:9000] %(message)s",
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
                    "handlers": ["stdout.warning.colorized", "mail_admins"],
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
                        "format": "%(asctime)s [test.example.com:9000] %(message)s",
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
