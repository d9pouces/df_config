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
import io
from collections import OrderedDict, defaultdict
from unittest import TestCase
from unittest.mock import MagicMock

from django.utils.functional import SimpleLazyObject

from df_config.config.dynamic_settings import ExpandIterable, RawValue, SettingReference
from df_config.config.fields import ConfigField
from df_config.config.fields_providers import ConfigFieldsProvider
from df_config.config.merger import SettingMerger
from df_config.config.values_providers import DictProvider, PythonModuleProvider

# ---------------------------------------------------------------------------
# Helper objects
# ---------------------------------------------------------------------------


class MyObject:
    instantiated = False

    def __init__(self, content: str):
        self.content = content
        MyObject.instantiated = True

    def __str__(self) -> str:
        return self.content


class SimpleFieldsProvider(ConfigFieldsProvider):
    """Minimal fields provider for tests."""

    def __init__(self, fields):
        self._fields = fields

    def get_config_fields(self):
        return self._fields

    def is_valid(self):
        return True


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

    def test_lazy_object(self):
        obj = SimpleLazyObject(lambda: MyObject("test"))
        self.assertTrue(hasattr(obj, "_wrapped"))
        self.assertFalse(MyObject.instantiated)
        merger = SettingMerger(
            None,
            [DictProvider({"X": obj}, name="d1")],
        )
        merger.process()
        merger.post_process()
        obj_2 = merger.settings["X"]
        self.assertTrue(hasattr(obj_2, "_wrapped"))
        self.assertFalse(MyObject.instantiated)
        content = obj.content
        self.assertTrue(MyObject.instantiated)
        self.assertEqual("test", content)

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
        self.assertEqual(
            {
                "X": 2,
                "Y": "x2",
            },
            merger.settings,
        )

    def test_loop(self):
        merger = SettingMerger(
            None,
            [DictProvider({"X": "{Y}", "Y": "{Z}", "Z": "{X}"}, name="1")],
        )
        self.assertRaises(ValueError, merger.process)

    def test_dynamic_setting(self):
        stderr = io.StringIO()
        stdout = io.StringIO()
        merger = SettingMerger(
            None,
            [
                DictProvider({"X": 1}, name="d1"),
                DictProvider({"X": RawValue("{Y}")}, name="d2"),
            ],
            stderr=stderr,
            stdout=stdout,
        )
        merger.process()
        self.assertEqual({"X": "{Y}"}, merger.settings)
        self.assertEqual(
            OrderedDict([("d1", 1), ("d2", RawValue("{Y}"))]), merger.raw_settings["X"]
        )
        self.assertEqual("", stderr.getvalue())
        self.assertEqual("", stdout.getvalue())

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


# ---------------------------------------------------------------------------
# TestSettingMergerExtended
# ---------------------------------------------------------------------------


