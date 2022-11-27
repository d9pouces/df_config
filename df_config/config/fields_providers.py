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
from importlib import import_module
from typing import Any, List, Optional, Tuple

from df_config.config.fields import ConfigField


def import_attribute(value: str, default=None) -> Tuple[Optional[Any], bool]:
    if value is None:
        return default, False
    module_name, sep, attribute_name = value.partition(":")
    try:
        module = import_module(module_name, package=None)
        return getattr(module, attribute_name), True
    except AttributeError:
        return default, False
    except ImportError:
        return default, False


class ConfigFieldsProvider:
    """Provides a list of :class:`df_config.config.fields.ConfigField`.
    Used for retrieving settings from a config file.
    """

    name = None

    def get_config_fields(self) -> List[ConfigField]:
        """Return a list of config fields to search in values providers"""
        raise NotImplementedError

    def is_valid(self) -> bool:
        """return True if the provider is working"""
        raise NotImplementedError


class PythonConfigFieldsProvider(ConfigFieldsProvider):
    """Provide a list of :class:`df_config.config.fields.ConfigField` from an attribute in a Python module."""

    name = "Python attribute"

    def __init__(self, value=None, fallback=None):
        self.attribute_name = value or "df_config.iniconf:EMPTY_INI_MAPPING"
        self.mapping, self.valid = import_attribute(self.attribute_name, [])
        if not self.valid and fallback:
            self.attribute_name = fallback
            self.mapping, self.valid = import_attribute(self.attribute_name, [])

    def is_valid(self) -> bool:
        return self.valid

    def get_config_fields(self):
        """Return the list that is defined in the module by the attribute name"""
        return self.mapping

    def __str__(self):
        return self.attribute_name
