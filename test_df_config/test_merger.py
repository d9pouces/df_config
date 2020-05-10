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
from collections import OrderedDict, defaultdict
from unittest import TestCase

from df_config.config.dynamic_settings import RawValue, SettingReference
from df_config.config.merger import SettingMerger
from df_config.config.values_providers import DictProvider


class TestSettingMerger(TestCase):
    def test_priority(self):
        merger = SettingMerger(
            None,
            [DictProvider({"X": 1}, name="d1"), DictProvider({"X": 2}, name="d2")],
        )
        merger.process()
        merger.post_process()
        self.assertEqual({"X": 2}, merger.settings)
        self.assertEqual(OrderedDict([("d1", 1), ("d2", 2)]), merger.raw_settings["X"])

    def test_postprocess(self):
        merger = SettingMerger(
            None,
            [
                DictProvider(
                    {
                        "INSTALLED_APPS": [
                            "df_config",
                            "django.contrib.auth",
                            "df_config",
                        ]
                    },
                    name="d1",
                )
            ],
        )
        merger.process()
        self.assertEqual(
            {"INSTALLED_APPS": ["df_config", "django.contrib.auth", "df_config"]},
            merger.settings,
        )
        merger.post_process()
        self.assertEqual(
            {"INSTALLED_APPS": ["df_config", "django.contrib.auth"]}, merger.settings
        )

    def test_parse(self):
        merger = SettingMerger(
            None,
            [
                DictProvider({"X": 1, "Y": "x{X}"}, name="1"),
                DictProvider({"X": 2}, name="2"),
            ],
        )
        merger.process()
        self.assertEqual({"X": 2, "Y": "x2",}, merger.settings)

    def test_loop(self):
        merger = SettingMerger(
            None, [DictProvider({"X": "{Y}", "Y": "{Z}", "Z": "{X}"}, name="1")],
        )
        self.assertRaises(ValueError, merger.process)

    def test_dynamic_setting(self):
        merger = SettingMerger(
            None,
            [
                DictProvider({"X": 1}, name="d1"),
                DictProvider({"X": RawValue("{Y}")}, name="d2"),
            ],
        )
        merger.process()
        self.assertEqual({"X": "{Y}"}, merger.settings)
        self.assertEqual(
            OrderedDict([("d1", 1), ("d2", RawValue("{Y}"))]), merger.raw_settings["X"]
        )

    def test_complex_settings_ref(self):
        merger = SettingMerger(
            None,
            [
                DictProvider({"X": 1}, name="d1"),
                DictProvider({"Y": SettingReference("X")}, name="d2"),
            ],
        )
        merger.process()
        self.assertEqual({"X": 1, "Y": 1}, merger.settings)

    def test_complex_settings_ref_str(self):
        merger = SettingMerger(
            None,
            [DictProvider({"X": 1}, name="d1"), DictProvider({"Y": "{X}"}, name="d2")],
        )
        merger.process()
        self.assertEqual({"X": 1, "Y": "1"}, merger.settings)

    def test_complex_settings_list(self):
        merger = SettingMerger(
            None,
            [
                DictProvider({"X": 1}, name="d1"),
                DictProvider({"Y": ["{X}"]}, name="d2"),
            ],
        )
        merger.process()
        self.assertEqual({"X": 1, "Y": ["1"]}, merger.settings)

    def test_complex_settings_tuple(self):
        merger = SettingMerger(
            None,
            [
                DictProvider({"X": 1}, name="d1"),
                DictProvider({"Y": ("{X}",)}, name="d2"),
            ],
        )
        merger.process()
        self.assertEqual({"X": 1, "Y": ("1",)}, merger.settings)

    def test_complex_settings_set(self):
        merger = SettingMerger(
            None,
            [
                DictProvider({"X": 1}, name="d1"),
                DictProvider({"Y": {"{X}"}}, name="d2"),
            ],
        )
        merger.process()
        self.assertEqual({"X": 1, "Y": {"1"}}, merger.settings)

    def test_complex_settings_dict(self):
        merger = SettingMerger(
            None,
            [
                DictProvider({"X": 1}, name="d1"),
                DictProvider({"Y": {"{X}": "{X}"}}, name="d2"),
            ],
        )
        merger.process()
        self.assertEqual({"X": 1, "Y": {"1": "1"}}, merger.settings)

    def test_complex_settings_ordereddict(self):
        merger = SettingMerger(
            None,
            [
                DictProvider({"X": 1}, name="d1"),
                DictProvider({"Y": OrderedDict([("{X}", "{X}")])}, name="d2"),
            ],
        )
        merger.process()
        self.assertEqual({"X": 1, "Y": {"1": "1"}}, merger.settings)
        self.assertIsInstance(merger.settings["Y"], OrderedDict)

    def test_complex_settings_defaultdict(self):
        values = defaultdict(lambda: [])
        values["{X}"].append("{X}")
        merger = SettingMerger(
            None,
            [DictProvider({"X": 1}, name="d1"), DictProvider({"Y": values}, name="d2")],
        )
        merger.process()
        self.assertEqual({"X": 1, "Y": {"1": ["1"]}}, merger.settings)
        self.assertIsInstance(merger.settings["Y"], defaultdict)
        merger.settings["Y"]["2"].append(1)
