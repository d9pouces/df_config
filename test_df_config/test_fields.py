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
import math
import os
import tempfile
from unittest import TestCase

from hypothesis import given
from hypothesis.strategies import floats, integers, text

from df_config.checks import settings_check_results
from df_config.config.fields import (
    BooleanConfigField,
    CharConfigField,
    ChoiceConfigFile,
    ConfigField,
    DirectoryPathConfigField,
    FilePathConfigField,
    FloatConfigField,
    IntegerConfigField,
    ListConfigField,
    bool_setting,
    guess_relative_path,
    str_or_blank,
    str_or_none,
    str_to_directory_path,
    str_to_filepath,
    strip_split,
)
from df_config.utils import ensure_dir


class TestFunctions(TestCase):
    def test_bool_setting(self):
        for k in {"1", "ok", "yes", "true", "on"}:
            self.assertTrue(bool_setting(k))
        for k in {"0", "ko", "no", "false", "of"}:
            self.assertFalse(bool_setting(k))

    @given(text())
    def test_bool_setting_multi(self, k):
        if k.lower() not in {"1", "ok", "yes", "true", "on"}:
            self.assertFalse(bool_setting(k))

    def test_str_or_none(self):
        self.assertIsNone(str_or_none(""))
        self.assertIsNone(str_or_none(None))

    @given(text())
    def test_str_or_none_multi(self, k):
        if k:
            self.assertEqual(k, str_or_none(k))

    def test_str_or_blank(self):
        self.assertEqual("", str_or_blank(""))
        self.assertEqual("", str_or_blank(None))

    @given(text())
    def test_str_or_blank_multi(self, k):
        self.assertEqual(k, str_or_blank(k))

    def test_guess_relative_path(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as dirname:
            os.chdir(dirname)
            dirname = os.getcwd()
            tested_path = os.path.join(dirname, "test1", "test2")
            r_1 = guess_relative_path(tested_path)
            ensure_dir(tested_path, parent=False)
            r_2 = guess_relative_path(tested_path)

        os.chdir(cwd)
        self.assertEqual("./test1/test2", r_1)
        self.assertEqual("./test1/test2", r_2)
        self.assertEqual("", guess_relative_path(None))
        self.assertEqual("", guess_relative_path(""))

    def test_guess_relative_path_outside_cwd(self):
        """guess_relative_path returns the absolute path when not under cwd."""
        # /tmp is typically not a sub-path of whatever the cwd is
        result = guess_relative_path("/tmp")
        self.assertTrue(os.path.isabs(result))

    @given(text())
    def test_guess_relative_path_multi(self, value):
        guess_relative_path(value)

    def test_strip_split(self):
        r = strip_split("keyword1, keyword2 ,,keyword3")
        self.assertEqual(["keyword1", "keyword2", "keyword3"], r)
        self.assertEqual([], strip_split(",,,,"))
        self.assertEqual([], strip_split(None))
        self.assertEqual([], strip_split(""))


class TestFields(TestCase):
    def assertEqual(self, x, y, msg=None):
        if (
            isinstance(x, float)
            and isinstance(y, float)
            and math.isnan(x)
            and math.isnan(y)
        ):
            return
        super().assertEqual(x, y, msg=msg)

    def check(self, field: ConfigField, str_value, py_value, reverse: bool = True):
        self.assertEqual(py_value, field.from_str(str_value))
        if reverse:
            self.assertEqual(str_value, field.to_str(py_value))
            self.assertEqual(str_value, field.to_str(field.from_str(str_value)))
            self.assertEqual(py_value, field.from_str(field.to_str(py_value)))

    def test_char_config_field(self):
        self.check(CharConfigField("test.test", "TEST", allow_none=True), "", None)
        self.check(CharConfigField("test.test", "TEST", allow_none=False), "", "")

    @given(text())
    def test_char_config_field_multi(self, value):
        self.check(CharConfigField("test.test", "TEST", allow_none=False), value, value)

    def test_int_config_field(self):
        self.check(IntegerConfigField("test.test", "TEST", allow_none=False), "0", 0)
        self.check(IntegerConfigField("test.test", "TEST", allow_none=False), "1", 1)
        self.check(IntegerConfigField("test.test", "TEST", allow_none=True), "", None)
        self.check(
            IntegerConfigField("test.test", "TEST", allow_none=False),
            "",
            0,
            reverse=False,
        )

    @given(integers())
    def test__config_field_multi(self, value):
        self.check(
            IntegerConfigField("test.test", "TEST", allow_none=False), str(value), value
        )

    def test_float_config_field(self):
        self.check(FloatConfigField("test.test", "TEST", allow_none=False), "0.0", 0.0)
        self.check(FloatConfigField("test.test", "TEST", allow_none=False), "1.0", 1.0)
        self.check(FloatConfigField("test.test", "TEST", allow_none=True), "", None)
        self.check(
            FloatConfigField("test.test", "TEST", allow_none=False),
            "",
            0.0,
            reverse=False,
        )

    @given(floats())
    def test_float_config_field_multi(self, value):
        self.check(
            FloatConfigField("test.test", "TEST", allow_none=False), str(value), value
        )

    def test_list_config_field(self):
        self.check(ListConfigField("test.test", "TEST"), "0,1", ["0", "1"])
        self.check(ListConfigField("test.test", "TEST"), "", [])

    def test_bool_config_field(self):
        self.check(BooleanConfigField("test.test", "TEST"), "true", True)
        self.check(BooleanConfigField("test.test", "TEST"), "false", False)

    def test_choice_config_field(self):
        p_values = [x for x in settings_check_results]
        settings_check_results[:] = []
        self.check(
            ChoiceConfigFile("test.test", "TEST", {"1": "V1", "2": "V2"}), "1", "V1"
        )
        self.assertEqual(0, len(settings_check_results))
        self.check(
            ChoiceConfigFile("test.test", "TEST", {"1": "V1", "2": "V2"}),
            "3",
            None,
            reverse=False,
        )
        self.assertEqual(1, len(settings_check_results))

        settings_check_results[:] = p_values


class TestStrToFilepath(TestCase):
    """Cover lines 69-80 (str_to_filepath)."""

    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def test_none_returns_none(self):
        self.assertIsNone(str_to_filepath(None))
        self.assertIsNone(str_to_filepath(""))
        self.assertIsNone(str_to_filepath("   "))

    def test_nonexistent_file_adds_warning(self):
        result = str_to_filepath("/nonexistent/path/test_file.txt")
        self.assertIsNotNone(result)
        self.assertEqual(1, len(settings_check_results))
        self.assertEqual("df_config.W002", settings_check_results[0].id)

    def test_existing_file_no_warning(self):
        with tempfile.NamedTemporaryFile() as f:
            result = str_to_filepath(f.name)
        self.assertEqual(0, len(settings_check_results))
        self.assertIsNotNone(result)

    def test_strips_whitespace(self):
        with tempfile.NamedTemporaryFile() as f:
            result = str_to_filepath("  " + f.name + "  ")
        self.assertEqual(os.path.abspath(f.name), result)


class TestStrToDirectoryPath(TestCase):
    """Cover lines 91-102 (str_to_directory_path)."""

    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def test_none_returns_none(self):
        self.assertIsNone(str_to_directory_path(None))
        self.assertIsNone(str_to_directory_path(""))

    def test_nonexistent_dir_adds_warning(self):
        result = str_to_directory_path("/nonexistent/xyz_dir_test")
        self.assertIsNotNone(result)
        self.assertEqual(1, len(settings_check_results))

    def test_existing_dir_no_warning(self):
        with tempfile.TemporaryDirectory() as d:
            result = str_to_directory_path(d)
        self.assertEqual(0, len(settings_check_results))
        self.assertIsNotNone(result)


class TestConfigFieldHelpers(TestCase):
    """Cover lines 168, 172 (ConfigField.get_help and __str__)."""

    def test_get_help(self):
        f = ConfigField("section.name", "MY_SETTING", help_str="My help text.")
        self.assertEqual("My help text.", f.get_help())

    def test_str_with_name(self):
        f = ConfigField("section.name", "MY_SETTING")
        self.assertEqual("section.name", str(f))

    def test_str_without_name(self):
        f = ConfigField(None, "MY_SETTING")
        self.assertEqual("MY_SETTING", str(f))


class TestBooleanConfigFieldAllowNone(TestCase):
    """Cover lines 253-261 (BooleanConfigField with allow_none=True)."""

    def test_empty_string_returns_none(self):
        f = BooleanConfigField("s.k", "S", allow_none=True)
        self.assertIsNone(f.from_str(""))
        self.assertIsNone(f.from_str(None))

    def test_true_value(self):
        f = BooleanConfigField("s.k", "S", allow_none=True)
        self.assertTrue(f.from_str("true"))

    def test_to_str_none(self):
        f = BooleanConfigField("s.k", "S", allow_none=True)
        self.assertEqual("", f.to_str(None))

    def test_to_str_false(self):
        f = BooleanConfigField("s.k", "S", allow_none=True)
        self.assertEqual("false", f.to_str(False))

    def test_to_str_true(self):
        f = BooleanConfigField("s.k", "S", allow_none=True)
        self.assertEqual("true", f.to_str(True))


class TestChoiceConfigFileHelpers(TestCase):
    """Cover lines 311, 326-336 (ChoiceConfigFile.to_str no match + get_help)."""

    def test_to_str_no_match_returns_empty(self):
        f = ChoiceConfigFile("s.k", "S", {"a": "ValA", "b": "ValB"})
        self.assertEqual("", f.to_str("UnknownValue"))

    def test_get_help_with_doc(self):
        f = ChoiceConfigFile(
            "s.k", "S", {"a": "ValA", "b": "ValB"}, help_str="My help."
        )
        help_text = f.get_help()
        self.assertIn("My help.", help_text)
        self.assertIn('"a"', help_text)

    def test_get_help_without_doc(self):
        f = ChoiceConfigFile("s.k", "S", {"a": "ValA"})
        f.__doc__ = None  # simulate missing docstring
        help_text = f.get_help()
        self.assertIn('"a"', help_text)


class TestFileAndDirPathFields(TestCase):
    """Cover lines 344, 350-352 (FilePathConfigField and DirectoryPathConfigField)."""

    def test_file_path_config_field_init(self):
        f = FilePathConfigField("section.path", "MY_FILE_PATH")
        self.assertEqual("section.path", f.name)
        self.assertEqual(str_to_filepath, f.from_str)

    def test_directory_path_config_field_init(self):
        f = DirectoryPathConfigField("section.dir", "MY_DIR_PATH")
        self.assertEqual("section.dir", f.name)
        self.assertEqual(str_to_directory_path, f.from_str)
