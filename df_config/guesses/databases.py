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
import re
from urllib.parse import urlparse, urlencode

from pkg_resources import DistributionNotFound, get_distribution

from df_config.checks import missing_package, settings_check_results

_default_database_engines = {
    "mysql": "django.db.backends.mysql",
    "mariadb": "django.db.backends.mysql",
    "oracle": "django.db.backends.oracle",
    "postgres": "django.db.backends.postgresql",
    "postgresql": "django.db.backends.postgresql",
    "sqlite": "django.db.backends.sqlite3",
    "sqlite3": "django.db.backends.sqlite3",
}


def database_engine(settings_dict):
    """Allow to use aliases for database engines, as well as the default dotted name"""
    engine = _default_database_engines.get(
        settings_dict["DATABASE_ENGINE"].lower(), settings_dict["DATABASE_ENGINE"]
    )
    if engine == "django.db.backends.postgresql":
        try:
            get_distribution("psycopg2-binary")
        except DistributionNotFound:
            try:
                get_distribution("psycopg2")
            except DistributionNotFound:
                settings_check_results.append(
                    missing_package("psycopg2-binary", " to use PostgreSQL database")
                )
    elif engine == "django.db.backends.oracle":
        try:
            get_distribution("cx_Oracle")
        except DistributionNotFound:
            settings_check_results.append(
                missing_package("cx_Oracle", " to use Oracle database")
            )
    elif engine == "django.db.backends.mysql":
        try:
            get_distribution("mysqlclient")
        except DistributionNotFound:
            settings_check_results.append(
                missing_package("mysqlclient", " to use MySQL or MariaDB database")
            )
    return engine


database_engine.required_settings = ["DATABASE_ENGINE"]


def databases(settings_dict):
    """Build a complete DATABASES setting, taking into account the `DATABASE_URL` environment variable if present
     (used on the Heroku platform)."""
    engine = database_engine(settings_dict)
    name = settings_dict["DATABASE_NAME"]
    user = settings_dict["DATABASE_USER"]
    options = settings_dict["DATABASE_OPTIONS"]
    password = settings_dict["DATABASE_PASSWORD"]
    host = settings_dict["DATABASE_HOST"]
    port = settings_dict["DATABASE_PORT"]
    if "DATABASE_URL" in os.environ:  # Used on Heroku environment
        parsed = urlparse(os.environ["DATABASE_URL"])
        engine = database_engine({"DATABASE_ENGINE": parsed.scheme})
        user = parsed.username
        name = parsed.path[1:]
        password = parsed.password
        host = parsed.hostname
        port = parsed.port
    return {
        "default": {
            "ENGINE": engine,
            "NAME": name,
            "USER": user,
            "OPTIONS": options,
            "PASSWORD": password,
            "HOST": host,
            "PORT": port,
        }
    }


databases.required_settings = [
    "DATABASE_ENGINE",
    "DATABASE_NAME",
    "DATABASE_USER",
    "DATABASE_OPTIONS",
    "DATABASE_PASSWORD",
    "DATABASE_HOST",
    "DATABASE_PORT",
]


