"""Unit tests for df_config/management/commands/server.py."""

import io
import sys
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.core.management.base import OutputWrapper
from django.test import override_settings


class TestServerCommand(TestCase):
    def _make_cmd(self):
        from df_config.management.commands.server import Command

        cmd = Command()
        cmd.stdout = OutputWrapper(io.StringIO())
        cmd.stderr = OutputWrapper(io.StringIO())
        return cmd

    @override_settings(LISTEN_ADDRESS="0.0.0.0:8001")
    def test_listen_port(self):
        cmd = self._make_cmd()
        self.assertEqual(8001, cmd.listen_port)

    @override_settings(LISTEN_ADDRESS="0.0.0.0:8001")
    def test_listen_address(self):
        cmd = self._make_cmd()
        self.assertEqual("0.0.0.0", cmd.listen_address)

    @override_settings(WSGI_APPLICATION="myapp.wsgi.application")
    def test_get_wsgi_application(self):
        from df_config.management.commands.server import Command

        self.assertEqual("myapp.wsgi:application", Command.get_wsgi_application())

    @override_settings(ASGI_APPLICATION="myapp.asgi.application")
    def test_get_asgi_application(self):
        from df_config.management.commands.server import Command

        self.assertEqual("myapp.asgi:application", Command.get_asgi_application())

    def test_handle_no_op(self):
        cmd = self._make_cmd()
        cmd.handle()  # should not raise

    @override_settings(DF_SERVER="gunicorn")
    def test_run_from_argv_gunicorn(self):
        cmd = self._make_cmd()
        cmd.run_gunicorn = MagicMock()
        cmd.run_from_argv(["manage.py", "server"])
        cmd.run_gunicorn.assert_called_once()

    @override_settings(DF_SERVER="daphne")
    def test_run_from_argv_daphne(self):
        cmd = self._make_cmd()
        cmd.run_daphne = MagicMock()
        cmd.run_from_argv(["manage.py", "server"])
        cmd.run_daphne.assert_called_once()

    @override_settings(DF_SERVER="uvicorn")
    def test_run_from_argv_uvicorn(self):
        cmd = self._make_cmd()
        cmd.run_daphne = MagicMock()
        cmd.run_from_argv(["manage.py", "server"])
        cmd.run_daphne.assert_called_once()

    @override_settings(DF_SERVER="unknown_server")
    def test_run_from_argv_unknown(self):
        stderr_buf = io.StringIO()
        cmd = self._make_cmd()
        cmd.stderr = OutputWrapper(stderr_buf)
        cmd.run_from_argv(["manage.py", "server"])
        self.assertIn("unknown value", stderr_buf.getvalue())

    @override_settings(
        LISTEN_ADDRESS="0.0.0.0:8000", ASGI_APPLICATION="myapp.asgi.application"
    )
    def test_run_daphne_import_error(self):
        stderr_buf = io.StringIO()
        cmd = self._make_cmd()
        cmd.stderr = OutputWrapper(stderr_buf)
        with patch.dict(sys.modules, {"daphne": None, "daphne.cli": None}):
            cmd.run_daphne()
        self.assertIn("daphne", stderr_buf.getvalue())

    @override_settings(
        LISTEN_ADDRESS="0.0.0.0:8000", ASGI_APPLICATION="myapp.asgi.application"
    )
    def test_run_daphne_success(self):
        class FakeAction:
            def __init__(self, dest):
                self.dest = dest
                self.default = None
                self.required = True

        class FakeParser:
            _actions = [
                FakeAction("port"),
                FakeAction("host"),
                FakeAction("application"),
                FakeAction("other"),
            ]

        class FakeCLI:
            def __init__(self):
                self.parser = FakeParser()

            def run(self, args):
                return None

        mock_daphne_cli = MagicMock()
        mock_daphne_cli.CommandLineInterface = FakeCLI
        with patch.dict(
            sys.modules, {"daphne": MagicMock(), "daphne.cli": mock_daphne_cli}
        ):
            cmd = self._make_cmd()
            result = cmd.run_daphne()

    @override_settings(
        LISTEN_ADDRESS="0.0.0.0:8000",
        WSGI_APPLICATION="myapp.wsgi.application",
        USE_WEBSOCKETS=False,
    )
    def test_run_gunicorn_import_error(self):
        stderr_buf = io.StringIO()
        cmd = self._make_cmd()
        cmd.stderr = OutputWrapper(stderr_buf)
        orig_argv = sys.argv[:]
        sys.argv = ["manage.py", "server"]
        try:
            with patch.dict(sys.modules, {"gunicorn": None, "gunicorn.config": None}):
                cmd.run_gunicorn()
        finally:
            sys.argv = orig_argv
        self.assertIn("gunicorn", stderr_buf.getvalue())

    @override_settings(
        LISTEN_ADDRESS="0.0.0.0:8000",
        WSGI_APPLICATION="myapp.wsgi.application",
        USE_WEBSOCKETS=False,
    )
    def test_run_gunicorn_no_websockets(self):
        orig_argv = sys.argv[:]
        sys.argv = ["manage.py", "server"]
        try:
            mock_gunicorn = MagicMock()
            bind_setting = MagicMock()
            bind_setting.name = "bind"
            worker_setting = MagicMock()
            worker_setting.name = "worker_class"
            mock_gunicorn.config.KNOWN_SETTINGS = [bind_setting, worker_setting]
            mock_app = MagicMock()

            class FakeWSGIApp:
                def __init__(self, prog):
                    pass

                def run(self):
                    # Call init with empty args (tests lines 142-143: args.append)
                    self.init(None, None, [])
                    # Call init with non-empty args (tests line 144: pass through)
                    self.init(None, None, ["app"])
                    return None

                def init(self, parser, opts, args):
                    pass

            mock_app.WSGIApplication = FakeWSGIApp
            with patch.dict(
                sys.modules,
                {
                    "gunicorn": mock_gunicorn,
                    "gunicorn.config": mock_gunicorn.config,
                    "gunicorn.app": mock_app,
                    "gunicorn.app.wsgiapp": mock_app,
                },
            ):
                cmd = self._make_cmd()
                cmd.run_gunicorn()
        finally:
            sys.argv = orig_argv

    @override_settings(
        LISTEN_ADDRESS="0.0.0.0:8000",
        WSGI_APPLICATION="myapp.wsgi.application",
        ASGI_APPLICATION="myapp.asgi.application",
        USE_WEBSOCKETS=True,
    )
    def test_run_gunicorn_with_websockets_uvicorn_worker_present(self):
        orig_argv = sys.argv[:]
        sys.argv = ["manage.py", "server"]
        try:
            mock_gunicorn = MagicMock()
            mock_gunicorn.config.KNOWN_SETTINGS = []
            mock_app = MagicMock()

            class FakeWSGIApp:
                def __init__(self, prog):
                    pass

                def run(self):
                    return None

            mock_app.WSGIApplication = FakeWSGIApp
            with (
                patch.dict(
                    sys.modules,
                    {
                        "gunicorn": mock_gunicorn,
                        "gunicorn.config": mock_gunicorn.config,
                        "gunicorn.app": mock_app,
                        "gunicorn.app.wsgiapp": mock_app,
                    },
                ),
                patch(
                    "df_config.management.commands.server.is_package_present",
                    return_value=True,
                ),
            ):
                cmd = self._make_cmd()
                cmd.run_gunicorn()
        finally:
            sys.argv = orig_argv

    @override_settings(
        LISTEN_ADDRESS="0.0.0.0:8000",
        WSGI_APPLICATION="myapp.wsgi.application",
        ASGI_APPLICATION="myapp.asgi.application",
        USE_WEBSOCKETS=True,
    )
    def test_run_gunicorn_with_websockets_uvicorn_not_present_workers_present(self):
        orig_argv = sys.argv[:]
        sys.argv = ["manage.py", "server"]
        try:
            mock_gunicorn = MagicMock()
            mock_gunicorn.config.KNOWN_SETTINGS = []
            mock_app = MagicMock()

            class FakeWSGIApp:
                def __init__(self, prog):
                    pass

                def run(self):
                    return None

            mock_app.WSGIApplication = FakeWSGIApp

            def fake_present(pkg):
                return pkg == "uvicorn.workers"

            with (
                patch.dict(
                    sys.modules,
                    {
                        "gunicorn": mock_gunicorn,
                        "gunicorn.config": mock_gunicorn.config,
                        "gunicorn.app": mock_app,
                        "gunicorn.app.wsgiapp": mock_app,
                    },
                ),
                patch(
                    "df_config.management.commands.server.is_package_present",
                    side_effect=fake_present,
                ),
            ):
                stderr_buf = io.StringIO()
                cmd = self._make_cmd()
                cmd.stderr = OutputWrapper(stderr_buf)
                cmd.run_gunicorn()
            self.assertIn("uvicorn-worker", stderr_buf.getvalue())
        finally:
            sys.argv = orig_argv

    @override_settings(
        LISTEN_ADDRESS="0.0.0.0:8000",
        WSGI_APPLICATION="myapp.wsgi.application",
        ASGI_APPLICATION="myapp.asgi.application",
        USE_WEBSOCKETS=True,
    )
    def test_run_gunicorn_with_websockets_neither_present(self):
        orig_argv = sys.argv[:]
        sys.argv = ["manage.py", "server"]
        try:
            mock_gunicorn = MagicMock()
            mock_gunicorn.config.KNOWN_SETTINGS = []
            mock_app = MagicMock()

            class FakeWSGIApp:
                def __init__(self, prog):
                    pass

            mock_app.WSGIApplication = FakeWSGIApp
            with (
                patch.dict(
                    sys.modules,
                    {
                        "gunicorn": mock_gunicorn,
                        "gunicorn.config": mock_gunicorn.config,
                        "gunicorn.app": mock_app,
                        "gunicorn.app.wsgiapp": mock_app,
                    },
                ),
                patch(
                    "df_config.management.commands.server.is_package_present",
                    return_value=False,
                ),
            ):
                cmd = self._make_cmd()
                cmd.run_gunicorn()
        finally:
            sys.argv = orig_argv

    @override_settings(
        LISTEN_ADDRESS="0.0.0.0:8000", ASGI_APPLICATION="myapp.asgi.application"
    )
    def test_run_uvicorn(self):
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            cmd = self._make_cmd()
            cmd.run_uvicorn()
        mock_uvicorn.run.assert_called_once()
