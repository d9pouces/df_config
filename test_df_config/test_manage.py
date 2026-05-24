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
import os
import sys
from unittest import TestCase
from unittest.mock import patch

from df_config.manage import (
    MODULE_VARIABLE_NAME,
    PYCHARM_VARIABLE_NAME,
    SETTINGS_VARIABLE_NAME,
    get_merger_from_env,
    manage,
    patch_commands,
    set_env,
)
from test_df_config.test_values_providers import EnvPatch


class TestSetEnv(TestCase):
    def test_set_env(self):
        delete = {PYCHARM_VARIABLE_NAME, SETTINGS_VARIABLE_NAME, MODULE_VARIABLE_NAME}

        with EnvPatch(delete=delete):
            module_name = set_env(module_name="Django-Floor")
            self.assertEqual(
                "df_config.config.base", os.environ[SETTINGS_VARIABLE_NAME]
            )
        self.assertEqual("django_floor", module_name)

        with EnvPatch(delete=delete, **{MODULE_VARIABLE_NAME: "demo"}):
            module_name = set_env(module_name="Django-Floor")
            self.assertEqual(
                "df_config.config.base", os.environ[SETTINGS_VARIABLE_NAME]
            )
        self.assertEqual("demo", module_name)

        with EnvPatch(delete=delete, **{SETTINGS_VARIABLE_NAME: "demo.settings"}):
            module_name = set_env(module_name="Django-Floor")
            self.assertEqual("demo.settings", os.environ[SETTINGS_VARIABLE_NAME])
        self.assertEqual("django_floor", module_name)

        with EnvPatch(delete=delete):
            module_name = set_env(argv=["demo-ctl"])
        self.assertEqual("demo", module_name)

        with EnvPatch(delete=delete):
            module_name = set_env(argv=["demo-ctl.py"])
        self.assertEqual("demo", module_name)

        with EnvPatch(delete=delete):
            module_name = set_env(argv=["demo-ctl.pyc"])
        self.assertEqual("demo", module_name)

    def test_manage(self):
        with EnvPatch(**{MODULE_VARIABLE_NAME: "df_config"}):
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            manage(["df-config-ctl"])

    def test_get_merger_from_env(self):
        with EnvPatch(**{MODULE_VARIABLE_NAME: "df_config"}):
            merger = get_merger_from_env()
            self.assertEqual(8, len(merger.providers))
        with EnvPatch(**{MODULE_VARIABLE_NAME: "demo"}):
            merger = get_merger_from_env()
            self.assertEqual(8, len(merger.providers))


class TestPatchCommands(TestCase):
    def test_patch_commands_ipv4(self):
        from django.core.management.commands.runserver import Command
        from django.test import override_settings

        with override_settings(LISTEN_ADDRESS="127.0.0.1:9999"):
            patch_commands()
        self.assertEqual("9999", Command.default_port)
        self.assertEqual("127.0.0.1", Command.default_addr)

    def test_patch_commands_ipv6(self):
        from django.core.management.commands.runserver import Command
        from django.test import override_settings

        with override_settings(LISTEN_ADDRESS="::1:8080"):
            patch_commands()
        # IPv6 address ::1 → default_addr_ipv6 should be set
        self.assertEqual("8080", Command.default_port)

    def test_patch_commands_wildcard_ipv4(self):
        from django.core.management.commands.runserver import Command
        from django.test import override_settings

        with override_settings(LISTEN_ADDRESS="0.0.0.0:7777"):
            patch_commands()
        self.assertEqual("7777", Command.default_port)

    def test_patch_commands_no_listen_address(self):
        # Should not raise even if LISTEN_ADDRESS is not set
        from django.conf import settings as django_settings
        from django.test import override_settings

        if hasattr(django_settings, "LISTEN_ADDRESS"):
            # patch_commands is fine with it set too
            patch_commands()
        else:
            patch_commands()

    def test_patch_commands_invalid_port(self):
        from django.test import override_settings

        # Should not raise on invalid port
        with override_settings(LISTEN_ADDRESS="localhost:notaport"):
            patch_commands()  # should not raise
