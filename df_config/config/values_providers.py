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
import hashlib
import importlib.util
import os
import shlex
from collections import OrderedDict
from configparser import ConfigParser
from importlib import import_module
from io import StringIO
from typing import Any, Iterable, Tuple

from df_config.config.fields import ConfigField
from df_config.config.fields_providers import import_attribute


class ConfigProvider:
    """Base class of config provider."""

    name = None

    def has_value(self, config_field: ConfigField) -> bool:
        """Return True if a config_field is present in the file"""
        raise NotImplementedError

    def set_value(self, config_field: ConfigField, include_doc=False):
        """Get the value of the config_field and set its internal value"""
        raise NotImplementedError

    def get_value(self, config_field: ConfigField):
        """Get the internal value if the config field is present in its internal values.
        Otherwise returns the current value of the config field.
        """
        raise NotImplementedError

    def get_extra_settings(self) -> Iterable[Tuple[str, Any]]:
        """Return all settings internally defined.

        :return: an iterable of (setting_name, value).
        """
        raise NotImplementedError

    def is_valid(self) -> bool:
        """Return `True` if the provider is valid (for example, the corresponding file is missing)."""
        raise NotImplementedError

    def to_str(self) -> str:
        """Convert all its internal values to a string"""
        raise NotImplementedError


class EnvironmentConfigProvider(ConfigProvider):
    name = "Environment"

    def __init__(self, prefix, mapping: str = None):

        self.prefix = prefix
        self.exports = ""
        self.exported_values = set()

    def __str__(self):
        count = len(self.exported_values)
        if count <= 1:
            return f"Shell environment ({count} variable)"
        return f"Shell environment ({count} variables)"

    def has_value(self, config_field: ConfigField):
        key = self.get_key(config_field)
        if key is None:
            return False
        return key in os.environ

    def get_key(self, config_field):
        if config_field.environ_name is config_field.AUTO:
            key = f"{self.prefix}{config_field.setting_name}"
        else:
            key = config_field.environ_name
        return key

    def set_value(self, config_field, include_doc=False):
        key = self.get_key(config_field)
        if key is None:
            return
        value = config_field.to_str(config_field.value)
        self.exports += "%s=%s\n" % (shlex.quote(key), shlex.quote(value))

    def get_value(self, config_field):
        key = self.get_key(config_field)
        if key in os.environ:
            self.exported_values.add(key)
            return config_field.from_str(os.environ[key])
        return config_field.value

    def get_extra_settings(self):
        return []

    def is_valid(self):
        return True

    def to_str(self):
        return self.exports


class IniConfigProvider(ConfigProvider):
    """Read a config file using the .ini syntax."""

    name = ".ini file"

    def __init__(self, config_file=None):
        self.parser = ConfigParser()
        self.config_file = config_file
        if config_file:
            self.parser.read([config_file])

    def __str__(self):
        return self.config_file

    @staticmethod
    def __get_info(config_field: ConfigField):
        if config_field.name is None:
            return None, None
        section, sep, option = config_field.name.partition(".")
        return section, option

    def set_value(self, config_field: ConfigField, include_doc: bool = False):
        """update the internal config file"""
        section, option = self.__get_info(config_field)
        if section is None:
            return
        if not self.parser.has_section(section):
            self.parser.add_section(section)
        to_str = config_field.to_str(config_field.value)
        if include_doc and config_field.__doc__:
            for line in config_field.__doc__.splitlines():
                to_str += " \n# %s" % line
        self.parser.set(section, option, to_str)

    def get_value(self, config_field: ConfigField):
        """get option from the config file"""
        section, option = self.__get_info(config_field)
        if section is None:
            return None
        if self.parser.has_option(section=section, option=option):
            str_value = self.parser.get(section=section, option=option)
            return config_field.from_str(str_value)
        return config_field.value

    def has_value(self, config_field: ConfigField):
        """return `True` if the option is defined in the config file"""
        section, option = self.__get_info(config_field)
        if section is None:
            return False
        return self.parser.has_option(section=section, option=option)

    def get_extra_settings(self):
        """No extra setting can be defined in a config file"""
        return []

    def is_valid(self):
        """Return `True` if the config file exists"""
        return os.path.isfile(self.config_file)

    def to_str(self):
        """Display the config file"""
        fd = StringIO()
        self.parser.write(fd)
        return fd.getvalue()


class PythonModuleProvider(ConfigProvider):
    """Load a Python module from its dotted name"""

    name = "Python module"

    def __init__(self, module_name=None):
        self.module_name = module_name
        self.module = None
        self.values = OrderedDict()
        if module_name is not None:
            try:
                self.module = import_module(module_name, package=None)
            except AttributeError:
                pass
            except ImportError:
                pass

    def __str__(self):
        return self.module_name

    def set_value(self, config_field, include_doc=False):
        """Set the value of the config field in an internal dict"""
        self.values[config_field.setting_name] = config_field.value

    def get_value(self, config_field):
        """Get the value of a variable defined in the Python module."""
        if self.module is None or not hasattr(self.module, config_field.setting_name):
            return config_field.value
        return getattr(self.module, config_field.setting_name)

    def has_value(self, config_field):
        """Return `True` if the corresponding variable is defined in the module"""
        return self.module is not None and hasattr(
            self.module, config_field.setting_name
        )

    def get_extra_settings(self):
        """Return all values that look like a Django setting (i.e. uppercase variables)"""
        if self.module is not None:
            for key, value in sorted(self.module.__dict__.items()):
                if key.upper() != key or key == "_":
                    continue
                yield key, value

    def is_valid(self):
        """Return `True` if the module can be imported"""
        return bool(self.module)

    def to_str(self):
        """Display values as if set in a Python module"""
        fd = StringIO()
        for k, v in sorted(self.values.items()):
            fd.write("%s = %r\n" % (k, v))
        return fd.getvalue()


class PythonFileProvider(PythonModuleProvider):
    """Load a Python module from its absolute path"""

    name = "Python file"

    def __init__(self, module_filename):
        self.module_filename = module_filename
        super().__init__()
        if not os.path.isfile(module_filename):
            return
        md5 = hashlib.md5(module_filename.encode("utf-8")).hexdigest()  # nosec  # nosec
        module_name = "df_config.__private" + md5
        spec = importlib.util.spec_from_file_location(module_name, module_filename)
        module_ = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module_)
        self.module = module_

    def __str__(self):
        return self.module_filename


class DictProvider(ConfigProvider):
    """Use a plain Python dict as a setting provider"""

    name = "dict"

    def __init__(self, values, name="default values"):
        self.name = name
        self.values = values

    def get_extra_settings(self):
        """Return all uppercase keys of the internal dict as valid filenames"""
        for k, v in self.values.items():
            if k == k.upper():
                yield k, v

    def set_value(self, config_field, include_doc=False):
        """modify the internal dict for storing the value"""
        self.values[config_field.setting_name] = config_field.value

    def get_value(self, config_field):
        """get a value from the internal dict if present"""
        return self.values.get(config_field.setting_name, config_field.value)

    def has_value(self, config_field):
        """check if the value is present in the internal dict"""
        return config_field.setting_name in self.values

    def __str__(self):
        return self.name

    def is_valid(self):
        """Return always `True`"""
        return True

    def to_str(self):
        """Display the internal dict"""
        return "%r" % dict(self.values)
