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
import os
import tempfile
from collections import OrderedDict
from typing import Dict, Iterable
from unittest import TestCase

import pkg_resources

from df_config.config.fields import BooleanConfigField, CharConfigField
from df_config.config.values_providers import (
    DictProvider,
    EnvironmentConfigProvider,
    IniConfigProvider,
    PythonFileProvider,
    PythonModuleProvider,
)


class EnvPatch:
    def __init__(self, delete: Iterable[str] = None, **values):
        self.backup = os.environ.copy()  # type: Dict[str, str]
        self.values = values  # type: Dict[str, str]
        self.delete = delete

    def __enter__(self):
        if self.delete:
            for key in self.delete:
                if key in os.environ:
                    del os.environ[key]
        for k, v in self.values.items():
            os.environ[k] = v
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        keys = list(os.environ)
        for k in keys:
            if k not in self.backup:
                del os.environ[k]
        os.environ.update(self.backup)


class TestEnvironmentConfigProvider(TestCase):
    def test_has_value(self):
        provider = EnvironmentConfigProvider(prefix="DF_")
        with EnvPatch(DF_UNITTEST="on"):
            self.assertTrue(
                provider.has_value(BooleanConfigField("test.test", "UNITTEST"))
            )
            self.assertFalse(
                provider.has_value(BooleanConfigField("test.test2", "UNITTEST_2"))
            )

    def test_get_value(self):
        provider = EnvironmentConfigProvider(prefix="DF_")
        with EnvPatch(DF_UNITTEST="off"):
            v = provider.get_value(
                BooleanConfigField("test.test", "UNITTEST", default=True)
            )
            self.assertEqual(False, v)

    def test_get_extra_settings(self):
        provider = EnvironmentConfigProvider(prefix="DF_")
        self.assertEqual([], provider.get_extra_settings())

    def test_is_valid(self):
        provider = EnvironmentConfigProvider(prefix="DF_")
        self.assertEqual(True, provider.is_valid())

    def test_to_str(self):
        provider = EnvironmentConfigProvider(prefix="DF_")
        with EnvPatch():
            provider.set_value(
                BooleanConfigField("test.test", "UNITTEST", default=True)
            )
            provider.set_value(
                CharConfigField(
                    "test.test2", "UNITTEST2", default="$KEY {VALUE} 'SPECIAL \"CHARS"
                )
            )
        content = provider.to_str()
        self.assertEqual(
            "DF_UNITTEST=true\nDF_UNITTEST2='$KEY {VALUE} '\"'\"'SPECIAL \"CHARS'\n",
            content,
        )


class TestIniConfigProvider(TestCase):
    def test_has_value(self):
        with tempfile.NamedTemporaryFile() as fd:
            fd.write(b"[test]\ntest = on\n")
            fd.flush()
            provider = IniConfigProvider(config_file=fd.name)
            self.assertTrue(
                provider.has_value(BooleanConfigField("test.test", "UNITTEST"))
            )
            self.assertFalse(
                provider.has_value(BooleanConfigField("test.test2", "UNITTEST_2"))
            )

    def test_to_str(self):
        with tempfile.NamedTemporaryFile() as fd:
            fd.write(b"[test]\ntest = on\n")
            fd.flush()
            provider = IniConfigProvider(config_file=fd.name)
            provider.set_value(
                BooleanConfigField("test.test", "UNITTEST", default=True)
            )
            provider.set_value(
                CharConfigField(
                    "test.test2", "UNITTEST2", default="$KEY {VALUE} 'SPECIAL \"CHARS"
                )
            )
        content = provider.to_str()
        self.assertEqual(
            "[test]\ntest = true\ntest2 = $KEY {VALUE} 'SPECIAL \"CHARS\n\n", content
        )

    def test_get_value(self):
        with tempfile.NamedTemporaryFile() as fd:
            fd.write(b"[test]\ntest = off\n")
            fd.flush()
            provider = IniConfigProvider(config_file=fd.name)
            v = provider.get_value(
                BooleanConfigField("test.test", "UNITTEST", default=True)
            )
            self.assertEqual(False, v)

    def test_get_extra_settings(self):
        with tempfile.NamedTemporaryFile() as fd:
            fd.write(b"[test]\ntest = off\n")
            fd.flush()
            provider = IniConfigProvider(config_file=fd.name)
            self.assertEqual([], provider.get_extra_settings())

    def test_is_valid(self):
        with tempfile.NamedTemporaryFile() as fd:
            fd.write(b"[test]\ntest = off\n")
            fd.flush()
            provider = IniConfigProvider(config_file=fd.name)
            self.assertEqual(True, provider.is_valid())
        provider = IniConfigProvider(config_file=fd.name)
        self.assertEqual(False, provider.is_valid())


class TestPythonModuleProvider(TestCase):
    def test_has_value(self):
        provider = self.get_provider()
        self.assertTrue(provider.has_value(BooleanConfigField("test.test", "UNITTEST")))
        self.assertFalse(
            provider.has_value(BooleanConfigField("test.test2", "UNITTEST_2"))
        )

    def get_provider(self):
        return PythonModuleProvider("test_df_config.data.sample_settings")

    def test_to_str(self):
        provider = self.get_provider()
        provider.set_value(BooleanConfigField("test.test", "UNITTEST", default=True))
        provider.set_value(
            CharConfigField(
                "test.test2", "UNITTEST2", default="$KEY {VALUE} 'SPECIAL \"CHARS"
            )
        )
        content = provider.to_str()
        self.assertEqual(self.get_str_form(), content)

    def get_str_form(self):
        return "UNITTEST = True\nUNITTEST2 = '$KEY {VALUE} \\'SPECIAL \"CHARS'\n"

    def test_get_value(self):
        provider = self.get_provider()
        v = provider.get_value(
            BooleanConfigField("test.test", "UNITTEST_3", default=True)
        )
        self.assertEqual(False, v)

    def test_get_extra_settings(self):
        provider = self.get_provider()
        settings = {k: v for k, v in provider.get_extra_settings()}
        self.assertEqual({"UNITTEST": True, "UNITTEST_3": False,}, settings)

    def test_is_valid(self):
        provider = self.get_provider()
        self.assertEqual(True, provider.is_valid())
        provider = PythonModuleProvider("test_df_config.data.sample_settings2")
        self.assertEqual(False, provider.is_valid())
        provider = PythonFileProvider(
            pkg_resources.resource_filename(
                "test_df_config.data", "sample_settings2.py"
            )
        )
        self.assertEqual(False, provider.is_valid())


class TestPythonFileProvider(TestPythonModuleProvider):
    def get_provider(self):
        return PythonFileProvider(
            pkg_resources.resource_filename("test_df_config.data", "sample_settings.py")
        )


class TestDictProvider(TestPythonFileProvider):
    def get_provider(self):
        values = OrderedDict()
        values["UNITTEST"] = True
        values["UNITTEST_3"] = False
        return DictProvider(values)

    def get_str_form(self):
        return "{'UNITTEST': True, 'UNITTEST_3': False, 'UNITTEST2': '$KEY {VALUE} \\'SPECIAL \"CHARS'}"
