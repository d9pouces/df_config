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
"""Settings for database and cache backends."""
from typing import List, Set
from urllib.parse import ParseResult, urlencode, urlparse

from django.core.exceptions import ImproperlyConfigured
from django.utils import version

from df_config import utils
from df_config.config.dynamic_settings import Directory
from df_config.config.url import DatabaseURL

prometheus_engines = {
    "django.db.backends.sqlite3": "django_prometheus.db.backends.sqlite3",
    "django.db.backends.postgresql": "django_prometheus.db.backends.postgresql",
    "django.db.backends.mysql": "django_prometheus.db.backends.mysql",
    "django.core.cache.backends.filebased.FileBasedCache": "django_prometheus.cache.backends.filebased.FileBasedCache",
    "django.core.cache.backends.locmem.LocMemCache": "django_prometheus.cache.backends.locmem.LocMemCache",
    "django.core.cache.backends.memcached.PyLibMCCache": "django_prometheus.cache.backends.memcached.PyLibMCCache",
    "django.core.cache.backends.memcached.PyMemcacheCache": "django_prometheus.cache.backends.memcached.PyMemcacheCache",
    "django.core.cache.backends.redis.RedisCache": "django_prometheus.cache.backends.redis.RedisCache",
}


def databases(settings_dict):
    """Build a complete DATABASES setting for the default database.

    When django-prometheus is used, the engine is replaced by the matching prometheus engine.
    """
    engine = DatabaseURL.normalize_engine(settings_dict["DATABASE_ENGINE"])
    if settings_dict["USE_PROMETHEUS"]:
        engine = prometheus_engines.get(engine, engine)
    hosts, ports = None, None
    host = settings_dict["DATABASE_HOST"]
    if isinstance(host, str):
        hosts = host.split(",")
    port = settings_dict["DATABASE_PORT"]
    if isinstance(port, int):
        port = str(port)
    if isinstance(port, str):
        ports = port.split(",")
    if hosts and ports and len(ports) != len(hosts):
        raise ImproperlyConfigured(
            "DATABASE_HOST and DATABASE_PORT must have the same number of elements."
        )
    default = {
        "ENGINE": engine,
        "NAME": settings_dict["DATABASE_NAME"],
        "USER": settings_dict["DATABASE_USER"],
        "OPTIONS": settings_dict["DATABASE_OPTIONS"],
        "PASSWORD": settings_dict["DATABASE_PASSWORD"],
        "HOST": host,
        "PORT": port,
        "CONN_MAX_AGE": settings_dict["DATABASE_CONN_MAX_AGE"],
        "CONN_HEALTH_CHECKS": bool(settings_dict["DATABASE_CONN_MAX_AGE"]),
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
    "DATABASE_CONN_MAX_AGE",
    "USE_PROMETHEUS",
]


