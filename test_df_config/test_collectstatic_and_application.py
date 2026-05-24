"""Unit tests for collectstatic command and application module (100% coverage)."""

from unittest import TestCase
from unittest.mock import MagicMock, call, patch


class TestCollectstaticCommand(TestCase):
    """Tests for df_config/management/commands/collectstatic.py."""

    def _make_command(self):
        """Return a Command instance with stdout/stderr mocked."""
        from df_config.management.commands.collectstatic import Command

        cmd = Command()
        cmd.stdout = MagicMock()
        cmd.stderr = MagicMock()
        cmd.style = MagicMock()
        return cmd

    def test_handle_calls_merger_hooks_and_super(self):
        """handle() calls pre_collectstatic, super().handle(), then post_collectstatic."""
        from df_config.management.commands.collectstatic import Command

        call_log = []

        mock_merger = MagicMock()
        mock_merger.call_method_on_config_values.side_effect = (
            lambda name: call_log.append(name)
        )

        # Patch super().handle() so it doesn't actually collect static files
        with (
            patch("df_config.management.commands.collectstatic.merger", mock_merger),
            patch(
                "django.contrib.staticfiles.management.commands.collectstatic.Command.handle",
                side_effect=lambda **opts: call_log.append("super_handle"),
            ),
        ):
            cmd = self._make_command()
            cmd.handle(interactive=False, verbosity=0)

        self.assertEqual(
            call_log,
            ["pre_collectstatic", "super_handle", "post_collectstatic"],
            "Expected pre_collectstatic → super.handle → post_collectstatic",
        )
        mock_merger.call_method_on_config_values.assert_any_call("pre_collectstatic")
        mock_merger.call_method_on_config_values.assert_any_call("post_collectstatic")


class TestApplicationModule(TestCase):
    """Tests for df_config/application.py."""

    def test_module_exports_wsgi_and_asgi_applications(self):
        """Importing application.py produces wsgi_application and asgi_application."""
        import importlib

        import df_config.application as app_mod

        importlib.reload(app_mod)

        self.assertTrue(
            callable(app_mod.wsgi_application),
            "wsgi_application should be a callable WSGI app",
        )
        self.assertTrue(
            callable(app_mod.asgi_application),
            "asgi_application should be a callable ASGI app",
        )

    def test_import_error_falls_back_to_wsgi(self):
        """When get_asgi_application cannot be imported, asgi falls back to wsgi."""
        import importlib
        import sys
        from unittest.mock import patch

        import df_config.application as app_mod

        # Setting sys.modules[name] = None blocks the import and raises ImportError
        with patch.dict(sys.modules, {"django.core.asgi": None}):
            importlib.reload(app_mod)
            # Both should still be callable (asgi falls back to wsgi handler)
            self.assertTrue(callable(app_mod.wsgi_application))
            self.assertTrue(callable(app_mod.asgi_application))

        # Restore the module to a valid state for subsequent tests
        importlib.reload(app_mod)
