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
from typing import Dict, Optional

from df_config.config.url import URLSetting
from test_df_config.test_dynamic_settings import TestDynamicSetting


class TestDynamicSettingURL(TestDynamicSetting):
    def test_url(self):
        values = {"DATABASE_URL": "psql://user:password@localhost:5432/database"}
        self.check_alls(
            values,
            {
                "hostname": "localhost",
                "netloc": "user:password@localhost:5432",
                "params": "",
                "password": "password",
                "path": "/database",
                "port": 5432,
                "query": "",
                "scheme": "psql",
                "username": "user",
                "database": "database",
                "port_int": 5432,
                "use_tls": False,
                "use_ssl": False,
            },
        )

    def test_url_missing_values(self):
        values = {"DATABASE_URL": "psql://localhost"}
        self.check_alls(
            values,
            {
                "hostname": "localhost",
                "netloc": "localhost",
                "params": "",
                "password": None,
                "path": "",
                "port": None,
                "query": "",
                "scheme": "psql",
                "username": None,
                "database": None,
                "port_int": 5432,
                "use_tls": False,
                "use_ssl": False,
            },
        )

    def test_default_values(self):
        values = {"DATABASE_URL": None}
        self.check_alls(
            values,
            {
                "hostname": "localhost",
                "netloc": "localhost",
                "params": "",
                "password": None,
                "path": "",
                "port": None,
                "query": "",
                "scheme": None,
                "username": None,
                "database": None,
                "port_int": None,
                "use_tls": False,
                "use_ssl": False,
            },
        )

    def check_alls(self, values: Dict[str, Optional[str]], attributes: Dict[str, str]):
        setting = URLSetting("DATABASE_URL")
        for key, value in attributes.items():
            dynamic_setting = getattr(setting, key)()
            self.check(dynamic_setting, value, previous_settings=values)
