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
import copy
import io
import os
import stat
import sys
import tempfile
from unittest import TestCase
from unittest.mock import MagicMock, patch

from df_config.checks import settings_check_results
from df_config.config.dynamic_settings import (
    AutocreateFile,
    AutocreateFileContent,
    CallableSetting,
    DeduplicatedCallableList,
    Directory,
    DirectoryOrNone,
    DynamicSettting,
    ExpandIterable,
    File,
    Path,
    RawValue,
    SettingReference,
)
from df_config.config.merger import SettingMerger
from df_config.config.values_providers import DictProvider


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _make_merger(settings_dict):
    """Return a SettingMerger with stdout/stderr captured."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    provider = DictProvider(settings_dict, name="test")
    merger = SettingMerger(None, [provider], stdout=stdout, stderr=stderr)
    merger.load_raw_settings()
    return merger, provider, stdout, stderr


class TestDynamicSetting(TestCase):
    maxDiff = None
    setting_name = "X"
    other_values = {"OTHER": "42"}

    def check(
        self,
        dynamic_setting,
        expected_value,
        pre_collectstatic=False,
        pre_migrate=False,
        post_collectstatic=False,
        post_migrate=False,
        previous_settings=None,
        extra_values=None,
        expected_stdout="",
        expected_stderr="",
    ):
        p_values = [x for x in settings_check_results]
        settings_check_results[:] = []
        values = previous_settings or copy.copy(self.other_values)
        if extra_values:
            values.update(extra_values)
        values[self.setting_name] = dynamic_setting

        if hasattr(dynamic_setting, "required"):
            values = {
                x: y for (x, y) in values.items() if x in dynamic_setting.required
            }
        provider = DictProvider(values, name="d1")
        stdout = io.StringIO()
        stderr = io.StringIO()
        merger = SettingMerger(None, [provider], stdout=stdout, stderr=stderr)
        merger.load_raw_settings()
        actual_value = dynamic_setting.get_value(
            merger, provider.name, self.setting_name
        )
        self.assertEqual(expected_value, actual_value)
        if pre_collectstatic:
            dynamic_setting.pre_collectstatic(
                merger, provider.name, self.setting_name, actual_value
            )
        if pre_migrate:
            dynamic_setting.pre_migrate(
                merger, provider.name, self.setting_name, actual_value
            )
        if post_collectstatic:
            dynamic_setting.post_collectstatic(
                merger, provider.name, self.setting_name, actual_value
            )
        if post_migrate:
            dynamic_setting.post_migrate(
                merger, provider.name, self.setting_name, actual_value
            )
        n_values = [x for x in settings_check_results]
        settings_check_results[:] = p_values
        self.assertEqual(expected_stdout, stdout.getvalue())
        self.assertEqual(expected_stderr, stderr.getvalue())
        if isinstance(dynamic_setting, CallableSetting):
            provided_keys = set(extra_values or {})
            expected_keys = set(dynamic_setting.required)
            self.assertTrue(provided_keys.issubset(expected_keys))
        return n_values


class TestDynamicSettingClasses(TestDynamicSetting):
    def test_raw_value(self):
        self.check(RawValue("{X}"), "{X}")

    def test_path(self):
        self.check(Path("./test/../parent"), "parent")

    def test_directory(self):
        with tempfile.TemporaryDirectory() as dirname:
            stdout = f"""Creating directory '{dirname}/test'
Change mode of '{dirname}/test' to 0o777\n"""
            path = dirname + "/test"
            r = self.check(
                Directory(path, mode=0o777),
                dirname + "/test/",
                pre_migrate=True,
                pre_collectstatic=True,
                expected_stdout=stdout,
            )
            self.assertTrue(os.path.isdir(path))
            self.assertEqual(1, len(r))
            self.assertEqual(0o777, (os.stat(path).st_mode & 0o777))
            stdout = f"""Change mode of '{dirname}/test' to 0o700\n"""
            r = self.check(
                Directory(path, mode=0o700),
                dirname + "/test/",
                pre_migrate=True,
                pre_collectstatic=True,
                expected_stdout=stdout,
            )
            self.assertTrue(os.path.isdir(path))
            self.assertEqual(0, len(r))
            self.assertEqual(0o700, (os.stat(path).st_mode & 0o777))

    def test_file(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = dirname + "/test/file"
            stdout = f"Creating directory '{dirname}/test'\n"
            r = self.check(
                File(path, mode=0o700),
                path,
                pre_migrate=True,
                pre_collectstatic=True,
                expected_stdout=stdout,
            )
            self.assertTrue(os.path.isdir(dirname + "/test"))
            self.assertFalse(os.path.isfile(path))
            self.assertEqual(1, len(r))
            with open(path, "w") as fd:
                fd.write("test")
            stdout = f"Change mode of '{dirname}/test/file' to 0o700\n"
            r = self.check(
                File(path, mode=0o700),
                path,
                pre_migrate=True,
                pre_collectstatic=True,
                expected_stdout=stdout,
            )
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(0, len(r))
            self.assertEqual(0o700, (os.stat(path).st_mode & 0o777))

    def test_autocreatefilecontent(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = dirname + "/test/file"
            stdout = f"""Creating directory '{dirname}/test'
