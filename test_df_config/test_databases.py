import tempfile
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.utils.version import get_complete_version

from df_config.config.dynamic_settings import CallableSetting
from df_config.guesses.databases import cache_setting, databases, databases_options
from test_df_config.test_dynamic_settings import TestDynamicSetting


class TestDatabaseSetting(TestDynamicSetting):
    other_values = {}
    maxDiff = None

    def test_postgresql(self):
        expected = {
            "default": {
                "CONN_HEALTH_CHECKS": False,
                "CONN_MAX_AGE": 0,
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "localhost",
                "NAME": "database",
                "OPTIONS": None,
                "PASSWORD": "password",
                "PORT": "5432",
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
                "DATABASE_CONN_MAX_AGE": 0,
            },
        )

    def test_postgresql_empty_port(self):
        expected = {
            "default": {
                "CONN_HEALTH_CHECKS": False,
                "CONN_MAX_AGE": 0,
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "localhost",
                "NAME": "database",
                "OPTIONS": None,
                "PASSWORD": "password",
                "PORT": None,
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
                "DATABASE_PORT": None,
                "USE_PROMETHEUS": False,
                "DATABASE_CONN_MAX_AGE": 0,
            },
        )

    def test_postgresql_cluster(self):
        expected = {
            "default": {
                "CONN_HEALTH_CHECKS": False,
                "CONN_MAX_AGE": 0,
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "dbserver1.example.com,dbserver2.example.com",
                "NAME": "database",
                "OPTIONS": None,
                "PASSWORD": "password",
                "PORT": "5432,5432",
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
                "DATABASE_HOST": "dbserver1.example.com,dbserver2.example.com",
                "DATABASE_PORT": "5432,5432",
                "USE_PROMETHEUS": False,
                "DATABASE_CONN_MAX_AGE": 0,
            },
        )

    def test_postgresql_prometheus(self):
        expected = {
            "default": {
                "CONN_HEALTH_CHECKS": False,
                "CONN_MAX_AGE": 0,
                "ENGINE": "django_prometheus.db.backends.postgresql",
                "HOST": "localhost",
                "NAME": "database",
                "OPTIONS": None,
                "PASSWORD": "password",
                "PORT": "5432",
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
                "DATABASE_CONN_MAX_AGE": 0,
            },
        )

    def test_databases_options(self):
        s = CallableSetting(databases_options)
        settings = {
            "DATABASE_ENGINE": "postgres",
            "DATABASE_SSL_CA": "",
            "DATABASE_SSL_CRL": "",
            "DATABASE_SSL_MODE": "",
            "DATABASE_SSL_CLIENT_CERT": "",
            "DATABASE_SSL_CLIENT_KEY": "",
        }
        expected = {}
        self.check(s, expected, extra_values=settings)
        settings = {
            "DATABASE_ENGINE": "mysql",
            "DATABASE_SSL_CA": "",
            "DATABASE_SSL_CRL": "",
            "DATABASE_SSL_MODE": "",
            "DATABASE_SSL_CLIENT_CERT": "",
            "DATABASE_SSL_CLIENT_KEY": "",
        }
        expected = {}
        self.check(s, expected, extra_values=settings)
        with tempfile.NamedTemporaryFile() as fd:
            fd.write(
                b"""-----BEGIN CERTIFICATE-----
MIIEMDCCAxigAwIBAgIQUJRs7Bjq1ZxN1ZfvdY+grTANBgkqhkiG9w0BAQUFADCB
-----END CERTIFICATE-----"""
            )
            fd.flush()
            settings = {
                "DATABASE_ENGINE": "postgres",
                "DATABASE_SSL_CA": fd.name,
                "DATABASE_SSL_CRL": fd.name,
                "DATABASE_SSL_MODE": "verify-ca",
                "DATABASE_SSL_CLIENT_CERT": fd.name,
                "DATABASE_SSL_CLIENT_KEY": fd.name,
            }
            expected = {
                "sslcert": fd.name,
                "sslcrl": fd.name,
                "sslkey": fd.name,
                "sslmode": "verify-ca",
                "sslrootcert": fd.name,
            }
            self.check(s, expected, extra_values=settings)
            settings = {
                "DATABASE_ENGINE": "mysql",
                "DATABASE_SSL_CA": fd.name,
                "DATABASE_SSL_CRL": fd.name,
                "DATABASE_SSL_MODE": "verify-ca",
                "DATABASE_SSL_CLIENT_CERT": fd.name,
                "DATABASE_SSL_CLIENT_KEY": fd.name,
            }
            expected = {
                "ssl": {"ca": fd.name, "cert": fd.name, "crl": fd.name, "key": fd.name},
                "ssl_mode": "VERIFY_CA",
            }
            self.check(s, expected, extra_values=settings)
        with self.assertRaises(ImproperlyConfigured):
            self.check(s, expected, extra_values=settings)
        with self.assertRaises(ImproperlyConfigured):
            settings = {
                "DATABASE_ENGINE": "mysql",
                "DATABASE_SSL_CA": "",
                "DATABASE_SSL_CRL": "",
                "DATABASE_SSL_MODE": "ca-check",
                "DATABASE_SSL_CLIENT_CERT": "",
                "DATABASE_SSL_CLIENT_KEY": "",
            }
            self.check(s, expected, extra_values=settings)


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
        # noinspection PyUnresolvedReferences
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
        # noinspection PyUnresolvedReferences
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
                    "LOCATION": ["redis://:password@localhost:6379/1"],
                },
                "cached": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": ["redis://:password@localhost:6379/1"],
                },
                "default": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": ["redis://:password@localhost:6379/1"],
                },
                "locmem": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "unique-snowflake",
                },
            }
        else:
            # noinspection PyUnresolvedReferences
            expected = {
                "base": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": ["redis://:password@localhost:6379/1"],
                    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                },
                "cached": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": ["redis://:password@localhost:6379/1"],
                    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                },
                "default": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": ["redis://:password@localhost:6379/1"],
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

    def test_cache_setting_no_debug_redis_cluster(self):
        django_version = get_complete_version()
        if django_version >= (4, 0):
            expected = {
                "base": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": [
                        "redis://:password@hostname1:6379/1",
                        "redis://:password@hostname2:6379/1",
                    ],
                },
                "cached": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": [
                        "redis://:password@hostname1:6379/1",
                        "redis://:password@hostname2:6379/1",
                    ],
                },
                "default": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": [
                        "redis://:password@hostname1:6379/1",
                        "redis://:password@hostname2:6379/1",
                    ],
                },
                "locmem": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "unique-snowflake",
                },
            }
        else:
            # noinspection PyUnresolvedReferences
            expected = {
                "base": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": [
                        "redis://:password@hostname1:6379/1",
                        "redis://:password@hostname2:6379/1",
                    ],
                    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                },
                "cached": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": [
                        "redis://:password@hostname1:6379/1",
                        "redis://:password@hostname2:6379/1",
                    ],
                    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                },
                "default": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": [
                        "redis://:password@hostname1:6379/1",
                        "redis://:password@hostname2:6379/1",
                    ],
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
                "CACHE_URL": "redis://:password@hostname1:6379/1,redis://:password@hostname2:6379/1",
                "USE_PROMETHEUS": False,
            },
        )

    def test_cache_setting_no_debug_redis_prometheus(self):
        django_version = get_complete_version()
        if django_version >= (4, 0):
            # noinspection PyUnresolvedReferences
            expected = {
                "base": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": ["redis://:password@localhost:6379/1"],
                },
                "cached": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": ["redis://:password@localhost:6379/1"],
                },
                "default": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": ["redis://:password@localhost:6379/1"],
                },
                "locmem": {
                    "BACKEND": "django_prometheus.cache.backends.locmem.LocMemCache",
                    "LOCATION": "unique-snowflake",
                },
            }
        else:
            # noinspection PyUnresolvedReferences
            expected = {
                "base": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": ["redis://:password@localhost:6379/1"],
                    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                },
                "cached": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": ["redis://:password@localhost:6379/1"],
                    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                },
                "default": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": ["redis://:password@localhost:6379/1"],
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
                    "LOCATION": ["redis://:password@localhost:6379/1"],
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
            # noinspection PyUnresolvedReferences
            expected = {
                "base": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": ["redis://:password@localhost:6379/1"],
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
                "LOCATION": ["localhost:11211"],
            },
            "cached": {
                "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
                "LOCATION": ["localhost:11211"],
            },
            "default": {
                "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
                "LOCATION": ["localhost:11211"],
            },
            "locmem": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
        }
        s = CallableSetting(cache_setting)
        with mock.patch(
            "df_config.utils.is_package_present", new=lambda x: x == "pymemcache"
        ):
            self.check(
                s,
                expected,
                extra_values={
                    "DEBUG": False,
                    "CACHE_URL": "memcache://localhost:11211",
                    "USE_PROMETHEUS": False,
                },
            ),
        expected = {
            "base": {
                "BACKEND": "django.core.cache.backends.memcached.PyLibMCCache",
                "LOCATION": ["hostname1:11211", "hostname2:11211"],
            },
            "cached": {
                "BACKEND": "django.core.cache.backends.memcached.PyLibMCCache",
                "LOCATION": ["hostname1:11211", "hostname2:11211"],
            },
            "default": {
                "BACKEND": "django.core.cache.backends.memcached.PyLibMCCache",
                "LOCATION": ["hostname1:11211", "hostname2:11211"],
            },
            "locmem": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            },
        }
        s = CallableSetting(cache_setting)
        with mock.patch(
            "df_config.utils.is_package_present", new=lambda x: x == "pylibmc"
        ):
            self.check(
                s,
                expected,
                extra_values={
                    "DEBUG": False,
                    "CACHE_URL": "memcache://hostname1:11211,memcache://hostname2:11211",
                    "USE_PROMETHEUS": False,
                },
            ),
        with mock.patch("df_config.utils.is_package_present", new=lambda x: False):
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
        s = CallableSetting(cache_setting)
        with mock.patch("df_config.utils.is_package_present", new=lambda x: False):
            self.assertRaises(
                ImproperlyConfigured,
                lambda: self.check(
                    s,
                    {},
                    extra_values={
                        "DEBUG": True,
                        "CACHE_URL": "memcache://localhost:11211",
                        "USE_PROMETHEUS": False,
                    },
                ),
            )

    def test_cache_setting_no_debug_file(self):
        expected = {
            "base": {
                "BACKEND": "django_prometheus.cache.backends.filebased.FileBasedCache",
                "LOCATION": "/var/tmp/django_cache/",
            },
            "cached": {
                "BACKEND": "django_prometheus.cache.backends.filebased.FileBasedCache",
                "LOCATION": "/var/tmp/django_cache/",
            },
            "default": {
                "BACKEND": "django_prometheus.cache.backends.filebased.FileBasedCache",
                "LOCATION": "/var/tmp/django_cache/",
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
                "CACHE_URL": "file:///var/tmp/django_cache",
                "USE_PROMETHEUS": True,
            },
        )

    def test_cache_setting_no_debug_file_invalid(self):
        s = CallableSetting(cache_setting)
        self.assertRaises(
            ImproperlyConfigured,
            lambda: self.check(
                s,
                {},
                extra_values={
                    "DEBUG": False,
                    "CACHE_URL": "file:///var/tmp/django_cache,file:///var/tmp/django_cache2",
                    "USE_PROMETHEUS": True,
                },
            ),
        )
