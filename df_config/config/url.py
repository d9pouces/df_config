import re
import urllib.parse
from typing import List, Optional

from pkg_resources import DistributionNotFound, get_distribution

from df_config.config.dynamic_settings import DynamicSettting


class Attribute(DynamicSettting):
    def __init__(self, parsed_url, attribute: callable, default=None):
        super().__init__(attribute)
        self.url_setting: URLSetting = parsed_url
        self.default = default

    def get_value(self, merger, provider_name: str, setting_name: str):
        self.url_setting.load(merger)
        if self.url_setting.parsed_url:
            value = self.value()
        else:
            value = self.default
        return merger.analyze_raw_value(value, provider_name, setting_name)

    def __repr__(self):
        method = self.value.__name__[:-1]
        default = self.default
        setting = (
            f"{self.url_setting.__class__.__name__}({self.url_setting.setting_name!r})"
        )
        return f"{setting}.{method}(default={default!r})"


class URLSetting:
    ENGINES = {}
    REQUIREMENTS = {}
    SCHEME_ALIASES = {}
    SCHEMES = {
        "amqp": (5672, False, False),
        "file": (None, False, False),
        "http": (80, False, False),
        "https": (443, True, False),
        "memcache": (11211, False, False),
        "mariadb": (3306, False, False),
        "mysql": (3306, False, False),
        "oracle": (1521, False, False),
        "postgres": (5432, False, False),
        "redis": (6379, False, False),
        "rediss": (6379, True, False),
        "smtp": (25, False, False),
        "smtp+tls": (487, False, True),
        "smtps": (465, True, False),
        "sqlite": (None, False, False),
        "sqlite3": (None, False, False),
    }

    def __init__(
        self,
        setting_name: str = None,
        required: List[str] = None,
        url: Optional[str] = None,
    ):
        if url is None:
            self.parsed_url = None
            self._url_str = None
            self._loaded = False
        else:
            self._url_str = url
            self.parsed_url = urllib.parse.urlparse(self._url_str)
            self._loaded = True
        self.setting_name = setting_name
        self.required = required or []

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.setting_name}')"

    def load(self, merger):
        if self._loaded or not self.setting_name:
            return
        for required in self.required:
            merger.get_setting_value(required)
        value = merger.get_setting_value(self.setting_name)
        if value is self or not value:
            self._url_str = None
            self.parsed_url = None
        else:
            self._url_str = value
            self.parsed_url = urllib.parse.urlparse(self._url_str)
        self._loaded = True

    def hostname(self, default="localhost"):
        return Attribute(self, self.hostname_, default=default)

    def hostname_(self):
        return self.parsed_url.hostname if self.parsed_url else None

    def netloc(self, default="localhost"):
        return Attribute(self, self.netloc_, default=default)

    def netloc_(self):
        return self.parsed_url.netloc if self.parsed_url else None

    def params(self, default=""):
        return Attribute(self, self.params_, default=default)

    def params_(self):
        return self.parsed_url.params if self.parsed_url else None

    def password(self, default=None):
        return Attribute(self, self.password_, default=default)

    def password_(self):
        return self.parsed_url.password if self.parsed_url else None

    def path(self, default=""):
        return Attribute(self, self.path_, default=default)

    def path_(self):
        return self.parsed_url.path if self.parsed_url else None

    def port(self, default=None):
        return Attribute(self, self.port_, default=default)

    def port_(self):
        return self.parsed_url.port if self.parsed_url else None

    def query(self, default=""):
        return Attribute(self, self.query_, default=default)

    def query_(self):
        return self.parsed_url.query if self.parsed_url else None

    def scheme(self, default=None):
        return Attribute(self, self.scheme_, default=default)

    def scheme_(self):
        if self.parsed_url is None:
            return None
        s = self.parsed_url.scheme.lower()
        return self.SCHEME_ALIASES.get(s, s)

    def username(self, default=None):
        return Attribute(self, self.username_, default=default)

    def username_(self):
        return self.parsed_url.username if self.parsed_url else None

    def database(self, default=None):
        return Attribute(self, self.database_, default=default)

    def database_(self):
        if self.parsed_url is None or not self.parsed_url.path:
            return None
        matcher = re.match(r"/([^/]+)", self.parsed_url.path)
        if not matcher:
            return None
        return matcher.group(1)

    def port_int(self, default=None):
        """Return an integer value for the port (the default one if not specified)."""
        return Attribute(self, self.port_int_, default=default)

    def port_int_(self) -> Optional[int]:
        if not self.parsed_url:
            return None
        if self.parsed_url.port:
            return int(self.parsed_url.port)
        s = self.scheme_()
        return self.SCHEMES[s][0]

    def use_tls(self, default=False):
        return Attribute(self, self.use_tls_, default=default)

    def use_tls_(self):
        if not self.parsed_url:
            return False
        s = self.scheme_()
        return self.SCHEMES[s][2]

    def use_ssl(self, default=False):
        return Attribute(self, self.use_ssl_, default=default)

    def use_ssl_(self):
        if not self.parsed_url:
            return False
        s = self.scheme_()
        return self.SCHEMES[s][1]

    def engine(self, default=None):
        return Attribute(self, self.engine_, default=default)

    def engine_(self):
        if not self.parsed_url:
            return None
        return self.normalize_engine(self.scheme_())

    @classmethod
    def normalize_engine(cls, scheme):
        engine = cls.ENGINES.get(scheme, scheme)
        requirements = cls.REQUIREMENTS.get(engine, [])
        found = False
        for req in requirements:
            try:
                get_distribution(req)
                found = True
            except DistributionNotFound:
                pass
        if not found and requirements:
            from df_config.checks import missing_package, settings_check_results

            settings_check_results.append(
                missing_package("/".join(requirements), f" to use {engine}.")
            )
        return engine


class DatabaseURL(URLSetting):
    ENGINES = {
        "mysql": "django.db.backends.mysql",
        "mariadb": "django.db.backends.mysql",
        "oracle": "django.db.backends.oracle",
        "postgres": "django.db.backends.postgresql",
        "sqlite3": "django.db.backends.sqlite3",
    }
    SCHEME_ALIASES = {
        "psql": "postgres",
        "postgresql": "postgres",
        "sqlite": "sqlite3",
    }
    REQUIREMENTS = {
        "django.db.backends.postgresql": ["psycopg2-binary", "psycopg2"],
        "django.db.backends.oracle": ["cx_Oracle"],
        "django.db.backends.mysql": ["mysqlclient", "pymysql"],
    }


class RedisURL(URLSetting):
    def database_(self):
        if self.parsed_url is None:
            return None
        elif not self.parsed_url.path:
            return 1
        matcher = re.match(r"/(0|[1-9]\d*)$", self.parsed_url.path)
        if not matcher:
            return 0
        return int(matcher.group(1))
