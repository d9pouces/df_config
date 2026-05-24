"""Unit tests for df_config/management/commands/config.py."""

import io
import os
import tempfile
from collections import OrderedDict
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.core.management.base import OutputWrapper


def _make_style():
    style = MagicMock()
    style.SUCCESS = lambda x: x
    style.ERROR = lambda x: x
    style.WARNING = lambda x: x
    return style


def _make_merger(settings=None, providers=None, raw_settings=None):
    mock = MagicMock()
    mock.settings = settings if settings is not None else {"MY_SETTING": 42}
    mock.providers = providers if providers is not None else []
    mock.raw_settings = (
        raw_settings
        if raw_settings is not None
        else {"MY_SETTING": OrderedDict([("p1", 42)])}
    )
    mock.fields_provider = MagicMock()
    mock.fields_provider.__str__ = MagicMock(return_value="MyFieldsProvider")
    return mock


class TestConfigCommand(TestCase):
    def _make_cmd(self):
        from df_config.management.commands.config import Command

        cmd = Command()
        cmd.stdout = OutputWrapper(io.StringIO())
        cmd.stderr = OutputWrapper(io.StringIO())
        cmd.style = _make_style()
        return cmd

    # ---- handle() ----

    def test_handle_delegates_to_handle_head(self):
        cmd = self._make_cmd()
        called = []
        cmd.handle_head = lambda **kw: called.append(kw)
        cmd.handle(action="python", verbosity=1, filename=None)
        self.assertEqual(1, len(called))

    def test_handle_swallows_broken_pipe(self):
        cmd = self._make_cmd()
        cmd.handle_head = lambda **kw: (_ for _ in ()).throw(BrokenPipeError())
        # Should not raise
        cmd.handle(action="python", verbosity=1, filename=None)

    # ---- show_python_config() ----

    def test_show_python_config_verbosity_1(self):
        mock_merger = _make_merger(
            settings={"SETTING_A": 42},
            providers=[MagicMock(is_valid=MagicMock(return_value=True), name="p1")],
            raw_settings={"SETTING_A": OrderedDict([("p1", 42)])},
        )
        mock_merger.providers[0].__str__ = MagicMock(return_value="p1")
        cmd = self._make_cmd()
        with (
            patch("df_config.management.commands.config.merger", mock_merger),
            patch(
                "df_config.management.commands.config.get_version", return_value="1.0.0"
            ),
            patch(
                "df_config.management.commands.config.guess_version",
                return_value="2.0.0",
            ),
        ):
            cmd.show_python_config(verbosity=1)
        output = cmd.stdout._out.getvalue()
        self.assertIn("SETTING_A", output)

    def test_show_python_config_verbosity_2_invalid_provider(self):
        p1 = MagicMock()
        p1.name = "p1"
        p1.is_valid.return_value = True
        p2 = MagicMock()
        p2.name = "p2"
        p2.is_valid.return_value = False
        mock_merger = _make_merger(
            settings={"SETTING_A": 42},
            providers=[p1, p2],
            raw_settings={"SETTING_A": OrderedDict([(None, 42), ("p1", 99)])},
        )
        cmd = self._make_cmd()
        with (
            patch("df_config.management.commands.config.merger", mock_merger),
            patch(
                "df_config.management.commands.config.get_version", return_value="1.0.0"
            ),
            patch(
                "df_config.management.commands.config.guess_version",
                return_value="2.0.0",
            ),
        ):
            cmd.show_python_config(verbosity=2)
        output = cmd.stdout._out.getvalue()
        self.assertIn("SETTING_A", output)

    def test_show_python_config_with_imports(self):
        from collections import OrderedDict as OD

        mock_merger = _make_merger(
            settings={"SETTING_A": OD()},
            providers=[],
            raw_settings={"SETTING_A": OD()},
        )
        cmd = self._make_cmd()
        with (
            patch("df_config.management.commands.config.merger", mock_merger),
            patch(
                "df_config.management.commands.config.get_version", return_value="1.0.0"
            ),
            patch(
                "df_config.management.commands.config.guess_version",
                return_value="2.0.0",
            ),
        ):
            cmd.show_python_config(verbosity=1)
        output = cmd.stdout._out.getvalue()
        self.assertIn("import", output)

    # ---- show_ini_config() ----

    def test_show_ini_config_verbosity_1_valid_provider(self):
        from df_config.config.values_providers import IniConfigProvider

        valid_provider = IniConfigProvider("/some/path.ini")
        valid_provider.is_valid = lambda: True
        valid_provider.name = "ini1"
        mock_merger = _make_merger(providers=[valid_provider])
        mock_merger.write_provider = MagicMock()
        cmd = self._make_cmd()
        with patch("df_config.management.commands.config.merger", mock_merger):
            cmd.show_ini_config(verbosity=1)

    def test_show_ini_config_verbosity_2_invalid_provider(self):
        from df_config.config.values_providers import IniConfigProvider

        invalid_provider = IniConfigProvider("/missing.ini")
        invalid_provider.is_valid = lambda: False
        invalid_provider.name = "ini_invalid"
        non_ini_provider = MagicMock()
        mock_merger = _make_merger(providers=[invalid_provider, non_ini_provider])
        mock_merger.write_provider = MagicMock()
        cmd = self._make_cmd()
        with patch("df_config.management.commands.config.merger", mock_merger):
            cmd.show_ini_config(verbosity=2)

    # ---- show_env_config() ----

    def test_show_env_config_no_prefix(self):
        from df_config.config.values_providers import IniConfigProvider

        non_env_provider = IniConfigProvider("/some.ini")
        non_env_provider.is_valid = lambda: False
        mock_merger = _make_merger(providers=[non_env_provider])
        stderr_buf = io.StringIO()
        cmd = self._make_cmd()
        cmd.stderr = OutputWrapper(stderr_buf)
        with patch("df_config.management.commands.config.merger", mock_merger):
            cmd.show_env_config(verbosity=1)
        self.assertIn("Environment variables", stderr_buf.getvalue())

    def test_show_env_config_with_prefix(self):
        from df_config.config.values_providers import EnvironmentConfigProvider

        env_provider = EnvironmentConfigProvider("MYAPP_")
        mock_merger = _make_merger(providers=[env_provider])
        mock_merger.write_provider = MagicMock()
        cmd = self._make_cmd()
        with patch("df_config.management.commands.config.merger", mock_merger):
            cmd.show_env_config(verbosity=1)

    def test_show_env_config_verbosity_2(self):
        from df_config.config.values_providers import EnvironmentConfigProvider

        env_provider = EnvironmentConfigProvider("MYAPP_")
        mock_merger = _make_merger(providers=[env_provider])
        mock_merger.write_provider = MagicMock()
        cmd = self._make_cmd()
        with patch("df_config.management.commands.config.merger", mock_merger):
            cmd.show_env_config(verbosity=2)

    # ---- handle_head() with filename ----

    def test_handle_head_python_with_filename(self):
        mock_merger = _make_merger(
            settings={"A": 1}, providers=[], raw_settings={"A": OrderedDict()}
        )
        cmd = self._make_cmd()
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "output.py")
            with (
                patch("df_config.management.commands.config.merger", mock_merger),
                patch(
                    "df_config.management.commands.config.get_version",
                    return_value="1.0.0",
                ),
                patch(
                    "df_config.management.commands.config.guess_version",
                    return_value="2.0.0",
                ),
            ):
                cmd.handle_head(action="python", verbosity=1, filename=filename)
            self.assertTrue(os.path.isfile(filename))

    def test_handle_head_env_with_filename(self):
        from df_config.config.values_providers import EnvironmentConfigProvider

        env_provider = EnvironmentConfigProvider("MYAPP_")
        mock_merger = _make_merger(providers=[env_provider])
        mock_merger.write_provider = MagicMock()
        cmd = self._make_cmd()
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "output.env")
            with patch("df_config.management.commands.config.merger", mock_merger):
                cmd.handle_head(action="env", verbosity=1, filename=filename)
            self.assertTrue(os.path.isfile(filename))

    def test_handle_head_ini_does_not_write_file(self):
        mock_merger = _make_merger(providers=[])
        mock_merger.write_provider = MagicMock()
        cmd = self._make_cmd()
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "output.ini")
            with (
                patch("df_config.management.commands.config.merger", mock_merger),
                patch(
                    "df_config.management.commands.config.IniConfigProvider"
                ) as MockIni,
            ):
                mock_ini = MagicMock()
                mock_ini.to_str.return_value = "[section]\nkey=val"
                MockIni.return_value = mock_ini
                cmd.handle_head(action="ini", verbosity=1, filename=filename)
            self.assertFalse(os.path.isfile(filename))

    # ---- show_external_config() ----

    def test_show_external_config(self):
        mock_merger = _make_merger(settings={"KEY": "val"})
        cmd = self._make_cmd()
        with (
            patch("df_config.management.commands.config.merger", mock_merger),
            patch(
                "df_config.management.commands.config.render_to_string",
                return_value="rendered",
            ),
        ):
            cmd.show_external_config("some/template.html")
        self.assertIn("rendered", cmd.stdout._out.getvalue())

    # ---- _add_import() ----

    def test_add_import_builtin_ignored(self):
        from df_config.management.commands.config import Command

        imports = {}
        Command._add_import("name", 42, imports)
        self.assertEqual({}, imports)

    def test_add_import_non_builtin(self):
        from collections import OrderedDict

        from df_config.management.commands.config import Command

        imports = {}
        Command._add_import("name", OrderedDict(), imports)
        self.assertIn("collections", imports)
        self.assertIn("OrderedDict", imports["collections"])

    def test_add_import_with_type(self):
        from collections import OrderedDict

        from df_config.management.commands.config import Command

        imports = {}
        Command._add_import("name", OrderedDict, imports)
        self.assertIn("collections", imports)

    # ---- get_raw_imports() / _recursive_add_import() ----

    def test_get_raw_imports_dict_value(self):
        from collections import OrderedDict

        mock_merger = _make_merger(settings={"X": OrderedDict([("key", 42)])})
        cmd = self._make_cmd()
        with patch("df_config.management.commands.config.merger", mock_merger):
            imports = cmd.get_raw_imports(["X"])
        self.assertIn("collections", imports)

    def test_get_raw_imports_list_value(self):
        from collections import OrderedDict

        mock_merger = _make_merger(settings={"X": [OrderedDict()]})
        cmd = self._make_cmd()
        with patch("df_config.management.commands.config.merger", mock_merger):
            imports = cmd.get_raw_imports(["X"])
        self.assertIn("collections", imports)

    def test_get_raw_imports_missing_setting(self):
        mock_merger = _make_merger(settings={})
        cmd = self._make_cmd()
        with patch("df_config.management.commands.config.merger", mock_merger):
            imports = cmd.get_raw_imports(["MISSING"])
        self.assertEqual({}, imports)

    # ---- add_arguments() ----

    def test_add_arguments(self):
        from argparse import ArgumentParser

        from df_config.management.commands.config import Command

        cmd = Command()
        parser = ArgumentParser()
        cmd.add_arguments(parser)
        args = parser.parse_args(["python"])
        self.assertEqual("python", args.action)
        self.assertIsNone(args.filename)

    # ---- line 266: setting in raw_settings but not in settings ----

    def test_show_python_config_setting_skipped_when_not_in_settings(self):
        # "MISSING" is in raw_settings but not in settings → continue at line 266
        mock_merger = _make_merger(
            settings={"SETTING_A": 42},
            providers=[],
            raw_settings={
                "SETTING_A": OrderedDict([("p1", 42)]),
                "MISSING": OrderedDict([("p1", 99)]),
            },
        )
        cmd = self._make_cmd()
        with (
            patch("df_config.management.commands.config.merger", mock_merger),
            patch(
                "df_config.management.commands.config.get_version", return_value="1.0.0"
            ),
            patch(
                "df_config.management.commands.config.guess_version",
                return_value="2.0.0",
            ),
        ):
            cmd.show_python_config(verbosity=1)
        output = cmd.stdout._out.getvalue()
        self.assertNotIn("MISSING", output)

    # ---- lines 126-128: black formatting ----

    def test_handle_head_python_with_filename_and_black(self):
        import sys

        mock_black = MagicMock()
        mock_black.FileMode.return_value = MagicMock()
        mock_black.format_file_contents.return_value = "formatted = 1\n"
        mock_merger = _make_merger(
            settings={"A": 1}, providers=[], raw_settings={"A": OrderedDict()}
        )
        cmd = self._make_cmd()
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "output.py")
            with (
                patch("df_config.management.commands.config.merger", mock_merger),
                patch(
                    "df_config.management.commands.config.get_version",
                    return_value="1.0.0",
                ),
                patch(
                    "df_config.management.commands.config.guess_version",
                    return_value="2.0.0",
                ),
                patch.dict(sys.modules, {"black": mock_black}),
            ):
                cmd.handle_head(action="python", verbosity=1, filename=filename)
            with open(filename) as f:
                content = f.read()
        self.assertEqual("formatted = 1\n", content)