class RedisSmartSetting:
    """Handle values required for Redis configuration, as well as Heroku's standard environment variables.
    Can be used as :class:`df_config.config.dynamic_settings.CallableSetting`.
    """

    config_values = ["PROTOCOL", "HOST", "PORT", "DB", "PASSWORD"]

    def __init__(
        self, prefix="", env_variable="REDIS_URL", fmt="url", extra_values=None
    ):
        """Build Redis connection parameters from a set of settings:
            %(prefix)sPROTOCOL, %(prefix)sHOST, %(prefix)sPORT, %(prefix)sDB, %(prefix)sPASSWORD.

        :param prefix: prefix of all settings
        :param env_variable: if this environment variable is present, override given settings
        :param fmt: output format:
            "url": redis://:password@host:port/db
            "dict": {"host": "host", "password": "password" or None, "port": port, "db": db}
            "channels": expected by django-channels
        :param extra_values: added to the output format
        """
        self.fmt = fmt
        self.prefix = prefix
        self.env_variable = env_variable
        self.required_settings = [prefix + x for x in self.config_values]
        self.extra_values = extra_values

    def __call__(self, settings_dict):
        values = {x: settings_dict[self.prefix + x] for x in self.config_values}
        values["AUTH"] = ""
        if (
            values["PROTOCOL"] == "redis"
            and self.env_variable
            and self.env_variable in os.environ
        ):
            parsed_redis_url = urlparse(os.environ[self.env_variable])
            values["HOST"] = parsed_redis_url.hostname
            values["PORT"] = parsed_redis_url.port
            values["PASSWORD"] = parsed_redis_url.password
            values["DB"] = "0"
            if re.match(r"^/\d+$", parsed_redis_url.path):
                values["DB"] = parsed_redis_url.path[1:]
        if values["PASSWORD"]:
            values["AUTH"] = ":%s@" % values["PASSWORD"]
        if self.fmt == "url":
            url = "%(PROTOCOL)s://%(AUTH)s%(HOST)s:%(PORT)s/%(DB)s" % values
            if self.extra_values:
                url += "?" + urlencode(self.extra_values)
            return url
        elif self.fmt == "channels":
            config = {
                "address": (
                    values["HOST"] or "localhost",
                    int(values["PORT"] or 6379),
                ),
                "password": values["PASSWORD"] or None,
                "db": int(values["DB"] or 0),
            }
            if self.extra_values:
                config.update(self.extra_values)
            # noinspection PyUnresolvedReferences
            result = {
                "BACKEND": "channels_redis.core.RedisChannelLayer",
                "CONFIG": {"hosts": [config], "capacity": 5000, "expiry": 10,},
            }
            return result
        elif self.fmt == "dict":
            result = {
                "host": values["HOST"] or "localhost",
                "port": int(values["PORT"] or 6379),
                "db": int(values["DB"] or 0),
                "password": values["PASSWORD"] or None,
            }
            if self.extra_values:
                result.update(self.extra_values)
            return result
        raise ValueError("Unknown RedisSmartSetting format '%s'" % self.fmt)

    def __repr__(self):
        p = self.prefix
        if self.prefix.endswith("REDIS_"):
            p = self.prefix[:-6]
        return "%s.%sredis_%s" % (self.__module__, p.lower(), self.fmt)


cache_redis_url = RedisSmartSetting(prefix="CACHE_", fmt="url")
celery_redis_url = RedisSmartSetting(prefix="CELERY_", fmt="url")
session_redis_dict = RedisSmartSetting(
    prefix="SESSION_REDIS_", fmt="dict", extra_values={"prefix": "session"}
)
websocket_redis_dict = RedisSmartSetting(prefix="WEBSOCKET_REDIS_", fmt="dict")
websocket_redis_channels = RedisSmartSetting(prefix="WEBSOCKET_REDIS_", fmt="channels")


# noinspection PyUnresolvedReferences
def cache_setting(settings_dict):
    """Automatically compute cache settings:
      * if debug mode is set, then caching is disabled
      * if django_redis is available, then Redis is used for caching
      * else memory is used

    :param settings_dict:
    :return:
    """
    parsed_url = urlparse(settings_dict["CACHE_URL"])
    if settings_dict["DEBUG"]:
        return {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    elif settings_dict["USE_REDIS_CACHE"] and parsed_url.scheme == "redis":
        return {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": "{CACHE_URL}",
                "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            }
        }
    elif parsed_url.scheme == "memcache":
        location = "%s:%s" % (
            parsed_url.hostname or "localhost",
            parsed_url.port or 11211,
        )
        return {
            "default": {
                "BACKEND": "django.core.cache.backends.memcached.MemcachedCache",
                "LOCATION": location,
            }
        }
    return {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }


cache_setting.required_settings = ["USE_REDIS_CACHE", "DEBUG", "CACHE_URL"]
