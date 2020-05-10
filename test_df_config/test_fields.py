# ##############################################################################
#  This file is part of df_config                                              #
#                                                                              #
#  Copyright (C) 2020 Matthieu Gallet <github@19pouces.net>                    #
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
    FloatConfigField,
    IntegerConfigField,
    ListConfigField,
    bool_setting,
    guess_relative_path,
    str_or_blank,
    str_or_none,
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
        if k not in {"1", "ok", "yes", "true", "on"}:
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