class TestSettingMergerExtended(TestCase):
    """Cover lines 57, 64, 76-77, 88-89, 95-99, 105, 116, 136-142, 186, 198, 208, 233-241, 246-252."""

    # ------------------------------------------------------------------
    # no_color=True branch (line 57)
    # ------------------------------------------------------------------
    def test_no_color_init(self):
        """SettingMerger with no_color=True uses no_style()."""
        merger = SettingMerger(None, [], no_color=True)
        self.assertIsNotNone(merger.style)

    # ------------------------------------------------------------------
    # add_provider (line 64)
    # ------------------------------------------------------------------
    def test_add_provider(self):
        merger = SettingMerger(None, [])
        provider = DictProvider({"X": 1}, name="extra")
        merger.add_provider(provider)
        self.assertEqual(1, len(merger.providers))

    # ------------------------------------------------------------------
    # load_raw_settings with a real fields_provider (lines 76-77, 88-89, 95-99)
    # ------------------------------------------------------------------
    def test_load_raw_settings_with_fields_provider(self):
        """load_raw_settings picks up values from a real fields_provider."""
        from df_config.config.values_providers import ConfigProvider

        field = ConfigField("section.key", "MY_SETTING", default="default_val")
        fields_provider = SimpleFieldsProvider([field])

        class MockProvider(ConfigProvider):
            name = "mock"

            def has_value(self, config_field):
                return config_field.setting_name == "MY_SETTING"

            def get_value(self, config_field):
                return "overridden"

            def get_extra_settings(self):
                return [("EXTRA_SETTING", 99)]

            def is_valid(self):
                return True

            def set_value(self, config_field, include_doc=False):
                pass

            def to_str(self):
                return ""

            def __str__(self):
                return self.name

        merger = SettingMerger(fields_provider, [MockProvider()])
        merger.load_raw_settings()
        self.assertIn("MY_SETTING", merger.raw_settings)
        self.assertIn("EXTRA_SETTING", merger.raw_settings)
        # The fields_provider default is stored under None
        self.assertEqual("default_val", merger.raw_settings["MY_SETTING"][None])
        # The provider's override is stored under "mock"
        self.assertEqual("overridden", merger.raw_settings["MY_SETTING"]["mock"])

    # ------------------------------------------------------------------
    # has_setting_value (line 105)
    # ------------------------------------------------------------------
    def test_has_setting_value(self):
        merger = SettingMerger(None, [DictProvider({"X": 1}, name="d")])
        merger.process()
        self.assertTrue(merger.has_setting_value("X"))
        self.assertFalse(merger.has_setting_value("Y"))

    # ------------------------------------------------------------------
    # get_setting_value with unknown setting (line 116)
    # ------------------------------------------------------------------
    def test_get_setting_value_unknown_raises(self):
        merger = SettingMerger(None, [DictProvider({"X": 1}, name="d")])
        merger.process()
        with self.assertRaises(ValueError) as ctx:
            merger.get_setting_value("DOES_NOT_EXIST")
        self.assertIn("DOES_NOT_EXIST", str(ctx.exception))

    # ------------------------------------------------------------------
    # call_method_on_config_values (lines 136-142)
    # ------------------------------------------------------------------
    def test_call_method_on_config_values_normal(self):
        """call_method_on_config_values calls the method on each DynamicSetting."""
        merger = SettingMerger(
            None,
            [DictProvider({"X": RawValue("hello")}, name="d")],
        )
        merger.process()
        # Should not raise; RawValue.pre_migrate is a no-op
        merger.call_method_on_config_values("pre_migrate")

    def test_call_method_on_config_values_exception_caught(self):
        """Exceptions in call_method_on_config_values are caught and logged."""
        stdout = io.StringIO()
        merger = SettingMerger(
            None,
            [DictProvider({"X": RawValue("hello")}, name="d")],
            stdout=stdout,
        )
        merger.process()
        # Inject a broken entry into config_values
        broken = MagicMock()
        broken.pre_migrate = MagicMock(side_effect=ValueError("boom"))
        merger.config_values.append((broken, "d", "X", "hello"))
        merger.call_method_on_config_values("pre_migrate")
        self.assertIn("Invalid value", stdout.getvalue())

    # ------------------------------------------------------------------
    # ExpandIterable in list (line 186)
    # ------------------------------------------------------------------
    def test_expand_iterable_in_list(self):
        merger = SettingMerger(
            None,
            [
                DictProvider({"BASE": [1, 2]}, name="d1"),
                DictProvider({"RESULT": [0, ExpandIterable("BASE"), 3]}, name="d2"),
            ],
        )
        merger.process()
        self.assertEqual({"BASE": [1, 2], "RESULT": [0, 1, 2, 3]}, merger.settings)

    # ------------------------------------------------------------------
    # ExpandIterable in set (line 198)
    # ------------------------------------------------------------------
    def test_expand_iterable_in_set(self):
        """ExpandIterable inside a set merges the referenced set into the result."""
        merger = SettingMerger(
            None,
            [DictProvider({"BASE": {10, 20}}, name="d1")],
        )
        merger.process()

        # ExpandIterable is not hashable so we can't use a literal set;
        # create a fake set subclass whose __iter__ yields an ExpandIterable.
        class FakeSet(set):
            def __iter__(self_inner):
                yield 0
                yield ExpandIterable("BASE")

        fake = FakeSet()
        result = merger.analyze_raw_value(fake, "d1", "RESULT")
        self.assertIn(0, result)
        self.assertIn(10, result)
        self.assertIn(20, result)

    # ------------------------------------------------------------------
    # ExpandIterable in dict (line 208)
    # ------------------------------------------------------------------
    def test_expand_iterable_in_dict(self):
        merger = SettingMerger(
            None,
            [
                DictProvider({"BASE": {"a": 1, "b": 2}}, name="d1"),
                DictProvider(
                    {"RESULT": {"c": 3, None: ExpandIterable("BASE")}}, name="d2"
                ),
            ],
        )
        merger.process()
        result = merger.settings["RESULT"]
        self.assertIn("a", result)
        self.assertIn("b", result)
        self.assertIn("c", result)

    # ------------------------------------------------------------------
    # write_provider (lines 233-241)
    # ------------------------------------------------------------------
    def test_write_provider(self):
        """write_provider writes final settings to the given provider."""
        field = ConfigField("section.key", "MY_SETTING", default="initial")
        fields_provider = SimpleFieldsProvider([field])
        merger = SettingMerger(
            fields_provider,
            [DictProvider({"MY_SETTING": "final_value"}, name="d")],
        )
        merger.process()
        target_provider = PythonModuleProvider()
        merger.write_provider(target_provider)
        self.assertEqual("final_value", target_provider.values.get("MY_SETTING"))

    def test_write_provider_skips_missing_settings(self):
        """write_provider skips settings not present in merger.settings."""
        field = ConfigField("section.key", "MY_SETTING", default=None)
        field2 = ConfigField("section.key2", "OTHER_SETTING", default="x")
        fields_provider = SimpleFieldsProvider([field, field2])
        merger = SettingMerger(
            fields_provider,
            [DictProvider({"MY_SETTING": "val"}, name="d")],
        )
        merger.load_raw_settings()
        # Only load MY_SETTING, not OTHER_SETTING
        merger.settings["MY_SETTING"] = "val"
        target_provider = PythonModuleProvider()
        merger.write_provider(target_provider)
        self.assertIn("MY_SETTING", target_provider.values)
        self.assertNotIn("OTHER_SETTING", target_provider.values)

    # ------------------------------------------------------------------
    # unwrap_object (lines 246-252)
    # ------------------------------------------------------------------
    def test_unwrap_object_plain_value(self):
        """unwrap_object returns plain values unchanged."""
        self.assertEqual(42, SettingMerger.unwrap_object(42))
        self.assertEqual("hello", SettingMerger.unwrap_object("hello"))

    def test_unwrap_object_lazy_object(self):
        """unwrap_object unwraps a Django SimpleLazyObject."""
        from django.utils.functional import SimpleLazyObject

        obj = SimpleLazyObject(lambda: "lazy_value")
        result = SettingMerger.unwrap_object(obj)
        self.assertEqual("lazy_value", result)

    def test_unwrap_object_proxy_cast(self):
        """unwrap_object calls _proxy____cast when present."""
        mock = MagicMock()
        mock._proxy____cast = MagicMock(return_value="cast_result")
        # Remove _wrapped so that branch is not taken
        del mock._wrapped
        result = SettingMerger.unwrap_object(mock)
        self.assertEqual("cast_result", result)
        mock._proxy____cast.assert_called_once()
