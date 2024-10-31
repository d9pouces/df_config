"""Allow to create different dynamic settings from a single URL."""

import re
import urllib.parse
from importlib.metadata import PackageNotFoundError, version
from typing import Callable, Dict, List, Optional, Tuple, Union

from django.core.exceptions import ImproperlyConfigured

from df_config.config.dynamic_settings import DynamicSettting


class Attribute(DynamicSettting):
    """Dynamic setting which is an attribute of a URL string."""

    def __init__(
        self,
        url_setting,
        attribute: Callable[[], Optional[Union[str, bool]]],
        default=None,
    ):
        """Initialize the object."""
        super().__init__(attribute)
        self.url_setting: URLSetting = url_setting
        self.default = default

    def get_value(self, merger, provider_name: str, setting_name: str):
        """Get the final value of the attribute."""
        self.url_setting.load(merger)
        if self.url_setting.parsed_urls:
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
    SCHEMES: Dict[str, Tuple[int, bool, bool]] = {
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
    }  # (port, SSL ?, StartTLS ?)

    def __init__(
        self,
        setting_name: str = None,
        required: List[str] = None,
        url: Optional[str] = None,
        split_char: str = ",",
        split_netloc_only: bool = True,
    ):
        """Initialize the object.

        :param setting_name: The name of the Django setting that contains the URL string.
        :param required: A list of setting names that are required to be loaded before this one.
        :param url: The URL string to be parsed.
        :param split_char: A character to split the raw URL string into multiple URLs (useful for DB clusters).
        :param split_netloc_only: If True, scheme, auth, params and path parts must be identical across URLs.


        """
        self.split_char = split_char
        self.split_netloc_only = split_netloc_only
        if not url:
            self._url_str = None
            self.parsed_urls = None
            self._loaded = False
        else:
            self._url_str = url
            if self.split_char != "":
                self.parsed_urls = [
                    urllib.parse.urlparse(x)
                    for x in self._url_str.split(self.split_char)
                ]
            else:
                self.parsed_urls = [urllib.parse.urlparse(self._url_str)]
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
            self.parsed_urls = None
        elif self.split_char != "":
            self._url_str = value
            self.parsed_urls = [
                urllib.parse.urlparse(x) for x in self._url_str.split(self.split_char)
            ]
        else:
            self._url_str = value
            self.parsed_urls = [urllib.parse.urlparse(self._url_str)]
        self._loaded = True

    def hostname(self, default="localhost"):
        """Return a DynamicSetting that represents the hostname."""
        return Attribute(self, self.hostname_, default=default)

    def hostname_(self) -> Optional[str]:
        """Return the hostname."""
        if self.parsed_urls is None:
            return None
        return self.split_char.join(x.hostname for x in self.parsed_urls)

    def netloc(self, default="localhost"):
        """Return a DynamicSetting that represents the netloc."""
        return Attribute(self, self.netloc_, default=default)

    def netloc_(self) -> Optional[str]:
        """Return the netloc."""
        if self.parsed_urls is None:
            return None
        return self.split_char.join(x.netloc for x in self.parsed_urls)

    def params(self, default=""):
        """Return a DynamicSetting that represents the params."""
        return Attribute(self, self.params_, default=default)

    def params_(self) -> Optional[str]:
        """Return the params part of the URL."""
        return self.get_attribute_("params")

    def get_attribute_(self, attr_name) -> Optional[str]:
        """Return the params part of the URL."""
        if self.parsed_urls is None:
            return None
        elif self.split_netloc_only:
            if len({getattr(x, attr_name) for x in self.parsed_urls}) > 1:
                raise ImproperlyConfigured(
                    f"{attr_name} must be identical across URLs '{self._url_str}'."
                )
            return getattr(self.parsed_urls[0], attr_name)
        return self.split_char.join(getattr(x, attr_name) for x in self.parsed_urls)

    def password(self, default=None):
        """Return a DynamicSetting that represents the password."""
        return Attribute(self, self.password_, default=default)

    def password_(self) -> Optional[str]:
        """Return the user password."""
        return self.get_attribute_("password")

    def path(self, default=""):
        """Return a DynamicSetting that represents the path of the URL."""
        return Attribute(self, self.path_, default=default)

    def path_(self) -> Optional[str]:
        """Return the path of the URL."""
        return self.get_attribute_("path")

    def port(self, default=None):
        """Return a DynamicSetting that represents the port of the URL."""
        return Attribute(self, self.port_, default=default)

    def port_(self) -> Optional[str]:
        """Return the port of the URL."""
        if self.parsed_urls is None:
            return None
        ports = []
        for parsed_url in self.parsed_urls:
            if parsed_url.port:
                ports.append(str(parsed_url.port))
            else:
                s = parsed_url.scheme.lower()
                s = self.SCHEME_ALIASES.get(s, s)
                ports.append(str(self.SCHEMES[s][0]))
        return self.split_char.join(ports)

    def query(self, default=""):
        """Return a DynamicSetting that represents the query string from the URL."""
        return Attribute(self, self.query_, default=default)

    def query_(self) -> Optional[str]:
        """Return the query string from the URL."""
        return self.get_attribute_("query")

    def scheme(self, default=None):
        """Return a DynamicSetting that represents the URL scheme."""
        return Attribute(self, self.scheme_, default=default)

    def scheme_(self) -> Optional[str]:
        """Return the URL scheme."""
        if self.parsed_urls is None:
            return None
        schemes = [x.scheme.lower() for x in self.parsed_urls]
        schemes = [self.SCHEME_ALIASES.get(x, x) for x in schemes]
        if self.split_netloc_only:
            if len(set(schemes)) > 1:
                raise ImproperlyConfigured(
                    f"Scheme must be identical across URLs '{self._url_str}'."
                )
            return schemes[0]
        return self.split_char.join(schemes)

    def username(self, default=None):
        """Return a DynamicSetting that represents the username."""
        return Attribute(self, self.username_, default=default)

    def username_(self):
        """Return the username, if defined in the URL string."""
        return self.get_attribute_("username")

    def database(self, default=None):
        """Return a DynamicSetting that represents the database name."""
        return Attribute(self, self.database_, default=default)

    def database_(self):
        """Return the database name."""
        v = self.get_attribute_("path")
        if not v or not (matcher := re.match(r"/([^/]+)", v)):
            return None
        return matcher.group(1)

    def port_int(self, default=None):
        """Return an integer value for the port (the default one if not specified)."""
        return Attribute(self, self.port_int_, default=default)

    def port_int_(self) -> Optional[int]:
        """Return the port number for the port (the default one if not specified)."""
        if not self.parsed_urls:
            return None
        elif len(self.parsed_urls) > 1:
            raise ImproperlyConfigured("Multiple URLs, cannot return a single port.")
        parsed_url = self.parsed_urls[0]
        if parsed_url.port:
            return parsed_url.port
        s = parsed_url.scheme.lower()
        s = self.SCHEME_ALIASES.get(s, s)
        return self.SCHEMES[s][0]

    def use_tls(self, default=False):
        """Return a dynamic setting for the TLS usage."""
        return Attribute(self, self.use_tls_, default=default)

    def use_tls_(self):
        """Return True is TLS is used."""
        if not self.parsed_urls:
            return False
        elif len(self.parsed_urls) > 1:
            raise ImproperlyConfigured("Multiple URLs, cannot return a single value.")
        s = self.scheme_()
        return self.SCHEMES[s][2]

    def use_ssl(self, default=False):
        """Return a dynamic setting for the SSL usage."""
        return Attribute(self, self.use_ssl_, default=default)

    def use_ssl_(self):
        """Return True if SSL is used."""
        if not self.parsed_urls:
            return False
        elif len(self.parsed_urls) > 1:
            raise ImproperlyConfigured("Multiple URLs, cannot return a single value.")
        s = self.scheme_()
        return self.SCHEMES[s][1]

    def engine(self, default=None):
        """Return a dynamic setting for the database engine."""
        return Attribute(self, self.engine_, default=default)

    def engine_(self):
        """Return the engine name from the URL scheme."""
        if not self.parsed_urls:
            return None
        scheme = self.parsed_urls[0].scheme.lower()
        return self.normalize_engine(scheme)

    @classmethod
    def normalize_engine(cls, scheme: str):
        """Return a normalized Django engine name from a URL scheme string."""
        scheme = cls.SCHEME_ALIASES.get(scheme, scheme)
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

    def database_(self) -> Optional[int]:
        """Extract a valid database number for Redis connections."""
        v = self.get_attribute_("path")
        if not v or not (matcher := re.match(r"/(0|[1-9]\d*)$", v)):
            return None
        return int(matcher.group(1))
