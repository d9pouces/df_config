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
import tempfile
from typing import Dict, Union
from unittest import TestCase

from df_config.checks import settings_check_results
from df_config.config.dynamic_settings import (
    AutocreateFile,
    AutocreateFileContent,
    CallableSetting,
    Directory,
    DynamicSettting,
    File,
    Path,
    RawValue,
    SettingReference,
)
from df_config.config.merger import SettingMerger
from df_config.config.values_providers import DictProvider


class TestDynamicSetting(TestCase):
    maxDiff = None
    setting_name = "X"
    other_values: Dict[str, Union[str, DynamicSettting]] = {"OTHER": "42"}

    def check(
        self,
        dynamic_setting: DynamicSettting,
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
