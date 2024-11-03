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
from pathlib import Path
from typing import Dict, Optional

from django.core.exceptions import ImproperlyConfigured

from df_config.config.url import DatabaseURL
from df_config.guesses.databases import databases
from test_df_config.test_dynamic_settings import TestDynamicSetting


class TestDynamicSettingURL(TestDynamicSetting):
    def test_repr(self):
        database_url = DatabaseURL("DATABASE_URL")
        s = database_url.database("db_name")
        self.assertEqual(f"{database_url!r}", "DatabaseURL('DATABASE_URL')")
        self.assertEqual(
            f"{s!r}", "DatabaseURL('DATABASE_URL').database(default='db_name')"
        )

    def test_url(self):
        values = {"DATABASE_URL": "psql://user:password@localhost:5432/database"}
        self.check_alls(
            values,
            {
                "engine": "django.db.backends.postgresql",
                "hostname": "localhost",
                "netloc": "user:password@localhost:5432",
                "params": "",
                "password": "password",
                "path": "/database",
                "port": "5432",
                "query": "",
                "scheme": "postgres",
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
                "engine": "django.db.backends.postgresql",
                "hostname": "localhost",
                "netloc": "localhost",
                "params": "",
                "password": None,
                "path": "",
                "port": "5432",
                "query": "",
                "scheme": "postgres",
                "username": None,
                "database": None,
                "port_int": 5432,
                "use_tls": False,
                "use_ssl": False,
            },
        )

    def test_url_multiple_values(self):
        values = {"DATABASE_URL": "psql://localhost,psql://localhost:5433"}
        self.check_alls(
            values,
            {
                "engine": "django.db.backends.postgresql",
                "hostname": "localhost,localhost",
                "netloc": "localhost,localhost:5433",
                "params": "",
                "password": None,
                "path": "",
                "port": "5432,5433",
                "query": "",
                "scheme": "postgres",
                "username": None,
                "database": None,
            },
        )

    def test_url_multiple_values_with_dict(self):
        database_url = DatabaseURL(
            "DATABASE_URL", url="psql://localhost,psql://localhost:5433"
        )
        settings_dict = {
            "DATABASE_ENGINE": database_url.engine_(),
            "DATABASE_NAME": database_url.database_(),
            "DATABASE_USER": database_url.username_(),
            "DATABASE_PASSWORD": database_url.password_(),
            "DATABASE_HOST": database_url.hostname_(),
            "DATABASE_PORT": database_url.port_(),
            "DATABASE_OPTIONS": {},
            "USE_PROMETHEUS": False,
            "DATABASE_CONN_MAX_AGE": 0,
        }
        actual = databases(settings_dict)
        expected = {
            "default": {
                "CONN_HEALTH_CHECKS": False,
                "CONN_MAX_AGE": 0,
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "localhost,localhost",
                "NAME": None,
                "OPTIONS": {},
                "PASSWORD": None,
                "PORT": "5432,5433",
                "USER": None,
            }
        }
        self.assertEqual(actual, expected)

    def test_url_multiple_values_with_dict_invalid(self):
        database_url = DatabaseURL(
            "DATABASE_URL",
            url="psql://username:password@localhost/db1,psql://localhost:5433/db2",
        )
        self.assertRaises(ImproperlyConfigured, lambda: database_url.database_())
        self.assertRaises(ImproperlyConfigured, lambda: database_url.username_())
        self.assertRaises(ImproperlyConfigured, lambda: database_url.password_())
        settings_dict = {
            "DATABASE_ENGINE": database_url.engine_(),
            "DATABASE_HOST": database_url.hostname_(),
            "DATABASE_PORT": database_url.port_(),
            "DATABASE_OPTIONS": {},
        }

    def test_default_values(self):
        values = {"DATABASE_URL": None}
        self.check_alls(
            values,
            {
                "engine": None,
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
        setting = DatabaseURL("DATABASE_URL")
        for key, value in attributes.items():
            if (
                key in ("port_int", "use_tls", "use_ssl")
                and setting.parsed_urls
                and len(setting.parsed_urls) > 1
            ):
                self.assertRaises(ValueError, getattr(setting, key)())
            else:
                dynamic_setting = getattr(setting, key)()
                self.check(dynamic_setting, value, previous_settings=values)
