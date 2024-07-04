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
"""Initial environment values and management commands."""
import ipaddress
import logging
import os
import re
import sys
from typing import List

from df_config.config.fields_providers import PythonConfigFieldsProvider
from df_config.config.merger import SettingMerger
from df_config.config.values_providers import (
    DictProvider,
    EnvironmentConfigProvider,
    IniConfigProvider,
    PythonFileProvider,
    PythonModuleProvider,
)

PYCHARM_VARIABLE_NAME = "PYCHARM_DJANGO_MANAGE_MODULE"
SETTINGS_VARIABLE_NAME = "DJANGO_SETTINGS_MODULE"
DEFAULT_SETTINGS_MODULE = "df_config.config.base"
MODULE_VARIABLE_NAME = "DF_CONF_NAME"


def set_env(
    module_name: str = None,
    argv: List[str] = None,
    settings_module=DEFAULT_SETTINGS_MODULE,
):
    """Set the environment variable `DF_CONF_NAME` with the main Python module name.

    The value looks like "project_name".
    If `module_name` is not given, tries to infer it from the running script name

    """
    if MODULE_VARIABLE_NAME not in os.environ:
        script_re = re.compile(r"^([\w_\-.]+)-\w+(?:\.py|\.pyc|)$")
        if not module_name:
            if PYCHARM_VARIABLE_NAME in os.environ:
                pycharm_matcher = script_re.match(os.environ[PYCHARM_VARIABLE_NAME])
                if pycharm_matcher:
                    module_name = pycharm_matcher.group(1)
        if not module_name:
            argv = argv or sys.argv
            if argv and argv[0]:
                script_matcher = script_re.match(os.path.basename(argv[0]))
                if script_matcher:
                    module_name = script_matcher.group(1)
        if not module_name:
            module_name = "df_config"
        os.environ[MODULE_VARIABLE_NAME] = module_name.replace("-", "_").lower()
    os.environ.setdefault(SETTINGS_VARIABLE_NAME, settings_module)
    return os.environ[MODULE_VARIABLE_NAME]


def get_merger_from_env(
    merger_class=SettingMerger, settings_module=DEFAULT_SETTINGS_MODULE
) -> SettingMerger:
    """Return a settingmerger to determien all available settings, should be used after set_env().

    Settings are found in this order:

    * df_config.config.defaults
    * {project_name}.defaults (overrides df_config.config.defaults)
    * {root}/etc/{project_name}/settings.ini (overrides {project_name}.settings)
    * {root}/etc/{project_name}/settings.py (overrides {root}/etc/{project_name}/settings.ini)
    * ./local_settings.ini (overrides {root}/etc/{project_name}/settings.py)
    * ./local_settings.py (overrides ./local_settings.ini)
    * environment variables (overrides ./local_settings.py)
    """
    # required if set_env is not called
    module_name = set_env(settings_module=settings_module)
    prefix = os.path.abspath(sys.prefix)
    if prefix == "/usr":
        prefix = ""
    ini_mapping = f"{module_name}.iniconf:INI_MAPPING"
    config_providers = [
        DictProvider({"DF_MODULE_NAME": module_name}, name="default values"),
        PythonModuleProvider("df_config.config.defaults"),
        PythonModuleProvider("%s.defaults" % module_name),
        IniConfigProvider(
            "%s/etc/%s/settings.ini"
            % (
                prefix,
                module_name,
            )
        ),
        PythonFileProvider(
            "%s/etc/%s/settings.py"
            % (
                prefix,
                module_name,
            )
        ),
        EnvironmentConfigProvider("%s_" % module_name.upper()),
        IniConfigProvider(os.path.abspath("local_settings.ini")),
        PythonFileProvider(os.path.abspath("local_settings.py")),
    ]
    fields_provider = PythonConfigFieldsProvider(
        ini_mapping, fallback="df_config.iniconf:DEFAULT_INI_MAPPING"
    )
    return merger_class(fields_provider, config_providers)


def manage(argv=None, module_name: str = None, settings_module=DEFAULT_SETTINGS_MODULE):
    """Set the environment variable and run the manage command."""
    set_env(module_name=module_name, settings_module=settings_module)
    import django

    django.setup()
    from django.core.management import execute_from_command_line

    patch_commands()
    argv = argv or sys.argv
    logger = logging.getLogger("django.server")
    logger.info("command='%s'", " ".join(argv))
    execute_from_command_line(argv=argv)


def patch_commands():
    """Patch the runserver command to use the configured LISTEN_ADDRESS."""
    from django.conf import settings
    from django.core.management.commands.runserver import Command

    if not hasattr(settings, "LISTEN_ADDRESS"):
        return
    add, sep, port = settings.LISTEN_ADDRESS.rpartition(":")
    if sep == ":":
        try:
            Command.default_port = str(int(port))
            add = ipaddress.ip_address(add)
            if add.version == 4:
                Command.default_addr = str(add)
            else:
                Command.default_addr_ipv6 = str(add)
        except ValueError:
            pass
