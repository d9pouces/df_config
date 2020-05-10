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
from unittest import TestCase

from df_config.manage import (
    MODULE_VARIABLE_NAME,
    PYCHARM_VARIABLE_NAME,
    SETTINGS_VARIABLE_NAME,
    get_merger_from_env,
    manage,
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
            manage(["df-config-ctl"])

    def test_get_merger_from_env(self):
        with EnvPatch(**{MODULE_VARIABLE_NAME: "df_config"}):
            merger = get_merger_from_env()
            self.assertEqual(8, len(merger.providers))
        with EnvPatch(**{MODULE_VARIABLE_NAME: "demo"}):
            merger = get_merger_from_env()
            self.assertEqual(8, len(merger.providers))