Writing new value to '{dirname}/test/file'
Change mode of '{dirname}/test/file' to 0o700\n"""
            r = self.check(
                AutocreateFileContent(path, lambda x: "test", mode=0o700),
                "test",
                pre_migrate=True,
                pre_collectstatic=True,
                expected_stdout=stdout,
            )
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(1, len(r))
            self.assertEqual(0o700, (os.stat(path).st_mode & 0o777))

    def test_autocreatefile(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = dirname + "/test/file"
            stdout = (
                f"Creating directory '{dirname}/test'\n"
                f"Writing new value to '{dirname}/test/file'\n"
                f"Change mode of '{dirname}/test/file' to "
                "0o700\n"
            )
            r = self.check(
                AutocreateFile(path, mode=0o700),
                path,
                pre_migrate=True,
                pre_collectstatic=True,
                expected_stdout=stdout,
            )
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(1, len(r))
            self.assertEqual(0o700, (os.stat(path).st_mode & 0o777))

    def test_reference(self):
        self.check(SettingReference("OTHER"), "42")

    def test_callable_setting(self):
        def fn(values):
            return "[%(OTHER)s]" % values

        self.assertRaises(KeyError, lambda: self.check(CallableSetting(fn), "[42]"))
        self.check(CallableSetting(fn, "OTHER"), "[42]")
        fn.required_settings = ["OTHER"]
        self.check(CallableSetting(fn), "[42]")


# ===========================================================================
# Base DynamicSettting class
# ===========================================================================
class TestDynamicSettingBaseClass(TestCase):
    """Cover lines 69, 77, 85, 90, 95, 99, 113 in DynamicSettting."""

    def test_get_value_raises_not_implemented(self):
        """DynamicSettting.get_value must raise NotImplementedError."""
        ds = DynamicSettting("x")
        merger, provider, _, _ = _make_merger({"X": "1"})
        with self.assertRaises(NotImplementedError):
            ds.get_value(merger, "test", "X")

    def test_base_pass_methods_return_none(self):
        """pre_collectstatic/pre_migrate/post_collectstatic/post_migrate are no-ops."""
        ds = DynamicSettting("x")
        merger, _, _, _ = _make_merger({"X": "1"})
        self.assertIsNone(ds.pre_collectstatic(merger, "test", "X", "1"))
        self.assertIsNone(ds.pre_migrate(merger, "test", "X", "1"))
        self.assertIsNone(ds.post_collectstatic(merger, "test", "X", "1"))
        self.assertIsNone(ds.post_migrate(merger, "test", "X", "1"))

    def test_repr(self):
        """__repr__ returns 'ClassName(repr_of_value)'."""
        ds = DynamicSettting("hello")
        self.assertEqual("DynamicSettting('hello')", repr(ds))

    def test_eq(self):
        ds1 = DynamicSettting("a")
        ds2 = DynamicSettting("a")
        ds3 = DynamicSettting("b")
        self.assertEqual(ds1, ds2)
        self.assertNotEqual(ds1, ds3)
        self.assertNotEqual(ds1, "a")

    def test_add_warning_excluded_command_skipped(self):
        """add_warning adds nothing when current argv command is in excluded_commands."""
        p_values = list(settings_check_results)
        settings_check_results[:] = []
        with patch.object(sys, "argv", ["manage.py", "migrate"]):
            DynamicSettting.add_warning("test msg", {"migrate"})
        count = len(settings_check_results)
        settings_check_results[:] = p_values
        self.assertEqual(0, count)

    def test_add_warning_not_excluded(self):
        """add_warning fires when command is NOT in excluded_commands."""
        p_values = list(settings_check_results)
        settings_check_results[:] = []
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            DynamicSettting.add_warning("test msg", {"migrate"})
        count = len(settings_check_results)
        settings_check_results[:] = p_values
        self.assertEqual(1, count)


# ===========================================================================
# Path class methods
# ===========================================================================
class TestPathMethods(TestCase):
    """Cover lines 170, 174, 183-184, 188-189, 201-202."""

    def test_str(self):
        """Path.__str__ returns str(value)."""
        p = Path("/tmp/test")
        self.assertEqual("/tmp/test", str(p))

    def test_repr(self):
        """Path.__repr__ returns Path('value')."""
        p = Path("/tmp/test")
        r = repr(p)
        self.assertIn("Path", r)
        self.assertIn("/tmp/test", r)

    def test_makedirs_when_path_is_file(self):
        """makedirs when dirname exists as a file -> prints to stderr."""
        merger, _, stdout, stderr = _make_merger({"X": "1"})
        with tempfile.NamedTemporaryFile() as f:
            Path.makedirs(merger, f.name)
        self.assertIn("already exists", stderr.getvalue())

    def test_makedirs_exception(self):
        """makedirs when os.makedirs raises -> prints error to stderr."""
        merger, _, stdout, stderr = _make_merger({"X": "1"})
        with tempfile.TemporaryDirectory() as d:
            target = d + "/cannot/be/created"
            with patch(
                "df_config.config.dynamic_settings.os.makedirs",
                side_effect=OSError("perm denied"),
            ):
                Path.makedirs(merger, target)
        self.assertIn("Unable to create directory", stderr.getvalue())

    def test_chmod_exception(self):
        """chmod when os.chmod raises -> prints error to stderr."""
        merger, _, stdout, stderr = _make_merger({"X": "1"})
        p = Path("/tmp", mode=0o755)  # 0o755 differs from tempdir's 0o700
        with tempfile.TemporaryDirectory() as d:
            # Make sure current mode != 0o755 so chmod branch is taken
            os.chmod(d, 0o700)
            with patch(
                "df_config.config.dynamic_settings.os.chmod",
                side_effect=OSError("perm"),
            ):
                p.chmod(merger, d)
        self.assertIn("Unable to change mode", stderr.getvalue())

    def test_chmod_no_mode(self):
        """chmod with mode=None does nothing."""
        merger, _, stdout, stderr = _make_merger({"X": "1"})
        p = Path("/tmp", mode=None)
        with tempfile.TemporaryDirectory() as d:
            p.chmod(merger, d)  # should not raise or write
        self.assertEqual("", stderr.getvalue())

    def test_makedirs_already_dir(self):
        """makedirs when dirname already exists as a directory -> does nothing."""
        merger, _, stdout, stderr = _make_merger({"X": "1"})
        with tempfile.TemporaryDirectory() as d:
            Path.makedirs(merger, d)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual("", stdout.getvalue())

    def test_makedirs_empty_dirname(self):
        """makedirs with empty dirname -> does nothing."""
        merger, _, stdout, stderr = _make_merger({"X": "1"})
        Path.makedirs(merger, "")
        self.assertEqual("", stderr.getvalue())


# ===========================================================================
# Directory / DirectoryOrNone
# ===========================================================================
class TestDirectoryOrNone(TestDynamicSetting):
    """Cover lines 222, 249-252."""

    def test_directory_warning_when_missing(self):
        """Directory.get_value adds a warning when the path is not an existing dir."""
        r = self.check(Directory("/nonexistent/path/xyz"), "/nonexistent/path/xyz/")
        # r contains the warnings emitted during check
        self.assertEqual(1, len(r))

    def test_directory_none_value(self):
        """Directory.get_value returns None when value is empty."""
        self.check(Directory(""), None)

    def test_directory_or_none_existing(self):
        """DirectoryOrNone returns the path when it IS a directory."""
        with tempfile.TemporaryDirectory() as d:
            result = self.check(DirectoryOrNone(d), d + "/")

    def test_directory_or_none_missing(self):
        """DirectoryOrNone returns None when the path is not a directory."""
        self.check(DirectoryOrNone("/nonexistent/path/xyz99"), None)

    def test_directory_or_none_null_value(self):
        """DirectoryOrNone returns None when value is None."""
        self.check(DirectoryOrNone(""), None)


# ===========================================================================
# File missing branches
# ===========================================================================
class TestFileBranches(TestDynamicSetting):
    """Cover lines 272, 287."""

    def test_file_warning_when_missing(self):
        """File.get_value adds a W003 warning when the file does not exist."""
        r = self.check(File("/nonexistent/file.txt"), "/nonexistent/file.txt")
        w003 = [w for w in r if getattr(w, "id", "") == "df_config.W003"]
        self.assertEqual(1, len(w003))

    def test_file_get_value_none_when_value_is_none(self):
        """File.get_value returns None when analyze_raw_value returns None."""
        merger, provider, stdout, stderr = _make_merger({"X": "1"})
        f = File(None)
        result = f.get_value(merger, provider.name, "X")
        self.assertIsNone(result)

    def test_file_pre_collectstatic_none_value(self):
        """File.pre_collectstatic does nothing when value is None."""
        merger, provider, stdout, stderr = _make_merger({"X": "1"})
        f = File("/tmp/test.txt")
        f.pre_collectstatic(merger, "test", "X", None)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())


# ===========================================================================
# AutocreateFileContent missing branches
# ===========================================================================
class TestAutocreateFileContentBranches(TestDynamicSetting):
    """Cover lines 346, 356-357, 362, 372, 386-388, 391-394, 398-403, 428."""

    def test_create_file_already_exists(self):
        """create_file does nothing when the file already exists."""
        with tempfile.TemporaryDirectory() as d:
            path = d + "/existing.txt"
            with open(path, "w") as f:
                f.write("existing")
            merger, provider, stdout, stderr = _make_merger({"X": "1"})
            ac = AutocreateFileContent(path, lambda action: "new content")
            ac.create_file(merger, provider.name, "X")
            # File should still have the original content
            with open(path) as f:
                self.assertEqual("existing", f.read())
        self.assertEqual("", stdout.getvalue())

    def test_create_file_write_exception(self):
        """create_file catches write exceptions and writes to stderr."""
        with tempfile.TemporaryDirectory() as d:
            path = d + "/new.txt"
            merger, provider, stdout, stderr = _make_merger({"X": "1"})
            ac = AutocreateFileContent(path, lambda action: "content")
            with patch("builtins.open", side_effect=IOError("disk full")):
                ac.create_file(merger, provider.name, "X")
        self.assertIn("Unable to write content", stderr.getvalue())

    def test_create_file_result_none(self):
        """create_file warns on stderr when create_function returns None."""
        with tempfile.TemporaryDirectory() as d:
            path = d + "/new.txt"
            merger, provider, stdout, stderr = _make_merger({"X": "1"})
            ac = AutocreateFileContent(path, lambda action: None)
            ac.create_file(merger, provider.name, "X")
        self.assertIn("Invalid empty content", stderr.getvalue())

    def test_pre_collectstatic_enabled(self):
        """pre_collectstatic creates the file when use_collectstatic=True."""
        with tempfile.TemporaryDirectory() as d:
            path = d + "/cs.txt"
            merger, provider, stdout, stderr = _make_merger({"X": "1"})
            ac = AutocreateFileContent(
                path, lambda action: "data", use_collectstatic=True, use_migrate=False
            )
            ac.pre_collectstatic(merger, provider.name, "X", None)
            self.assertTrue(os.path.isfile(path))

    def test_pre_collectstatic_disabled(self):
        """pre_collectstatic does nothing when use_collectstatic=False."""
        with tempfile.TemporaryDirectory() as d:
            path = d + "/cs.txt"
            merger, provider, stdout, stderr = _make_merger({"X": "1"})
            ac = AutocreateFileContent(
                path, lambda action: "data", use_collectstatic=False, use_migrate=False
            )
            ac.pre_collectstatic(merger, provider.name, "X", None)
        self.assertFalse(os.path.isfile(path))

    def test_get_value_file_exists(self):
        """get_value reads the file content when it already exists."""
        with tempfile.TemporaryDirectory() as d:
            path = d + "/existing.txt"
            with open(path, "w") as f:
                f.write("file content")
            merger, provider, stdout, stderr = _make_merger({"X": "1"})
            ac = AutocreateFileContent(path, lambda action: "default")
            result = ac.get_value(merger, provider.name, "X")
        self.assertEqual("file content", result)

    def test_get_value_warning_both_migrate_and_collectstatic(self):
        """Warning text includes both migrate and collectstatic when both are True."""
        p_values = list(settings_check_results)
        settings_check_results[:] = []
        try:
            merger, provider, stdout, stderr = _make_merger({"X": "1"})
            ac = AutocreateFileContent(
                "/nonexistent/file_both.txt",
                lambda action: "x",
                use_migrate=True,
                use_collectstatic=True,
            )
            ac.get_value(merger, provider.name, "X")
        finally:
            warnings = list(settings_check_results)
            settings_check_results[:] = p_values
        self.assertTrue(
            any("migrate" in str(w) and "collectstatic" in str(w) for w in warnings)
        )

    def test_get_value_warning_only_collectstatic(self):
        """Warning text includes collectstatic when only use_collectstatic=True."""
        p_values = list(settings_check_results)
        settings_check_results[:] = []
        try:
            merger, provider, stdout, stderr = _make_merger({"X": "1"})
            ac = AutocreateFileContent(
                "/nonexistent/file_cs_only.txt",
                lambda action: "x",
                use_migrate=False,
                use_collectstatic=True,
            )
            ac.get_value(merger, provider.name, "X")
        finally:
            warnings = list(settings_check_results)
            settings_check_results[:] = p_values
        self.assertTrue(any("collectstatic" in str(w) for w in warnings))

    def test_get_value_warning_neither(self):
        """No 'run command' hint when both use_migrate=False, use_collectstatic=False."""
        p_values = list(settings_check_results)
        settings_check_results[:] = []
        try:
            merger, provider, stdout, stderr = _make_merger({"X": "1"})
            ac = AutocreateFileContent(
                "/nonexistent/file_none.txt",
                lambda action: "x",
                use_migrate=False,
                use_collectstatic=False,
            )
            ac.get_value(merger, provider.name, "X")
        finally:
            warnings = list(settings_check_results)
            settings_check_results[:] = p_values
        self.assertEqual(1, len(warnings))

    def test_unserialize_value(self):
        """unserialize_value returns the text as-is."""
        ac = AutocreateFileContent("/tmp/x", lambda a: "")
        self.assertEqual("hello", ac.unserialize_value("hello"))


# ===========================================================================
# SettingReference with func
# ===========================================================================
class TestSettingReferenceFunc(TestDynamicSetting):
    """Cover line 496 – SettingReference with a transform func."""

    def test_reference_with_func(self):
        """SettingReference with func applies it to the referenced value."""
        self.check(SettingReference("OTHER", func=int), 42)


# ===========================================================================
# CallableSetting: str import and __repr__
# ===========================================================================
class TestCallableSettingMisc(TestDynamicSetting):
    """Cover lines 536, 558-561."""

    def test_callable_setting_str_import(self):
        """CallableSetting accepts a dotted import path string as value."""
        # Use a well-known callable from the standard library
        cs = CallableSetting("os.path.basename", "OTHER")
        self.assertIs(cs.value, os.path.basename)

    def test_callable_setting_repr_with_module(self):
        """CallableSetting.__repr__ uses module.name for functions."""

        def my_fn(values):
            return values.get("OTHER", "")

        cs = CallableSetting(my_fn, "OTHER")
        r = repr(cs)
        self.assertIn("CallableSetting", r)
        self.assertIn("my_fn", r)

    def test_callable_setting_repr_no_module(self):
        """CallableSetting.__repr__ for lambdas without __module__/__name__."""
        fn = lambda values: values.get("OTHER", "")
        cs = CallableSetting(fn, "OTHER")
        r = repr(cs)
        self.assertIn("CallableSetting", r)


# ===========================================================================
# DeduplicatedCallableList
# ===========================================================================
class TestDeduplicatedCallableList(TestDynamicSetting):
    """Cover lines 572-573."""

    def test_dedup(self):
        """DeduplicatedCallableList removes duplicates from the list."""

        def my_fn(values):
            return ["a", "b", "a", "c"]

        my_fn.required_settings = []
        cs = DeduplicatedCallableList(my_fn)
        merger, provider, _, _ = _make_merger({"X": cs})
        merger.load_raw_settings()
        result = cs.get_value(merger, "test", "X")
        self.assertEqual(["a", "b", "c"], result)
