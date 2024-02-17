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
"""Merger object, that analyzes all Django settings and merges them."""
import string
import sys
from collections import OrderedDict
from typing import Any

from django.core.management import color_style
from django.core.management.base import OutputWrapper
from django.core.management.color import no_style

from df_config.config.dynamic_settings import DynamicSettting, ExpandIterable
from df_config.config.fields import ConfigField
from df_config.config.fields_providers import PythonConfigFieldsProvider
from df_config.config.values_providers import ConfigProvider


class SettingMerger:
    """Load different settings modules and config files and merge them."""

    def __init__(
        self,
        fields_provider,
        providers,
        stdout=None,
        stderr=None,
        no_color=False,
    ):
        """Initialize the internal objects."""
        self.fields_provider = fields_provider or PythonConfigFieldsProvider(None)
        self.providers = providers or []
        self.__formatter = string.Formatter()
        self.settings = {}
        self.config_values = (
            []
        )  # list of (ConfigValue, provider_name, setting_name, final_value)
        self.raw_settings = OrderedDict()
        # raw_settings[setting_name][str(provider) or None] = raw_value
        self.__working_stack = set()
        self.stdout = OutputWrapper(stdout or sys.stdout)
        self.stderr = OutputWrapper(stderr or sys.stderr)
        if no_color:
            self.style = no_style()
        else:
            self.style = color_style()
            self.stderr.style_func = self.style.ERROR

    def add_provider(self, provider):
        """Add a new setting provider to the list."""
        self.providers.append(provider)

    def process(self):
        """Load all settings from the different providers and merge them."""
        self.load_raw_settings()
        self.load_settings()

    def load_raw_settings(self):
        """Load all raw settings, without analyzing them (just fetch their names)."""
        # get all setting names and sort them
        all_settings_names_set = set()
        for field in self.fields_provider.get_config_fields():
            assert isinstance(field, ConfigField)
            all_settings_names_set.add(field.setting_name)
        for provider in self.providers:
            assert isinstance(provider, ConfigProvider)
            for setting_name, value in provider.get_extra_settings():
                all_settings_names_set.add(setting_name)
        all_settings_names = list(sorted(all_settings_names_set))
        # initialize all defined settings
        for setting_name in all_settings_names:
            self.raw_settings[setting_name] = OrderedDict()
        # fetch default values if its exists (useless?)
        for field in self.fields_provider.get_config_fields():
            assert isinstance(field, ConfigField)
            self.raw_settings[field.setting_name][None] = field.value
        # read all providers (in the right order)
        for provider in self.providers:
            assert isinstance(provider, ConfigProvider)
            source_name = str(provider)
            for field in self.fields_provider.get_config_fields():
                assert isinstance(field, ConfigField)
                if provider.has_value(field):
                    value = provider.get_value(field)
                    # noinspection PyTypeChecker
                    self.raw_settings[field.setting_name][source_name] = value
            for setting_name, value in provider.get_extra_settings():
                self.raw_settings[setting_name][source_name] = value

    def has_setting_value(self, setting_name):
        """Return True if the setting exists."""
        return setting_name in self.raw_settings

    def get_setting_value(self, setting_name):
        """Return the value of the required setting, analyzing it when required."""
        if setting_name in self.settings:
            return self.settings[setting_name]
        elif setting_name in self.__working_stack:
            raise ValueError(
                "Invalid cyclic dependency between " + ", ".join(self.__working_stack)
            )
        elif setting_name not in self.raw_settings:
            raise ValueError("Invalid setting reference: %s" % setting_name)
        self.__working_stack.add(setting_name)
        provider_name, raw_value = None, None
        for provider_name, raw_value in self.raw_settings[setting_name].items():
            pass
        value = self.analyze_raw_value(raw_value, provider_name, setting_name)
        self.settings[setting_name] = value
        self.__working_stack.remove(setting_name)
        return value

    def load_settings(self):
        """Load and analyze all existing settings."""
        for setting_name in self.raw_settings:
            self.get_setting_value(setting_name)

    def call_method_on_config_values(self, method_name: str):
        """Scan all settings, looking for :class:`df_config.config.dynamic_settings.DynamicSetting`.

        :param method_name: 'pre_collectstatic', 'pre_migrate', 'post_collectstatic', or 'post_migrate'.
        """
        for raw_value, provider_name, setting_name, final_value in self.config_values:
            try:
                getattr(raw_value, method_name)(
                    self, provider_name, setting_name, final_value
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        'Invalid value "%s" in %s for %s (%s)'
                        % (raw_value, provider_name or "built-in", setting_name, e)
                    )
                )

    def analyze_raw_value(self, obj: Any, provider_name: str, setting_name: str) -> Any:
        """Parse the object for replacing variables by their values.

        If `obj` is a string like "THIS_IS_{TEXT}", search for a setting named "TEXT" and replace {TEXT} by its value
        (say, "VALUE"). The returned object is then equal to "THIS_IS_VALUE".
        If `obj` is a list, a set, a tuple or a dict, its components are recursively parsed.
        If `obj` is a subclass of :class:`df_config.config.dynamic_settings.DynamicSetting`, its value is on-the-fly computed.
        Otherwise, `obj` is returned as-is.

        :param obj: object to analyze
        :param provider_name: the name of the config file
        :param setting_name: the name of the setting containing this value
            but this value can be inside a dict or a list (like `SETTING = [Directory("/tmp"), ]`)
        :return: the parsed setting
        """
        if hasattr(obj, "_wrapped"):
            # this is a Django LazyObject
            return obj
        elif isinstance(obj, str):
            values = {}
            for (
                literal_text,
                field_name,
                format_spec,
                conversion,
            ) in self.__formatter.parse(obj):
                if field_name is not None:
                    values[field_name] = self.get_setting_value(field_name)
            return self.__formatter.format(obj, **values)
        elif isinstance(obj, DynamicSettting):
            final_value = obj.get_value(self, provider_name, setting_name)
            self.config_values.append((obj, provider_name, setting_name, final_value))
            return final_value
        elif isinstance(obj, list) or isinstance(obj, tuple):
            result = []
            for sub_obj in obj:
                if isinstance(sub_obj, ExpandIterable):
                    result += self.get_setting_value(sub_obj.value)
                else:
                    result.append(
                        self.analyze_raw_value(sub_obj, provider_name, setting_name)
                    )
            if isinstance(obj, tuple):
                return tuple(result)
            return result
        elif isinstance(obj, set):
            result = set()
            for sub_obj in obj:
                if isinstance(sub_obj, ExpandIterable):
                    result |= self.get_setting_value(sub_obj.value)
                else:
                    result.add(
                        self.analyze_raw_value(sub_obj, provider_name, setting_name)
                    )
            return result
        elif isinstance(obj, dict):
            result = {}  # OrderedDict or plain dict
            for sub_key, sub_obj in obj.items():
                if isinstance(sub_obj, ExpandIterable):
                    result.update(self.get_setting_value(sub_obj.value))
                else:
                    value = self.analyze_raw_value(sub_obj, provider_name, setting_name)
                    key = self.analyze_raw_value(sub_key, provider_name, setting_name)
                    result[key] = value
            # to work with OrderedDict and defaultdict, we need to use the provided object and not a new one
            to_remove = [key for key in obj if key not in result]
            for key in to_remove:
                del obj[key]
            obj.update(result)
            return obj
        return obj

    def post_process(self):
        """Perform some cleaning on settings.

        * remove duplicates in `INSTALLED_APPS` (keeps only the first occurrence)
        """
        # remove duplicates in INSTALLED_APPS
        key = "INSTALLED_APPS"
        if key in self.settings:
            self.settings[key] = list(OrderedDict.fromkeys(self.settings[key]))

    def write_provider(self, provider, include_doc=False):
        """Write settings to the given provider."""
        config_fields = self.fields_provider.get_config_fields()
        for config_field in sorted(config_fields, key=lambda x: str(x.name)):
            assert isinstance(config_field, ConfigField)
            if config_field.setting_name not in self.settings:
                continue
            config_field.value = self.unwrap_object(
                self.settings[config_field.setting_name]
            )
            provider.set_value(config_field, include_doc=include_doc)

    @staticmethod
    def unwrap_object(value):
        """Return the underlying objects in LazyObjects."""
        if hasattr(value, "_wrapped"):
            # this is a Django LazyObject
            str(value)  # force the call of the _setup method
            value = getattr(value, "_wrapped")
        return value
