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
from unittest import TestCase

from df_config.config.fields_providers import PythonConfigFieldsProvider


class TestPythonConfigFieldsProvider(TestCase):
    def test_python_config_fields_provider_valid(self):
        provider = PythonConfigFieldsProvider(
            "test_df_config.data.sample_iniconf:MAPPING"
        )
        self.assertTrue(provider.is_valid())
        self.assertEqual(2, len(provider.get_config_fields()))

    def test_python_config_fields_provider_invalid(self):
        provider = PythonConfigFieldsProvider(
            "test_df_config.data.sample_iniconf2:MAPPING"
        )
        self.assertFalse(provider.is_valid())
        self.assertEqual([], provider.get_config_fields())
