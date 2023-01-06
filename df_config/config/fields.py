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

"""Convert values from string to Python values
===========================================

Use these classes in your mapping provided in `yourproject.iniconf:INI_MAPPING`.
Check :mod:`df_config.iniconf` for examples.
"""

import os
from typing import Any, Optional, Union

from django.core.checks import Error

from df_config.checks import settings_check_results

MISSING_VALUE = [[]]


def bool_setting(value):
    """return `True` if the provided (lower-cased) text is one of {'1', 'ok', 'yes', 'true', 'on'}"""
    return str(value).lower() in {"1", "ok", "yes", "true", "on"}


def str_or_none(text):
    """return `None` if the text is empty, else returns the text"""
    return text or None


def str_or_blank(value):
    """return '' if the provided value is `None`, else return value"""
    return "" if value is None else str(value)


def guess_relative_path(value):
    """Replace an absolute path by its relative path if the abspath begins by the current dir"""
    if not value:
        return ""
    value = os.path.abspath(value)
    cwd = os.getcwd()
    if value.startswith(cwd):
        return ".%s" % (value[len(cwd) :])
    return value


def strip_split(value):
    """Split the value on "," and strip spaces of the result. Remove empty values.

    >>> strip_split('keyword1, keyword2 ,,keyword3')
    ['keyword1', 'keyword2', 'keyword3']

    >>> strip_split('')
    []

    >>> strip_split(None)
    []

    :param value:
    :type value:
    :return: a list of strings
    :rtype: :class:`list`
    """
    if value:
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


class ConfigField:
    """Class that maps an option in a .ini file to a setting.

    :param name: the section and the option in a .ini file (like "database.engine").
        this setting is not retrieved from config field if set to `None`.
    :param setting_name: the name of the setting (like "DATABASE_ENGINE")
    :param from_str: any callable that takes a text value and returns an object. Default to `str_or_none`
    :type from_str: `callable`
    :param to_str: any callable that takes the Python value and that converts it to str. Default to `str`
    :type to_str: `callable`
    :param help_str: any text that can serve has help in documentation.
    :param default: the value that will be used when generating documentation.
        The current setting value is used if equal to `None`.
    :param env_name: name of the environment variable to get the setting value.
        By default, the environment variable name is guessed from the setting name.
        If set to `None`, do not get the value from the environment.
    """

    AUTO = frozenset()

    def __init__(
        self,
        name: Optional[str],
        setting_name: str,
        from_str=str,
        to_str=str_or_blank,
        help_str: str = None,
        default: Any = None,
        env_name: Optional[Union[set, str]] = AUTO,
    ):
        self.name = name
        self.setting_name = setting_name
        self.from_str = from_str
        self.to_str = to_str
        self.__doc__ = help_str
        self.value = default
        self.environ_name = env_name

    def __str__(self):
        return self.name or self.setting_name


class CharConfigField(ConfigField):
    """Accepts str values. If `allow_none`, then `None` replaces any empty value."""

    def __init__(self, name, setting_name, allow_none=True, **kwargs):
        from_str = str_or_none if allow_none else str
        super().__init__(
            name, setting_name, from_str=from_str, to_str=str_or_blank, **kwargs
        )


class IntegerConfigField(ConfigField):
    """Accept integer values. If `allow_none`, then `None` replaces any empty values (other `0` is used)."""

    def __init__(self, name, setting_name, allow_none=True, **kwargs):
        if allow_none:

            def from_str(value: str):
                return int(value) if value else None

        else:

            def from_str(value: str):
                return int(value) if value else 0

        super().__init__(
            name, setting_name, from_str=from_str, to_str=str_or_blank, **kwargs
        )


class FloatConfigField(ConfigField):
    """Accept floating-point values. If `allow_none`, then `None` replaces any empty values (other `0.0` is used)."""

    def __init__(self, name, setting_name, allow_none=True, **kwargs):
        if allow_none:

            def from_str(value):
                return float(value) if value else None

        else:

            def from_str(value):
                return float(value) if value else 0.0

        super().__init__(
            name, setting_name, from_str=from_str, to_str=str_or_blank, **kwargs
        )


class ListConfigField(ConfigField):
    """Convert a string to a list of values, splitted with the :meth:`df_config.config.fields.strip_split` function."""

    def __init__(self, name, setting_name, **kwargs):
        def to_str(value):
            if value:
                return ",".join([str(x) for x in value])
            return ""

        super().__init__(
            name, setting_name, from_str=strip_split, to_str=to_str, **kwargs
        )


class BooleanConfigField(ConfigField):
    """Search for a boolean value in the ini file.
    If this value is empty and `allow_none` is `True`, then the value is `None`.
    Otherwise returns `True` if the provided (lower-cased) text is one of ('1', 'ok', 'yes', 'true', 'on')
    """

    def __init__(self, name, setting_name, allow_none=False, **kwargs):
        if allow_none:

            def from_str(value):
                if not value:
                    return None
                return bool_setting(value)

            def to_str(value):
                if value is None:
                    return ""
                return str(bool(value)).lower()

        else:

            def from_str(value):
                return bool_setting(value)

            def to_str(value):
                return str(bool(value)).lower()

        super().__init__(name, setting_name, from_str=from_str, to_str=to_str, **kwargs)


class ChoiceConfigFile(ConfigField):
    """Only allow a limited set of values in the .ini file.
    The available values must be given as :class:`str`.

    Choices must be a :class:`dict`, mapping .ini (string) values to actual values.

    If an invalid value is provided by the user, then `None` is returned, but an error is displayed
    through the Django check system.
    """

    def __init__(self, name, setting_name, choices, help_str="", **kwargs):
        def from_str(value):
            if value not in choices:
                valid = ", ".join([f'"{x}"' for x in choices])
                settings_check_results.append(
                    Error(
                        f'Invalid value "{value}". Valid choices: {valid}.',
                        obj="configuration",
                    )
                )
            return choices.get(value)

        def to_str(value):
            for k, v in choices.items():
                if v == value:
                    return str(k)
            return ""

        valid_values = ", ".join(['"%s"' % x for x in choices])
        if help_str:
            help_str += f" Valid choices: {valid_values}"
        else:
            help_str = f"Valid choices: {valid_values}"

        super().__init__(
            name,
            setting_name,
            from_str=from_str,
            to_str=to_str,
            help_str=help_str,
            **kwargs,
        )
