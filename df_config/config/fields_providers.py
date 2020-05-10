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
from importlib import import_module
from typing import List

from df_config.config.fields import ConfigField


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
    """Provide a list of :class:`df_config.config.fields.ConfigField` from an attribute in a Python module. """

    name = "Python attribute"

    def __init__(self, value=None):
        if value is None:
            module_name, attribute_name = None, None
        else:
            module_name, sep, attribute_name = value.partition(":")
        self.module_name = module_name
        self.attribute_name = attribute_name
        self.module = None
        if module_name is not None:
            try:
                self.module = import_module(module_name, package=None)
            except ImportError:
                pass

    def is_valid(self) -> bool:
        return self.module is not None

    def get_config_fields(self):
        """Return the list that is defined in the module by the attribute name"""
        if self.module:
            return getattr(self.module, self.attribute_name, [])
        return []

    def __str__(self):
        return "%s:%s" % (self.module_name, self.attribute_name)
