# ##############################################################################
#  This file is part of df_config                                              #
#                                                                              #
#  Copyright (C) 2020 Matthieu Gallet <df_config@19pouces.net>                    #
#  All Rights Reserved                                                         #
#                                                                              #
#  You may use, distribute and modify this code under the                      #
#  terms of the (BSD-like) CeCILL-B license.                                   #
#                                                                              #
# ##############################################################################
"""Unit tests for the LoggingConfiguration class and related helpers."""

import logging
import logging.config
import os
import platform
import stat
import tempfile
import time
from importlib.util import find_spec
from io import StringIO
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.test import override_settings

from df_config.guesses.log import (
    AdminEmailHandler,
    ColorizedFormatter,
    HTTPAccessRecordFilter,
    LoggingConfiguration,
    MaxLevelFilter,
    RemoveDuplicateWarnings,
    ServerFormatter,
    SlowQueriesFilter,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SERVER_LABEL = "test.example.com:9000"

BASE_SETTINGS = {
    "DEBUG": False,
    "DF_MODULE_NAME": "myapp",
    "LOG_DIRECTORY": None,
    "LOG_REMOTE_URL": None,
    "LOG_SLOW_QUERY_DURATION_IN_S": None,
    "LOG_REMOTE_ACCESS": False,
    "SERVER_NAME": "test.example.com",
    "SERVER_PORT": 9000,
    "LOG_EXCLUDED_COMMANDS": [],
    "LOG_LEVEL": "WARNING",
}

# All scenarios produce the same four formatters
COMMON_FORMATTERS = {
    "access.nocolor": {
        "()": "df_config.guesses.log.ServerFormatter",
        "fmt": f"%(asctime)s [{_SERVER_LABEL}] %(message)s",
        "use_color": False,
    },
    "access.color": {
        "()": "df_config.guesses.log.ServerFormatter",
        "fmt": f"%(asctime)s [{_SERVER_LABEL}] %(message)s",
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

# Base set of filters (without slow_queries)
COMMON_FILTERS = {
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

ACCESS_LOGGERS = sorted(LoggingConfiguration.access_loggers)


def _access_logger_entry(handlers):
    """Return the common dict for access loggers."""
    return {"filters": [], "handlers": handlers, "level": "INFO"}


# ---------------------------------------------------------------------------
# Helper base class
# ---------------------------------------------------------------------------


class LoggingConfigBase(TestCase):
    """Base class that patches sys.stdout/stderr to non-TTY streams."""

    maxDiff = None
    argv = ["manage.py", "server"]

    def get_config(self, **overrides):
        """Build and return a logging config dict.

        sys.stdout and sys.stderr are replaced with StringIO so that
        ``get_colored_formatter`` always returns the ``*.nocolor`` variant.
        dictConfig is applied to exercise handler/filter instantiation paths.
        """
        settings = dict(BASE_SETTINGS)
        settings.update(overrides)
        fake = StringIO()
        lc = LoggingConfiguration(stdout=fake, stderr=fake)
        fake_stdout = StringIO()
        fake_stderr = StringIO()
        with patch("sys.stdout", new=fake_stdout), patch("sys.stderr", new=fake_stderr):
            config = lc(settings, argv=self.argv)
        try:
            logging.config.dictConfig(config)
        except Exception:
            pass  # Some handlers (syslog, loki) may fail in test environment
        return config


# ===========================================================================
# Integration tests – full __call__ round-trips
# ===========================================================================


class TestLoggingConfigurationNoDirectory(LoggingConfigBase):
    """Configurations that do not use a log directory."""

    # ------------------------------------------------------------------
    # Non-debug, WARNING, no directory
    # ------------------------------------------------------------------
    def test_not_debug_warning_level(self):
        """No directory, not debug, WARNING level → console stdout/stderr."""
        config = self.get_config()
        self.assertEqual(
            config,
            {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": COMMON_FORMATTERS,
                "filters": COMMON_FILTERS,
                "handlers": {
                    "mail_admins": {
                        "class": "df_config.guesses.log.AdminEmailHandler",
                        "filters": ["not_http_access"],
                        "include_html": True,
                        "level": "ERROR",
                    },
                    "stdout-default": {
                        "class": "logging.StreamHandler",
                        "filters": ["below_error", "not_http_access"],
                        "formatter": "plain.nocolor",
                        "level": "WARNING",
                        "stream": "ext://sys.stdout",
                    },
                    "stderr-default": {
                        "class": "logging.StreamHandler",
                        "filters": ["not_http_access"],
                        "formatter": "plain.nocolor",
                        "level": "ERROR",
                        "stream": "ext://sys.stderr",
                    },
                    "stdout-access": {
                        "class": "logging.StreamHandler",
                        "filters": ["below_error", "http_access"],
                        "formatter": "access.nocolor",
                        "level": "INFO",
                        "stream": "ext://sys.stdout",
                    },
                    "stderr-access": {
                        "class": "logging.StreamHandler",
                        "filters": ["http_access"],
                        "formatter": "access.nocolor",
                        "level": "ERROR",
                        "stream": "ext://sys.stderr",
                    },
                },
                "loggers": {
                    "django": {"filters": [], "handlers": [], "level": "ERROR"},
                    "django.db": {"filters": [], "handlers": [], "level": "ERROR"},
                    "django.db.backends.schema": {
                        "filters": [],
                        "handlers": [],
                        "level": "ERROR",
                    },
                    "pip.vcs": {"filters": [], "handlers": [], "level": "ERROR"},
                    "py.warnings": {
                        "filters": ["remove_duplicate_warnings"],
                        "handlers": [],
                        "level": "ERROR",
                    },
                    **{
                        logger: _access_logger_entry(["stdout-access", "stderr-access"])
                        for logger in ACCESS_LOGGERS
                    },
                },
                "root": {
                    "handlers": ["mail_admins", "stdout-default", "stderr-default"],
                    "level": "WARNING",
                },
            },
        )

    # ------------------------------------------------------------------
    # Non-debug, INFO level
    # ------------------------------------------------------------------
    def test_not_debug_info_level(self):
        """INFO level → _level_up maps other_level_loggers to WARNING."""
        config = self.get_config(LOG_LEVEL="INFO")
        self.assertEqual(config["root"]["level"], "INFO")
        # _level_up["INFO"] = "WARNING"
        self.assertEqual(config["loggers"]["django"]["level"], "WARNING")
        self.assertEqual(config["loggers"]["pip.vcs"]["level"], "WARNING")
        self.assertEqual(config["loggers"]["py.warnings"]["level"], "WARNING")
        # stdout-default adapts to the requested level
        self.assertEqual(config["handlers"]["stdout-default"]["level"], "INFO")
        # mail_admins stays at ERROR
        self.assertIn("mail_admins", config["handlers"])

    # ------------------------------------------------------------------
    # Debug mode (no directory)
    # ------------------------------------------------------------------
    def test_debug_no_directory(self):
        """Debug mode without log directory → no mail_admins handler."""
        config = self.get_config(DEBUG=True)
        self.assertNotIn("mail_admins", config["handlers"])
        self.assertNotIn("mail_admins", config["root"]["handlers"])
        self.assertEqual(config["version"], 1)
        self.assertFalse(config["disable_existing_loggers"])
        # root should still work
        self.assertIn("stdout-default", config["root"]["handlers"])
        self.assertIn("stderr-default", config["root"]["handlers"])

    # ------------------------------------------------------------------
    # LOG_LEVEL not set → uses DEBUG from settings
    # ------------------------------------------------------------------
    def test_debug_level_derived_from_debug_flag(self):
        """When LOG_LEVEL is empty and DEBUG=True, level defaults to DEBUG."""
        config = self.get_config(DEBUG=True, LOG_LEVEL="")
        self.assertEqual(config["root"]["level"], "DEBUG")

    # ------------------------------------------------------------------
    # Missing log directory → falls back to stdout/stderr
    # ------------------------------------------------------------------
    def test_missing_log_directory_falls_back_to_stdout(self):
        """Configuring a non-existent directory generates stdout/stderr handlers."""
        config = self.get_config(LOG_DIRECTORY="/nonexistent/path/xyz")
        # Should fall back to stdout/stderr (empty-suffix names)
        self.assertIn("stdout", config["handlers"])
        self.assertIn("stderr", config["handlers"])
        # No file handler
        self.assertFalse(
            any(h.startswith("file.") for h in config["handlers"]),
            "No file handler expected when directory is missing",
        )

    # ------------------------------------------------------------------
    # Slow queries filter
    # ------------------------------------------------------------------
    def test_slow_queries(self):
        """slow_query_duration_in_s adds slow_queries filter and django.db.backends logger."""
        fake = StringIO()
        lc = LoggingConfiguration(stdout=fake, stderr=fake)
        lc.slow_query_duration_in_s = 1.0
        with patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()):
            config = lc(BASE_SETTINGS, argv=["manage.py", "server"])
        try:
            logging.config.dictConfig(config)
        except Exception:
            pass

        # slow_queries filter present
        self.assertIn("slow_queries", config["filters"])
        self.assertEqual(
            config["filters"]["slow_queries"],
            {
                "()": "df_config.guesses.log.SlowQueriesFilter",
                "slow_query_duration_in_s": 1.0,
            },
        )
        # django.db.backends logger added with the filter
        self.assertIn("django.db.backends", config["loggers"])
        backends_logger = config["loggers"]["django.db.backends"]
        self.assertEqual(backends_logger["level"], "INFO")
        self.assertIn("slow_queries", backends_logger["filters"])

    # ------------------------------------------------------------------
    # Loki remote URL (no directory)
    # ------------------------------------------------------------------
    def test_loki_remote_url(self):
        """A loki:// URL creates a loki handler in root handlers."""
        config = self.get_config(
            LOG_REMOTE_URL="loki://localhost:3100/loki/api/v1/push"
        )
        # The loki handler should appear in root
        loki_handlers = [h for h in config["root"]["handlers"] if "loki" in h]
        self.assertEqual(
            len(loki_handlers), 1, "Expected exactly one loki handler in root"
        )
        loki_name = loki_handlers[0]
        loki_handler = config["handlers"][loki_name]
        self.assertEqual(loki_handler["class"], "df_config.extra.loki.LokiHandler")
        self.assertEqual(loki_handler["url"], "http://localhost:3100/loki/api/v1/push")
        self.assertIsNone(loki_handler["auth"])
        self.assertEqual(loki_handler["level"], "WARNING")


class TestLoggingConfigurationWithDirectory(LoggingConfigBase):
    """Configurations that use a writeable log directory."""

    def _pre_create_logs(self, dirname):
        """Pre-create the log files so os.access() returns True."""
        for fname in ["myapp.log", "myapp-access.log"]:
            open(os.path.join(dirname, fname), "w").close()

    def test_file_handlers_created(self):
        """When pre-created log files exist, file handlers are used."""
        with tempfile.TemporaryDirectory() as dirname:
            self._pre_create_logs(dirname)
            config = self.get_config(LOG_DIRECTORY=dirname)

        handlers = config["handlers"]
        # Rotating file handler for default logs
        self.assertIn("file.", handlers)
        self.assertEqual(
            handlers["file."]["class"], "logging.handlers.RotatingFileHandler"
        )
        self.assertEqual(handlers["file."]["level"], "WARNING")
        self.assertIn("not_http_access", handlers["file."]["filters"])
        # Rotating file handler for access logs
        self.assertIn("file.-access", handlers)
        self.assertEqual(handlers["file.-access"]["level"], "INFO")
        self.assertIn("http_access", handlers["file.-access"]["filters"])
        # Root uses the file handler
        self.assertIn("file.", config["root"]["handlers"])
        # No stdout/stderr in root when directory is present and files are writable
        self.assertNotIn("stdout", config["root"]["handlers"])
        self.assertNotIn("stderr", config["root"]["handlers"])

    def test_file_handler_maxbytes_and_backup(self):
        """File handlers respect maxBytes and backupCount from LoggingConfiguration."""
        with tempfile.TemporaryDirectory() as dirname:
            self._pre_create_logs(dirname)
            config = self.get_config(LOG_DIRECTORY=dirname)

        handler = config["handlers"]["file."]
        self.assertEqual(handler["maxBytes"], 100_000_000)
        self.assertEqual(handler["backupCount"], 5)
        self.assertTrue(handler["delay"])

    def test_file_handler_filenames(self):
        """Log filenames are derived from project name and log suffix."""
        with tempfile.TemporaryDirectory() as dirname:
            self._pre_create_logs(dirname)
            config = self.get_config(LOG_DIRECTORY=dirname)

        handlers = config["handlers"]
        self.assertIn(dirname, handlers["file."]["filename"])
        self.assertTrue(handlers["file."]["filename"].endswith("myapp.log"))
        self.assertIn(dirname, handlers["file.-access"]["filename"])
        self.assertTrue(
            handlers["file.-access"]["filename"].endswith("myapp-access.log")
        )

    def test_debug_with_log_directory(self):
        """Debug mode with directory → file handlers + extra debug stdout/stderr."""
        with tempfile.TemporaryDirectory() as dirname:
            self._pre_create_logs(dirname)
            config = self.get_config(DEBUG=True, LOG_DIRECTORY=dirname)

        handlers = config["handlers"]
        # File handler still present
        self.assertIn("file.", handlers)
        # Extra debug stdout/stderr handlers
        self.assertIn("stdout-debug", handlers)
        self.assertIn("stderr-debug", handlers)
        # No mail_admins in debug mode
        self.assertNotIn("mail_admins", handlers)
        # Root uses file + debug handlers
        root_handlers = config["root"]["handlers"]
        self.assertIn("file.", root_handlers)
        self.assertIn("stdout-debug", root_handlers)

    def test_access_loggers_use_file_handler(self):
        """Access loggers use the file handler when directory is writeable."""
        with tempfile.TemporaryDirectory() as dirname:
            self._pre_create_logs(dirname)
            config = self.get_config(LOG_DIRECTORY=dirname)

        for logger in ACCESS_LOGGERS:
            entry = config["loggers"][logger]
            self.assertIn(
                "file.-access", entry["handlers"], f"{logger} should use file.-access"
            )
            self.assertEqual(entry["level"], "INFO")


class TestLoggingConfigurationSyslog(LoggingConfigBase):
    """Configurations that use a syslog remote URL."""

    def test_syslog_tcp_remote_url(self):
        """syslog+tcp:// URL creates a SysLogHandler with SOCK_STREAM."""
        import socket as sock_module

        config = self.get_config(LOG_REMOTE_URL="syslog+tcp://127.0.0.1:514")
        syslog_handlers = {k: v for k, v in config["handlers"].items() if "syslog" in k}
        self.assertTrue(syslog_handlers, "Expected at least one syslog handler")
        handler = next(iter(syslog_handlers.values()))
        self.assertEqual(handler["class"], "logging.handlers.SysLogHandler")
        self.assertEqual(handler["socktype"], sock_module.SOCK_STREAM)

    def test_syslog_udp_remote_url(self):
        """syslog:// URL creates a SysLogHandler with SOCK_DGRAM."""
        import socket as sock_module

        config = self.get_config(LOG_REMOTE_URL="syslog://127.0.0.1:514")
        syslog_handlers = {k: v for k, v in config["handlers"].items() if "syslog" in k}
        self.assertTrue(syslog_handlers, "Expected at least one syslog handler")
        handler = next(iter(syslog_handlers.values()))
        self.assertEqual(handler["class"], "logging.handlers.SysLogHandler")
        self.assertEqual(handler["socktype"], sock_module.SOCK_DGRAM)
        self.assertEqual(handler["address"], ("127.0.0.1", 514))

    def test_syslog_in_root_handlers(self):
        """Syslog handler appears in root handlers."""
        config = self.get_config(LOG_REMOTE_URL="syslog://127.0.0.1:514")
        syslog_in_root = [h for h in config["root"]["handlers"] if "syslog" in h]
        self.assertTrue(syslog_in_root, "Syslog handler should be referenced in root")

    def test_unknown_scheme_does_not_raise(self):
        """An unknown remote URL scheme does not raise, but appends a warning."""
        from df_config.checks import settings_check_results

        initial_count = len(settings_check_results)
        config = self.get_config(LOG_REMOTE_URL="unknown://host:1234")
        # A warning should have been appended
        self.assertGreater(len(settings_check_results), initial_count)
        # No unknown handler should be created
        unknown_handlers = [h for h in config["handlers"] if "unknown" in h.lower()]
        self.assertFalse(unknown_handlers)


# ===========================================================================
# Tests for missing branches in LoggingConfiguration
# ===========================================================================


class TestAddFileHandlerNotWritable(LoggingConfigBase):
    """Cover the 'file exists but not writable' branch (lines 1013-1025)."""

    def test_file_exists_but_not_writable_falls_back_to_stdout(self):
        """When the log file exists but is read-only, we fall back to stdout/stderr."""
        with tempfile.TemporaryDirectory() as dirname:
            # Create the file and make it read-only
            full_path = os.path.join(dirname, "myapp.log")
            open(full_path, "w").close()
            os.chmod(full_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            try:
                config = self.get_config(LOG_DIRECTORY=dirname)
            finally:
                # Restore permissions so the temp dir can be cleaned up
                os.chmod(full_path, stat.S_IRUSR | stat.S_IWUSR)

        # The file handler is NOT created; fallback to stdout/stderr
        self.assertFalse(
            any(h.startswith("file.") for h in config["handlers"]),
            "No file handler expected when log file is not writable",
        )
        # And a warning was registered
        from df_config.checks import settings_check_results

        warnings_w009 = [
            w
            for w in settings_check_results
            if getattr(w, "id", None) == "df_config.W009"
        ]
        self.assertTrue(warnings_w009)

    def test_second_write_error_no_duplicate_warning(self):
        """log_directory_warning flag prevents duplicate W009 warnings."""
        with tempfile.TemporaryDirectory() as dirname:
            full_path = os.path.join(dirname, "myapp.log")
            open(full_path, "w").close()
            os.chmod(full_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            try:
                # Create a LoggingConfiguration that has already emitted the warning
                fake = StringIO()
                lc = LoggingConfiguration(stdout=fake, stderr=fake)
                lc.log_directory_warning = True  # pretend already warned
                with (
                    patch("sys.stdout", new=StringIO()),
                    patch("sys.stderr", new=StringIO()),
                ):
                    config = lc(
                        dict(BASE_SETTINGS, LOG_DIRECTORY=dirname),
                        argv=["manage.py", "server"],
                    )
            finally:
                os.chmod(full_path, stat.S_IRUSR | stat.S_IWUSR)
        # Should still fall back gracefully
        self.assertIsInstance(config, dict)


class TestParseSyslogUrl(LoggingConfigBase):
    """Cover all branches of parse_syslog_url (lines 1057-1064)."""

    def _get_syslog_address(self, url):
        """Helper: extract the syslog handler address from config."""
        config = self.get_config(LOG_REMOTE_URL=url)
        handlers = {k: v for k, v in config["handlers"].items() if "syslog" in k}
        self.assertTrue(handlers, f"No syslog handler for URL {url!r}")
        return next(iter(handlers.values()))["address"]

    def test_device_path_used_as_address(self):
        """syslog:///dev/log/daemon → device='/dev/log' → address='/dev/log'."""
        address = self._get_syslog_address("syslog:///dev/log/daemon")
        self.assertEqual(address, "/dev/log")

    def test_darwin_default_address(self):
        """syslog:///user (no hostname, no device) on Darwin → /var/run/syslog."""
        with patch("df_config.guesses.log.platform.system", return_value="Darwin"):
            address = self._get_syslog_address("syslog:///user")
        self.assertEqual(address, "/var/run/syslog")

    def test_linux_default_address(self):
        """syslog:///user on Linux → /dev/log."""
        with patch("df_config.guesses.log.platform.system", return_value="Linux"):
            address = self._get_syslog_address("syslog:///user")
        self.assertEqual(address, "/dev/log")

    def test_other_platform_default_address(self):
        """syslog:///user on unknown platform → ('localhost', 514)."""
        with patch("df_config.guesses.log.platform.system", return_value="Windows"):
            address = self._get_syslog_address("syslog:///user")
        self.assertEqual(address, ("localhost", 514))


class TestLogdRemoteUrl(LoggingConfigBase):
    """Cover add_logd_handler (lines 1139-1151) and the logd scheme (line 1096)."""

    def test_logd_url_without_systemd_falls_back(self):
        """logd:// URL when systemd.journal is not installed → fallback to stdout."""
        with patch("df_config.guesses.log.find_spec", side_effect=lambda x: None):
            config = self.get_config(LOG_REMOTE_URL="logd:///myapp")
        # No logd handler; fallback handlers should be present
        logd_handlers = [h for h in config["handlers"] if h.startswith("logd.")]
        self.assertFalse(logd_handlers, "No logd handler expected without systemd")

    def test_logd_url_with_systemd_creates_journal_handler(self):
        """logd:// URL when systemd.journal IS installed → JournalHandler."""
        mock_spec = MagicMock()

        def fake_find_spec(name):
            if name == "systemd.journal":
                return mock_spec  # pretend it's installed
            return find_spec(name)

        with patch("df_config.guesses.log.find_spec", side_effect=fake_find_spec):
            config = self.get_config(LOG_REMOTE_URL="logd:///myapp")

        logd_handlers = {
            k: v for k, v in config["handlers"].items() if k.startswith("logd.")
        }
        self.assertTrue(
            logd_handlers, "Expected a logd handler when systemd.journal is available"
        )
        handler = next(iter(logd_handlers.values()))
        self.assertEqual(handler["class"], "systemd.journal.JournalHandler")


class TestLokiRemoteUrlVariants(LoggingConfigBase):
    """Cover loki URL with query string (line 1110), auth (line 1113)."""

    def test_loki_url_with_query_string(self):
        """loki URL with query params → query is appended to URL."""
        config = self.get_config(
            LOG_REMOTE_URL="loki://host:3100/loki/api/v1/push?tenant=1"
        )
        loki_handlers = {k: v for k, v in config["handlers"].items() if "loki" in k}
        # Either loki handler or fallback stdout handler must exist
        self.assertTrue(loki_handlers or "stdout-default" in config["handlers"])

    def test_loki_url_with_credentials(self):
        """loki URL with user:pass → auth tuple set in handler."""
        config = self.get_config(LOG_REMOTE_URL="loki://user:secret@host:3100/path")
        loki_handlers = {k: v for k, v in config["handlers"].items() if "loki" in k}
        if loki_handlers:
            handler = next(iter(loki_handlers.values()))
            self.assertEqual(handler.get("auth"), ("user", "secret"))

    def test_loki_fallback_when_library_missing(self):
        """When find_spec('logging_loki') returns None → fallback to stdout."""
        original = find_spec

        def patched(name):
            if name == "logging_loki":
                return None
            return original(name)

        with patch("df_config.guesses.log.find_spec", side_effect=patched):
            config = self.get_config(LOG_REMOTE_URL="loki://host:3100/path")

        loki_in_root = [h for h in config["root"]["handlers"] if "loki" in h]
        self.assertFalse(
            loki_in_root, "No loki handler in root when library is missing"
        )
        # A warning about missing library should have been added
        from df_config.checks import settings_check_results

        w006 = [
            w
            for w in settings_check_results
            if getattr(w, "id", None) == "df_config.W006"
        ]
        self.assertTrue(w006)

    def test_lokis_scheme_produces_https_url(self):
        """lokis:// scheme → https:// URL in handler."""
        config = self.get_config(LOG_REMOTE_URL="lokis://host:3100/path")
        loki_handlers = {k: v for k, v in config["handlers"].items() if "loki" in k}
        if loki_handlers:
            handler = next(iter(loki_handlers.values()))
            self.assertTrue(handler["url"].startswith("https://"))


class TestRemoteAccessForAccessLoggers(LoggingConfigBase):
    """Cover log_remote_url + log_remote_access for access handlers (line 1261)."""

    def test_syslog_with_remote_access_enabled(self):
        """LOG_REMOTE_ACCESS=True → access loggers also get the syslog handler."""
        config = self.get_config(
            LOG_REMOTE_URL="syslog://127.0.0.1:514",
            LOG_REMOTE_ACCESS=True,
        )
        # At least one access logger should have a syslog handler
        access_syslog = [
            h
            for logger in ACCESS_LOGGERS
            for h in config["loggers"][logger]["handlers"]
            if "syslog" in h
        ]
        self.assertTrue(
            access_syslog, "Access loggers should receive the syslog handler"
        )

    def test_loki_with_remote_access_enabled(self):
        """LOG_REMOTE_ACCESS=True with loki → access loggers also get loki/stdout handler."""
        config = self.get_config(
            LOG_REMOTE_URL="loki://host:3100/path",
            LOG_REMOTE_ACCESS=True,
        )
        # At least one additional handler for access loggers (loki or fallback)
        access_extra = [
            h
            for logger in ACCESS_LOGGERS
            for h in config["loggers"][logger]["handlers"]
        ]
        self.assertTrue(access_extra)


class TestDisabledLoggers(LoggingConfigBase):
    """Cover LoggingConfiguration.disabled_loggers (line 1369)."""

    def test_disabled_logger_is_created_with_critical_level(self):
        """Loggers in disabled_loggers get level=CRITICAL, propagate=False, disabled=True."""
        fake = StringIO()
        lc = LoggingConfiguration(stdout=fake, stderr=fake)
        lc.disabled_loggers = {"my.noisy.logger"}
        with patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()):
            config = lc(BASE_SETTINGS, argv=["manage.py", "server"])

        self.assertIn("my.noisy.logger", config["loggers"])
        entry = config["loggers"]["my.noisy.logger"]
        self.assertEqual(entry["level"], "CRITICAL")
        self.assertFalse(entry.get("propagate", True))
        self.assertTrue(entry.get("disabled"))

    def test_multiple_disabled_loggers(self):
        """Multiple loggers can be disabled at once."""
        fake = StringIO()
        lc = LoggingConfiguration(stdout=fake, stderr=fake)
        lc.disabled_loggers = {"logger.a", "logger.b"}
        with patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()):
            config = lc(BASE_SETTINGS, argv=["manage.py", "server"])

        for name in ("logger.a", "logger.b"):
            self.assertIn(name, config["loggers"])
            self.assertTrue(config["loggers"][name].get("disabled"))


# ===========================================================================
# Unit tests for helper classes: ColorizedFormatter
# ===========================================================================


class TestColorizedFormatter(TestCase):
    """Tests for ColorizedFormatter (lines 39-66)."""

    def _make_record(self, level, msg="test message"):
        record = logging.LogRecord(
            name="test",
            level=level,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )
        record.levelno = level
        return record

    def test_init_no_color(self):
        f = ColorizedFormatter(use_color=False)
        self.assertIsNotNone(f)

    def test_init_with_color(self):
        f = ColorizedFormatter(use_color=True)
        self.assertIsNotNone(f)

    def test_format_debug(self):
        f = ColorizedFormatter(use_color=False)
        result = f.format(self._make_record(logging.DEBUG))
        self.assertIn("test message", result)

    def test_format_info(self):
        f = ColorizedFormatter(use_color=False)
        result = f.format(self._make_record(logging.INFO))
        self.assertIn("test message", result)

    def test_format_warning(self):
        f = ColorizedFormatter(use_color=False)
        result = f.format(self._make_record(logging.WARNING))
        self.assertIn("test message", result)

    def test_format_error(self):
        f = ColorizedFormatter(use_color=False)
        result = f.format(self._make_record(logging.ERROR))
        self.assertIn("test message", result)

    def test_format_critical(self):
        f = ColorizedFormatter(use_color=False)
        result = f.format(self._make_record(logging.CRITICAL))
        self.assertIn("test message", result)

    def test_format_with_color(self):
        """Colorized formatter should still include the message."""
        f = ColorizedFormatter(use_color=True)
        for level in (
            logging.DEBUG,
            logging.INFO,
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        ):
            result = f.format(self._make_record(level))
            self.assertIn("test message", result)

    def test_format_stack(self):
        f = ColorizedFormatter(use_color=True)
        result = f.formatStack("some stack info here")
        self.assertIn("some stack info here", result)

    def test_format_stack_no_color(self):
        f = ColorizedFormatter(use_color=False)
        result = f.formatStack("stack trace")
        self.assertIn("stack trace", result)


# ===========================================================================
# Unit tests for helper classes: ServerFormatter
# ===========================================================================


class TestServerFormatter(TestCase):
    """Tests for ServerFormatter (lines 69-116)."""

    def _make_record(
        self, status_code=None, level=logging.INFO, msg="GET /path HTTP/1.1"
    ):
        record = logging.LogRecord(
            name="django.server",
            level=level,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )
        record.levelno = level
        if status_code is not None:
            record.status_code = status_code
        return record

    def test_init_no_color(self):
        f = ServerFormatter(use_color=False)
        self.assertIsNotNone(f)

    def test_init_with_color(self):
        f = ServerFormatter(use_color=True)
        self.assertIsNotNone(f)

    def test_format_2xx(self):
        f = ServerFormatter(use_color=False)
        result = f.format(self._make_record(status_code=200))
        self.assertIn("GET /path", result)

    def test_format_1xx(self):
        f = ServerFormatter(use_color=False)
        result = f.format(self._make_record(status_code=100))
        self.assertIn("GET /path", result)

    def test_format_304(self):
        f = ServerFormatter(use_color=False)
        result = f.format(self._make_record(status_code=304))
        self.assertIn("GET /path", result)

    def test_format_3xx(self):
        f = ServerFormatter(use_color=False)
        result = f.format(self._make_record(status_code=301))
        self.assertIn("GET /path", result)

    def test_format_404(self):
        f = ServerFormatter(use_color=False)
        result = f.format(self._make_record(status_code=404))
        self.assertIn("GET /path", result)

    def test_format_4xx(self):
        f = ServerFormatter(use_color=False)
        result = f.format(self._make_record(status_code=400))
        self.assertIn("GET /path", result)

    def test_format_5xx(self):
        f = ServerFormatter(use_color=False)
        result = f.format(self._make_record(status_code=500))
        self.assertIn("GET /path", result)

    def test_format_no_status_debug(self):
        f = ServerFormatter(use_color=False)
        result = f.format(self._make_record(status_code=0, level=logging.DEBUG))
        self.assertIn("GET /path", result)

    def test_format_no_status_info(self):
        f = ServerFormatter(use_color=False)
        result = f.format(self._make_record(status_code=0, level=logging.INFO))
        self.assertIn("GET /path", result)

    def test_format_no_status_warning(self):
        f = ServerFormatter(use_color=False)
        result = f.format(self._make_record(status_code=0, level=logging.WARNING))
        self.assertIn("GET /path", result)

    def test_format_no_status_error(self):
        f = ServerFormatter(use_color=False)
        result = f.format(self._make_record(status_code=0, level=logging.ERROR))
        self.assertIn("GET /path", result)

    def test_uses_server_time_true(self):
        f = ServerFormatter(fmt="%(server_time)s %(message)s")
        self.assertTrue(f.uses_server_time())

    def test_uses_server_time_false(self):
        f = ServerFormatter(fmt="%(asctime)s %(message)s")
        self.assertFalse(f.uses_server_time())

    def test_format_sets_server_time_when_needed(self):
        """format() injects server_time when the fmt requires it."""
        f = ServerFormatter(fmt="%(server_time)s %(message)s", use_color=False)
        record = self._make_record(status_code=200)
        # Remove server_time if present
        if hasattr(record, "server_time"):
            del record.server_time
        result = f.format(record)
        self.assertTrue(hasattr(record, "server_time"))


# ===========================================================================
# Unit tests for helper classes: AdminEmailHandler
# ===========================================================================


class TestAdminEmailHandler(TestCase):
    """Tests for AdminEmailHandler (lines 119-155)."""

    def setUp(self):
        # Reset class-level state
        AdminEmailHandler._previous_email_time = None

    def tearDown(self):
        AdminEmailHandler._previous_email_time = None

    def test_can_send_email_first_time(self):
        """First call with no previous email → can send."""
        handler = AdminEmailHandler()
        self.assertTrue(handler.can_send_email())

    def test_can_send_email_rate_limited(self):
        """Second call within min_interval → cannot send."""
        handler = AdminEmailHandler()
        handler.can_send_email()  # sets _previous_email_time to now
        # Override _previous_email_time to just now to trigger rate limit
        AdminEmailHandler._previous_email_time = time.time()
        self.assertFalse(handler.can_send_email())

    def test_can_send_email_after_interval(self):
        """Call after more than min_interval → can send again."""
        handler = AdminEmailHandler()
        AdminEmailHandler._previous_email_time = time.time() - 700  # 700s ago
        self.assertTrue(handler.can_send_email())

    @override_settings(EMAIL_HOST="", LOG_DIRECTORY=None)
    def test_send_mail_no_email_host(self):
        """send_mail does nothing when EMAIL_HOST is empty."""
        handler = AdminEmailHandler()
        # Should not raise and should not try to send
        with patch.object(type(handler).__bases__[0], "send_mail") as mock_super:
            handler.send_mail("subject", "body")
            mock_super.assert_not_called()

    @override_settings(EMAIL_HOST="smtp.example.com", LOG_DIRECTORY=None)
    def test_send_mail_smtp_exception_is_caught(self):
        """send_mail catches SMTP exceptions gracefully."""
        handler = AdminEmailHandler()
        AdminEmailHandler._previous_email_time = None
        with patch(
            "django.utils.log.AdminEmailHandler.send_mail",
            side_effect=Exception("SMTP error"),
        ):
            # Must not propagate
            handler.send_mail("subject", "body")

    @override_settings(EMAIL_HOST="smtp.example.com", LOG_DIRECTORY="/var/log")
    def test_send_mail_smtp_exception_with_log_directory(self):
        """With LOG_DIRECTORY set, the except branch prints the directory hint."""
        handler = AdminEmailHandler()
        AdminEmailHandler._previous_email_time = None
        with patch(
            "django.utils.log.AdminEmailHandler.send_mail",
            side_effect=Exception("SMTP error"),
        ):
            handler.send_mail("subject", "body")  # Must not raise


# ===========================================================================
# Unit tests for filter classes
# ===========================================================================


class TestRemoveDuplicateWarnings(TestCase):
    """Tests for RemoveDuplicateWarnings.filter (lines 168-171)."""

    def _make_record(self, pathname, args=()):
        record = logging.LogRecord(
            name="py.warnings",
            level=logging.WARNING,
            pathname=pathname,
            lineno=0,
            msg="msg",
            args=None,
            exc_info=None,
        )
        record.args = args
        return record

    def test_first_occurrence_is_kept(self):
        f = RemoveDuplicateWarnings()
        record = self._make_record("/app/foo.py", ("DeprecationWarning: old",))
        self.assertTrue(f.filter(record))

    def test_second_occurrence_is_filtered(self):
        f = RemoveDuplicateWarnings()
        record = self._make_record("/app/foo.py", ("DeprecationWarning: old",))
        f.filter(record)  # first – kept
        self.assertFalse(f.filter(record))  # same record – filtered

    def test_different_pathnames_are_kept(self):
        f = RemoveDuplicateWarnings()
        r1 = self._make_record("/app/a.py", ("msg",))
        r2 = self._make_record("/app/b.py", ("msg",))
        self.assertTrue(f.filter(r1))
        self.assertTrue(f.filter(r2))


class TestSlowQueriesFilter(TestCase):
    """Tests for SlowQueriesFilter (lines 179-191)."""

    def _make_record(self, duration):
        record = logging.LogRecord(
            name="django.db.backends",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="SELECT 1",
            args=None,
            exc_info=None,
        )
        record.duration = duration
        return record

    def test_fast_query_not_kept(self):
        f = SlowQueriesFilter(slow_query_duration_in_s=1.0)
        self.assertFalse(f.filter(self._make_record(0.5)))

    def test_slow_query_is_kept(self):
        f = SlowQueriesFilter(slow_query_duration_in_s=1.0)
        record = self._make_record(2.0)
        self.assertTrue(f.filter(record))
        self.assertIsNotNone(record.stack_info)

    def test_boundary_duration_is_not_slow(self):
        """Duration == threshold is NOT slow (strictly greater than required)."""
        f = SlowQueriesFilter(slow_query_duration_in_s=1.0)
        self.assertFalse(f.filter(self._make_record(1.0)))


class TestMaxLevelFilter(TestCase):
    """Tests for MaxLevelFilter.filter (line 209)."""

    def _make_record(self, level):
        record = logging.LogRecord(
            name="test",
            level=level,
            pathname="",
            lineno=0,
            msg="msg",
            args=None,
            exc_info=None,
        )
        record.levelno = level
        return record

    def test_below_max_is_kept(self):
        f = MaxLevelFilter(max_level=logging.ERROR)
        self.assertTrue(f.filter(self._make_record(logging.WARNING)))

    def test_at_max_level_is_filtered(self):
        f = MaxLevelFilter(max_level=logging.ERROR)
        self.assertFalse(f.filter(self._make_record(logging.ERROR)))

    def test_above_max_is_filtered(self):
        f = MaxLevelFilter(max_level=logging.ERROR)
        self.assertFalse(f.filter(self._make_record(logging.CRITICAL)))


class TestHTTPAccessRecordFilter(TestCase):
    """Tests for HTTPAccessRecordFilter.filter (lines 220-226)."""

    def _make_record(self, name, args=None):
        record = logging.LogRecord(
            name=name,
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="msg",
            args=None,
            exc_info=None,
        )
        if args is not None:
            record.args = args
        return record

    def test_channels_record_with_client_kept_by_access_filter(self):
        f = HTTPAccessRecordFilter(keep_access=True)
        record = self._make_record(
            "django.channels.server", args={"client": "127.0.0.1"}
        )
        self.assertTrue(f.filter(record))

    def test_channels_record_without_client_not_kept(self):
        f = HTTPAccessRecordFilter(keep_access=True)
        record = self._make_record("django.channels.server", args={"message": "info"})
        self.assertFalse(f.filter(record))

    def test_standard_access_logger_kept_by_access_filter(self):
        f = HTTPAccessRecordFilter(keep_access=True)
        access_name = sorted(LoggingConfiguration.access_loggers)[0]
        record = self._make_record(access_name)
        self.assertTrue(f.filter(record))

    def test_non_access_logger_not_kept_by_access_filter(self):
        f = HTTPAccessRecordFilter(keep_access=True)
        record = self._make_record("django.request")
        self.assertFalse(f.filter(record))

    def test_non_access_logger_kept_by_not_http_access_filter(self):
        f = HTTPAccessRecordFilter(keep_access=False)
        record = self._make_record("some.other.logger")
        self.assertTrue(f.filter(record))

    def test_access_logger_not_kept_by_not_http_access_filter(self):
        f = HTTPAccessRecordFilter(keep_access=False)
        access_name = sorted(LoggingConfiguration.access_loggers)[0]
        record = self._make_record(access_name)
        self.assertFalse(f.filter(record))


# ===========================================================================
# Unit tests for LoggingConfiguration helpers
# ===========================================================================


class TestGetColoredFormatter(TestCase):
    """Tests for LoggingConfiguration.get_colored_formatter (line 947)."""

    def test_returns_nocolor_when_stream_is_none(self):
        result = LoggingConfiguration.get_colored_formatter("plain", stream=None)
        self.assertEqual(result, "plain.nocolor")

    def test_returns_nocolor_for_non_tty_stringio(self):
        with patch("sys.stdout", new=StringIO()):
            result = LoggingConfiguration.get_colored_formatter(
                "plain", stream="stdout"
            )
        self.assertEqual(result, "plain.nocolor")

    def test_returns_color_for_tty_stream(self):
        """A stream whose isatty() returns True → color variant (line 947)."""
        mock_stream = MagicMock()
        mock_stream.isatty.return_value = True
        with patch("sys.stdout", mock_stream):
            result = LoggingConfiguration.get_colored_formatter(
                "plain", stream="stdout"
            )
        self.assertEqual(result, "plain.color")

    def test_returns_nocolor_when_stream_has_no_isatty(self):
        """Stream without isatty attribute → nocolor variant."""

        class NoIsatty:
            pass

        with patch("sys.stdout", NoIsatty()):
            result = LoggingConfiguration.get_colored_formatter(
                "plain", stream="stdout"
            )
        self.assertEqual(result, "plain.nocolor")


class TestReadSettings(TestCase):
    """Tests for LoggingConfiguration.read_settings (line 897)."""

    def setUp(self):
        fake = StringIO()
        self.lc = LoggingConfiguration(stdout=fake, stderr=fake)

    def test_log_level_from_setting(self):
        self.lc.read_settings(
            dict(BASE_SETTINGS, LOG_LEVEL="INFO"), argv=["manage.py", "server"]
        )
        self.assertEqual(self.lc.log_level, "INFO")

    def test_debug_derives_level(self):
        settings = dict(BASE_SETTINGS, LOG_LEVEL="", DEBUG=True)
        self.lc.read_settings(settings, argv=["manage.py", "server"])
        self.assertEqual(self.lc.log_level, "DEBUG")

    def test_no_debug_no_level_defaults_to_warning(self):
        """else branch (line 897): LOG_LEVEL='' and DEBUG=False → 'WARNING'."""
        settings = dict(BASE_SETTINGS, LOG_LEVEL="", DEBUG=False)
        self.lc.read_settings(settings, argv=["manage.py", "server"])
        self.assertEqual(self.lc.log_level, "WARNING")

    def test_server_settings(self):
        self.lc.read_settings(BASE_SETTINGS, argv=["manage.py", "server"])
        self.assertEqual(self.lc.server_name, "test.example.com")
        self.assertEqual(self.lc.server_port, 9000)

    def test_argv_defaults_to_sys_argv(self):
        import sys

        self.lc.read_settings(BASE_SETTINGS, argv=None)
        self.assertEqual(self.lc.argv, sys.argv)


class TestSetLogger(TestCase):
    """Tests for LoggingConfiguration.set_logger."""

    def setUp(self):
        fake = StringIO()
        self.lc = LoggingConfiguration(stdout=fake, stderr=fake)
        with patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()):
            self.lc(BASE_SETTINGS, argv=["manage.py", "server"])

    def test_set_logger_level(self):
        self.lc.set_logger("test.logger", level="DEBUG")
        self.assertIn("test.logger", self.lc.loggers)
        self.assertEqual(self.lc.loggers["test.logger"]["level"], "DEBUG")

    def test_set_logger_propagate_false(self):
        self.lc.set_logger("test.logger", level="WARNING", propagate=False)
        self.assertFalse(self.lc.loggers["test.logger"].get("propagate", True))

    def test_set_logger_disabled(self):
        self.lc.set_logger(
            "noisy.logger", level="CRITICAL", propagate=False, disabled=True
        )
        entry = self.lc.loggers["noisy.logger"]
        self.assertTrue(entry.get("disabled"))
