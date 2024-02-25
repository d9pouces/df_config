"""Allow to create different dynamic settings from a single URL."""
import re
import urllib.parse
from importlib.metadata import PackageNotFoundError, version
from typing import List, Optional

from df_config.config.dynamic_settings import DynamicSettting


class Attribute(DynamicSettting):
    """Dynamic setting that is a component of an URL string."""

    def __init__(self, parsed_url, attribute: callable, default=None):
        """Initialize the object."""
        super().__init__(attribute)
        self.url_setting: URLSetting = parsed_url
        self.default = default

    def get_value(self, merger, provider_name: str, setting_name: str):
        """Get the final value of the attribute."""
        self.url_setting.load(merger)
        if self.url_setting.parsed_url:
            value = self.value()
        else:
            value = self.default
        return merger.analyze_raw_value(value, provider_name, setting_name)

    def __repr__(self):
        """Represent this object as a string."""
        method = self.value.__name__[:-1]
        default = self.default
        setting = (
            f"{self.url_setting.__class__.__name__}({self.url_setting.setting_name!r})"
        )
        return f"{setting}.{method}(default={default!r})"


class URLSetting:
    """Represents an URL setting, such that each URL component can be used as a DynamicSetting."""

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
        """Initialize the object."""
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
        """Represent this object as a string."""
        return f"{self.__class__.__name__}('{self.setting_name}')"

    def __str__(self):
        """Return the loaded URL string."""
        return self._url_str if self._url_str is not None else ""

    def load(self, merger):
        """Get the URL string for the merger, parse it and load it to extract its components."""
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
        """Return a DynamicSetting that represents the hostname."""
        return Attribute(self, self.hostname_, default=default)

    def hostname_(self):
        """Return the hostname."""
        return self.parsed_url.hostname if self.parsed_url else None

    def netloc(self, default="localhost"):
        """Return a DynamicSetting that represents the netloc."""
        return Attribute(self, self.netloc_, default=default)

    def netloc_(self):
        """Return the netloc."""
        return self.parsed_url.netloc if self.parsed_url else None

    def params(self, default=""):
        """Return a DynamicSetting that represents the params."""
        return Attribute(self, self.params_, default=default)

    def params_(self):
        """Return the params part of the URL."""
        return self.parsed_url.params if self.parsed_url else None

    def password(self, default=None):
        """Return a DynamicSetting that represents the password."""
        return Attribute(self, self.password_, default=default)

    def password_(self):
        """Return the user password."""
        return self.parsed_url.password if self.parsed_url else None

    def path(self, default=""):
        """Return a DynamicSetting that represents the path of the URL."""
        return Attribute(self, self.path_, default=default)

    def path_(self):
        """Return the path of the URL."""
        return self.parsed_url.path if self.parsed_url else None

    def port(self, default=None):
        """Return a DynamicSetting that represents the port of the URL."""
        return Attribute(self, self.port_, default=default)

    def port_(self):
        """Return the port of the URL."""
        return self.parsed_url.port if self.parsed_url else None

    def query(self, default=""):
        """Return a DynamicSetting that represents the query string from the URL."""
        return Attribute(self, self.query_, default=default)

    def query_(self):
        """Return the query string from the URL."""
        return self.parsed_url.query if self.parsed_url else None

    def scheme(self, default=None):
        """Return a DynamicSetting that represents the URL scheme."""
        return Attribute(self, self.scheme_, default=default)

    def scheme_(self):
        """Return the URL scheme."""
        if self.parsed_url is None:
            return None
        s = self.parsed_url.scheme.lower()
        return self.SCHEME_ALIASES.get(s, s)

    def username(self, default=None):
        """Return a DynamicSetting that represents the username."""
        return Attribute(self, self.username_, default=default)

    def username_(self):
        """Return the username, if defined in the URL string."""
        return self.parsed_url.username if self.parsed_url else None

    def database(self, default=None):
        """Return a DynamicSetting that represents the database name."""
        return Attribute(self, self.database_, default=default)

    def database_(self):
        """Return the database name."""
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
        """Return the port number for the port (the default one if not specified)."""
        if not self.parsed_url:
            return None
        if self.parsed_url.port:
            return int(self.parsed_url.port)
        s = self.scheme_()
        return self.SCHEMES[s][0]

    def use_tls(self, default=False):
        """Return an Dynamic setting for the TLS usage."""
        return Attribute(self, self.use_tls_, default=default)

    def use_tls_(self):
        """Return True is TLS is used."""
        if not self.parsed_url:
            return False
        s = self.scheme_()
        return self.SCHEMES[s][2]

    def use_ssl(self, default=False):
        """Return an Dynamic setting for the SSL usage."""
        return Attribute(self, self.use_ssl_, default=default)

    def use_ssl_(self):
        """Return True if SSL is used."""
        if not self.parsed_url:
            return False
        s = self.scheme_()
        return self.SCHEMES[s][1]

    def engine(self, default=None):
        """Return an Dynamic setting for the database engine."""
        return Attribute(self, self.engine_, default=default)

    def engine_(self):
        """Return the engine name from the URL scheme."""
        if not self.parsed_url:
            return None
        return self.normalize_engine(self.scheme_())

    @classmethod
    def normalize_engine(cls, scheme):
        """Return a normalized engine name from a URL string."""
        engine = cls.ENGINES.get(scheme, scheme)
        requirements = cls.REQUIREMENTS.get(engine, [])
        found = False
        for req in requirements:
            try:
                version(req)
                found = True
            except PackageNotFoundError:
                pass
        if not found and requirements:
            from df_config.checks import missing_package, settings_check_results

            settings_check_results.append(
                missing_package("/".join(requirements), f" to use {engine}.")
            )
        return engine


class DatabaseURL(URLSetting):
    """Guess the database engines from a URL string."""

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
    """Specialized class for Redis URLs, since databases are identified by a integer."""

    def database_(self):
        """Extract a valid database number for Redis connections."""
        if self.parsed_url is None:
            return None
        elif not self.parsed_url.path:
            return 1
        matcher = re.match(r"/(0|[1-9]\d*)$", self.parsed_url.path)
        if not matcher:
            return 0
        return int(matcher.group(1))
