from django.core.exceptions import ImproperlyConfigured
from django.utils.version import get_complete_version

from df_config.config.dynamic_settings import CallableSetting
from df_config.guesses.databases import cache_setting, databases
from test_df_config.test_dynamic_settings import TestDynamicSetting


class TestDatabaseSetting(TestDynamicSetting):
    other_values = {}
    maxDiff = None

    def test_postgresql(self):
        expected = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "localhost",
                "NAME": "database",
                "OPTIONS": None,
                "PASSWORD": "password",
                "PORT": 5432,
                "USER": "user",
            }
        }
        s = CallableSetting(databases)
        self.check(
            s,
            expected,
            extra_values={
                "DATABASE_ENGINE": "postgres",
                "DATABASE_NAME": "database",
                "DATABASE_USER": "user",
                "DATABASE_OPTIONS": None,
                "DATABASE_PASSWORD": "password",
                "DATABASE_HOST": "localhost",
                "DATABASE_PORT": 5432,
                "USE_PROMETHEUS": False,
            },
        )

    def test_postgresql_prometheus(self):
        expected = {
            "default": {
                "ENGINE": "django_prometheus.db.backends.postgresql",
                "HOST": "localhost",
                "NAME": "database",
                "OPTIONS": None,
                "PASSWORD": "password",
                "PORT": 5432,
                "USER": "user",
            }
        }
        s = CallableSetting(databases)
        self.check(
            s,
            expected,
            extra_values={
                "DATABASE_ENGINE": "postgres",
                "DATABASE_NAME": "database",
                "DATABASE_USER": "user",
                "DATABASE_OPTIONS": None,
                "DATABASE_PASSWORD": "password",
                "DATABASE_HOST": "localhost",
                "DATABASE_PORT": 5432,
                "USE_PROMETHEUS": True,
            },
        )


class TestCacheSetting(TestDynamicSetting):
    other_values = {}
    maxDiff = None

    def test_cache_setting_no_debug(self):
        expected = {
            "base": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
            "cached": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
            "locmem": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
        }
        s = CallableSetting(cache_setting)
        self.check(
            s,
            expected,
            extra_values={"DEBUG": False, "CACHE_URL": "", "USE_PROMETHEUS": False},
        )

    def test_cache_setting_no_debug_prometheus(self):
        expected = {
            "base": {
                "BACKEND": "django_prometheus.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
            "cached": {
                "BACKEND": "django_prometheus.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
            "default": {
                "BACKEND": "django_prometheus.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
            "locmem": {
                "BACKEND": "django_prometheus.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
        }
        s = CallableSetting(cache_setting)
        self.check(
            s,
            expected,
            extra_values={"DEBUG": False, "CACHE_URL": "", "USE_PROMETHEUS": True},
        )

    def test_cache_setting_debug(self):
        expected = {
            "base": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
            "cached": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
            "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
            "locmem": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
        }
        s = CallableSetting(cache_setting)
        self.check(
            s,
            expected,
            extra_values={"DEBUG": True, "CACHE_URL": "", "USE_PROMETHEUS": False},
        )

    def test_cache_setting_debug_prometheus(self):
        expected = {
            "base": {
                "BACKEND": "django_prometheus.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
            "cached": {
                "BACKEND": "django_prometheus.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
            "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
            "locmem": {
                "BACKEND": "django_prometheus.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
        }
        s = CallableSetting(cache_setting)
        self.check(
            s,
            expected,
            extra_values={"DEBUG": True, "CACHE_URL": "", "USE_PROMETHEUS": True},
        )

    def test_cache_setting_no_debug_redis(self):
        django_version = get_complete_version()
        if django_version >= (4, 0):
            expected = {
                "base": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                },
                "cached": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                },
                "default": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                },
                "locmem": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "unique-snowflake",
                },
            }
        else:
            expected = {
                "base": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                },
                "cached": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                },
                "default": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                },
                "locmem": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "unique-snowflake",
                },
            }
        s = CallableSetting(cache_setting)
        self.check(
            s,
            expected,
            extra_values={
                "DEBUG": False,
                "CACHE_URL": "redis://:password@localhost:6379/1",
                "USE_PROMETHEUS": False,
            },
        )

    def test_cache_setting_no_debug_redis_prometheus(self):
        django_version = get_complete_version()
        if django_version >= (4, 0):
            expected = {
                "base": {
                    "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                },
                "cached": {
                    "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                },
                "default": {
                    "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                },
                "locmem": {
                    "BACKEND": "django_prometheus.cache.backends.locmem.LocMemCache",
                    "LOCATION": "unique-snowflake",
                },
            }
        else:
            expected = {
                "base": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                },
                "cached": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                },
                "default": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                },
                "locmem": {
                    "BACKEND": "django_prometheus.cache.backends.locmem.LocMemCache",
                    "LOCATION": "unique-snowflake",
                },
            }
        s = CallableSetting(cache_setting)
        self.check(
            s,
            expected,
            extra_values={
                "DEBUG": False,
                "CACHE_URL": "redis://:password@localhost:6379/1",
                "USE_PROMETHEUS": True,
            },
        )

    def test_cache_setting_debug_redis(self):
        django_version = get_complete_version()
        if django_version >= (4, 0):
            expected = {
                "base": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                },
                "cached": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "unique-snowflake",
                },
                "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
                "locmem": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "unique-snowflake",
                },
            }
        else:
            expected = {
                "base": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": "redis://:password@localhost:6379/1",
                    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                },
                "cached": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "unique-snowflake",
                },
                "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
                "locmem": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "unique-snowflake",
                },
            }
        s = CallableSetting(cache_setting)
        self.check(
            s,
            expected,
            extra_values={
                "DEBUG": True,
                "CACHE_URL": "redis://:password@localhost:6379/1",
                "USE_PROMETHEUS": False,
            },
        )

    def test_cache_setting_no_debug_memcache(self):
        expected = {
            "base": {
                "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
                "LOCATION": "localhost:11211",
            },
            "cached": {
                "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
                "LOCATION": "localhost:11211",
            },
            "default": {
                "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
                "LOCATION": "localhost:11211",
            },
            "locmem": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
        }
        s = CallableSetting(cache_setting)
        self.assertRaises(
            ImproperlyConfigured,
            lambda: self.check(
                s,
                expected,
                extra_values={
                    "DEBUG": False,
                    "CACHE_URL": "memcache://localhost:11211",
                    "USE_PROMETHEUS": False,
                },
            ),
        )

    def test_cache_setting_debug_memcache(self):
        expected = {
            "base": {
                "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
                "LOCATION": "localhost:11211",
            },
            "cached": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
            "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
            "locmem": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
        }
        s = CallableSetting(cache_setting)
        self.assertRaises(
            ImproperlyConfigured,
            lambda: self.check(
                s,
                expected,
                extra_values={
                    "DEBUG": True,
                    "CACHE_URL": "memcache://localhost:11211",
                    "USE_PROMETHEUS": False,
                },
            ),
        )
