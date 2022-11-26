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
from urllib.parse import urlencode, urlparse

from django.core.exceptions import ImproperlyConfigured
from django.utils.version import get_complete_version

from df_config.config.url import DatabaseURL
from df_config.utils import is_package_present


def databases(settings_dict):
    """Build a complete DATABASES setting.

    If present, Takes the `DATABASE_URL` environment variable into account
    (used on the Heroku platform).
    """
    default = {
        "ENGINE": DatabaseURL.normalize_engine(settings_dict["DATABASE_ENGINE"]),
        "NAME": settings_dict["DATABASE_NAME"],
        "USER": settings_dict["DATABASE_USER"],
        "OPTIONS": settings_dict["DATABASE_OPTIONS"],
        "PASSWORD": settings_dict["DATABASE_PASSWORD"],
        "HOST": settings_dict["DATABASE_HOST"],
        "PORT": settings_dict["DATABASE_PORT"],
    }
    return {"default": default}


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

    _config_values = ["PROTOCOL", "HOST", "PORT", "DB", "PASSWORD"]

    def __init__(
        self,
        prefix="",
        env_variable="REDIS_URL",
        fmt="url",
        extra_values=None,
        only_redis: bool = True,
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
        self.only_redis = only_redis
        self.config_values = list(self._config_values)
        if not only_redis:
            self.config_values += ["USERNAME"]
        self.required_settings = [prefix + x for x in self.config_values]
        self.extra_values = extra_values

    def __call__(self, settings_dict):
        values = {x: settings_dict[self.prefix + x] for x in self.config_values}
        values.setdefault("USERNAME")
        values["AUTH"] = ""
        if values["PASSWORD"]:
            values["AUTH"] = "%s:%s@" % (values["USERNAME"] or "", values["PASSWORD"])
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
                "CONFIG": {
                    "hosts": [config],
                    "capacity": 5000,
                    "expiry": 10,
                },
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
celery_broker_url = RedisSmartSetting(prefix="CELERY_", fmt="url", only_redis=False)
celery_result_url = RedisSmartSetting(
    prefix="CELERY_RESULT_", fmt="url", only_redis=False
)
session_redis_dict = RedisSmartSetting(
    prefix="SESSION_REDIS_", fmt="dict", extra_values={"prefix": "session"}
)
websocket_redis_dict = RedisSmartSetting(prefix="WEBSOCKET_REDIS_", fmt="dict")
websocket_redis_channels = RedisSmartSetting(prefix="WEBSOCKET_REDIS_", fmt="channels")


def cache_setting(settings_dict):
    """Automatically compute cache settings:
      * if debug mode is set, then caching is disabled
      * if django_redis is available, then Redis is used for caching
      * else memory is used

    :param settings_dict:
    :return:
    """
    parsed_url = urlparse(settings_dict["CACHE_URL"])
    django_version = get_complete_version()
    default = {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
    if settings_dict["DEBUG"]:
        pass
    elif django_version >= (4, 0) and parsed_url.scheme in ("redis", "rediss"):
        # noinspection PyUnresolvedReferences
        default = {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": "{CACHE_URL}",
        }
    elif parsed_url.scheme in ("redis", "rediss"):
        if is_package_present("django_redis"):
            # noinspection PyUnresolvedReferences
            default = {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": "{CACHE_URL}",
                "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            }
    elif parsed_url.scheme == "memcache":
        if django_version >= (3, 2) and is_package_present("pymemcache"):
            backend = "django.core.cache.backends.memcached.PyMemcacheCache"
        elif django_version >= (3, 2) and is_package_present("pylibmc"):
            backend = "django.core.cache.backends.memcached.PyLibMCCache"
        elif is_package_present("memcache"):
            backend = "django.core.cache.backends.memcached.MemcachedCache"
        else:
            raise ImproperlyConfigured(
                "Please install 'pylibmc' package before using memcache engine."
            )
        location = "%s:%s" % (
            parsed_url.hostname or "localhost",
            parsed_url.port or 11211,
        )
        default = {
            "BACKEND": backend,
            "LOCATION": location,
        }
    return {"default": default}


cache_setting.required_settings = ["DEBUG", "CACHE_URL"]