class RedisSmartSetting:
    """Handle values required for Redis configuration, as well as Heroku's standard environment variables.

    Can be used as :class:`df_config.config.dynamic_settings.CallableSetting`.
    """

    _config_values = ["PROTOCOL", "HOST", "PORT", "DB", "PASSWORD", "USERNAME"]

    def __init__(
        self,
        prefix="",
        env_variable="REDIS_URL",
        fmt="url",
        extra_values=None,
        only_redis: bool = True,
    ):
        """Build Redis connection parameters from a set of settings.

        These settings are:
        - "{prefix}PROTOCOL",
        - "{prefix}HOST",
        - "{prefix}PORT",
        - "{prefix}DB",
        - "{prefix}USERNAME",
        - "{prefix}PASSWORD".

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
        self.required_settings = [prefix + x for x in self.config_values]
        self.extra_values = extra_values

    def __call__(self, settings_dict):
        """Return the redis setting."""
        values = {x: settings_dict[self.prefix + x] for x in self.config_values}
        values["AUTH"] = ""
        if values["PASSWORD"]:
            values["AUTH"] = "%s:%s@" % (values["USERNAME"] or "", values["PASSWORD"])
        if self.fmt == "url":
            url = "%(PROTOCOL)s://%(AUTH)s%(HOST)s:%(PORT)s/%(DB)s" % values
            if self.extra_values:
                url += "?" + urlencode(self.extra_values)
            return url
        elif self.fmt == "channels":
            url = "%(PROTOCOL)s://%(AUTH)s%(HOST)s:%(PORT)s/%(DB)s" % values
            config = {
                "address": url,
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
        """Return a representation of the redis setting."""
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
    """Automatically compute cache settings.

    Four caches are defined:

      * `base` that uses the CACHE_URL setting with redis, rediss or memcache protocols as soon as possible,
      * `locmem`: always uses the local memory, hence destroyed when the process is killed,
      * `cached`: "locmem" when DEBUG is true, `base` else,
      * `default`: "dummy" when DEBUG is true,`base` else.

    The rational is that developping (DEBUG=True) requires sometimes actually no cache at all
    (we do not want HTML caching) and sometimes a cache (the authentication cannot work with no cache at all).

    :param settings_dict:
    :return:
    """
    cache_url: str = settings_dict["CACHE_URL"]
    parsed_urls: List[ParseResult] = [urlparse(x) for x in cache_url.split(",")]
    schemes: Set[str] = {x.scheme.lower() for x in parsed_urls}
    django_version = version.get_complete_version()
    backend = "django.core.cache.backends.locmem.LocMemCache"
    prometheus_engines_ = {}
    if settings_dict.get("USE_PROMETHEUS", False):
        prometheus_engines_ = prometheus_engines
    locmem = {
        "BACKEND": prometheus_engines_.get(backend, backend),
        "LOCATION": "unique-snowflake",
    }

    backend = "django.core.cache.backends.dummy.DummyCache"
    dummy = {"BACKEND": prometheus_engines_.get(backend, backend)}
    actual = locmem
    if django_version >= (4, 0) and schemes.issubset({"redis", "rediss"}):
        backend = "django.core.cache.backends.redis.RedisCache"
        actual = {
            "BACKEND": prometheus_engines_.get(backend, backend),
            "LOCATION": [x.geturl() for x in parsed_urls],
        }
    elif schemes.issubset({"redis", "rediss"}):
        if utils.is_package_present("django_redis"):
            # noinspection PyUnresolvedReferences
            actual = {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": [x.geturl() for x in parsed_urls],
                "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            }
        else:
            raise ImproperlyConfigured(
                "Please install 'django-redis' package to use Redis cache."
            )
    elif schemes == {"memcache"}:
        if django_version >= (3, 2) and utils.is_package_present("pymemcache"):
            backend = "django.core.cache.backends.memcached.PyMemcacheCache"
        elif django_version >= (3, 2) and utils.is_package_present("pylibmc"):
            backend = "django.core.cache.backends.memcached.PyLibMCCache"
        else:
            raise ImproperlyConfigured(
                "Please install 'pylibmc' package before using memcache engine."
            )
        info = [(x.hostname or "localhost", x.port or 11211) for x in parsed_urls]
        actual = {
            "BACKEND": prometheus_engines_.get(backend, backend),
            "LOCATION": [f"{x[0]}:{x[1]}" for x in info],
        }
    elif schemes == {"file"}:
        backend = "django.core.cache.backends.filebased.FileBasedCache"
        if len(parsed_urls) > 1:
            raise ImproperlyConfigured(
                "CACHE_URL with 'file' scheme must contain only one URL."
            )
        actual = {
            "BACKEND": prometheus_engines_.get(backend, backend),
            "LOCATION": Directory(parsed_urls[0].path),
        }
    elif cache_url:
        raise ImproperlyConfigured(
            "CACHE_URL must be a list of URLs with the 'file', 'redis', 'rediss' or 'memcache' scheme."
        )
    default = dummy if settings_dict["DEBUG"] else actual
    cached = locmem if settings_dict["DEBUG"] else actual
    return {"default": default, "locmem": locmem, "base": actual, "cached": cached}


cache_setting.required_settings = [
    "DEBUG",
    "CACHE_URL",
    "USE_PROMETHEUS",
]
