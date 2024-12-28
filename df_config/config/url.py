"""Allow to create different dynamic settings from a single URL."""

import re
import urllib.parse
from importlib.metadata import PackageNotFoundError, version
from typing import Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import ParseResult

from django.core.exceptions import ImproperlyConfigured
from setuptools.command.bdist_egg import can_scan

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
    """Represents a URL setting, such that each URL component can be used as a DynamicSetting."""

    ENGINES = {}
    REQUIREMENTS = {}
    SCHEME_ALIASES = {}
    # noinspection SpellCheckingInspection
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
    ):
        """Initialize the object.

        :param setting_name: The name of the Django setting that contains the URL string.
        :param required: A list of setting names that are required to be loaded before this one.
        :param url: The URL string to be parsed.
        :param split_char: A character to split the netloc part to form multiple URLs (useful for DB clusters).
        """
        self.split_char: Optional[str] = split_char
        self._url_str: Optional[str] = None
        self.parsed_urls: Optional[List[ParseResult]] = None
        self.parsed_query: Optional[Dict[str, str]] = None
        self._loaded: bool = False
        self.parse_value(url)
        self.setting_name = setting_name
        self.required = required or []

    def __repr__(self):
        """Represent this object as a string."""
        return f"{self.__class__.__name__}('{self.setting_name}')"

    def __str__(self):
        """Return the loaded URL string."""
        return self._url_str if self._url_str is not None else ""

    def parse_value(self, value: Optional[str]):
        """Parse the URL string and load its components."""
        parsed_url = None
        if value is self or not value:
            self._url_str = None
            self.parsed_urls = None
            self.parsed_query = None
        elif self.split_char != "":
            self._url_str = value
            parsed_url = urllib.parse.urlparse(value)
            self.parsed_urls = [
                parsed_url._replace(netloc=x)
                for x in parsed_url.netloc.split(self.split_char)
            ]
        else:
            self._url_str = value
            parsed_url = urllib.parse.urlparse(value)
            self.parsed_urls = [parsed_url]
        if parsed_url:
            self.parsed_query = urllib.parse.parse_qs(parsed_url.query)
        self._loaded = bool(parsed_url)

    def load(self, merger):
        """Get the URL string for the merger, parse it and load it to extract its components."""
        if self._loaded or not self.setting_name:
            return
        for required in self.required:
            merger.get_setting_value(required)
        value = merger.get_setting_value(self.setting_name)
        self.parse_value(value)
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
        return self.get_attribute_single("params")

    def get_attribute_single(self, attr_name) -> Optional[str]:
        """Return the params part of the URL."""
        if self.parsed_urls is None:
            return None
        return getattr(self.parsed_urls[0], attr_name)

    def get_attribute_multiple(self, attr_name) -> Optional[str]:
        """Return the params part of the URL."""
        if self.parsed_urls is None:
            return None
        return self.split_char.join(getattr(x, attr_name) for x in self.parsed_urls)

    def password(self, default=None):
        """Return a DynamicSetting that represents the password."""
        return Attribute(self, self.password_, default=default)

    def password_(self) -> Optional[str]:
        """Return the user password."""
        return self.get_attribute_single("password")

    def path(self, default=""):
        """Return a DynamicSetting that represents the path of the URL."""
        return Attribute(self, self.path_, default=default)

    def path_(self) -> Optional[str]:
        """Return the path of the URL."""
        return self.get_attribute_single("path")

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
        return self.get_attribute_single("query")

    def scheme(self, default=None):
        """Return a DynamicSetting that represents the URL scheme."""
        return Attribute(self, self.scheme_, default=default)

    def scheme_(self) -> Optional[str]:
        """Return the URL scheme."""
        if self.parsed_urls is None:
            return None
        scheme = self.parsed_urls[0].scheme.lower()
        scheme = self.SCHEME_ALIASES.get(scheme, scheme)
        return scheme

    def username(self, default=None):
        """Return a DynamicSetting that represents the username."""
        return Attribute(self, self.username_, default=default)

    def username_(self):
        """Return the username, if defined in the URL string."""
        return self.get_attribute_single("username")

    def database(self, default=None):
        """Return a DynamicSetting that represents the database name."""
        return Attribute(self, self.database_, default=default)

    def database_(self):
        """Return the database name."""
        v = self.get_attribute_single("path")
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

    def use_tls_(self, index=2):
        """Return True is TLS is used."""
        if not self.parsed_urls:
            return False
        s = self.scheme_()
        response = self.SCHEMES[s][index]
        return response

    def use_ssl(self, default=False):
        """Return a dynamic setting for the SSL usage."""
        return Attribute(self, self.use_ssl_, default=default)

    def use_ssl_(self):
        """Return True if SSL is used."""
        return self.use_tls_(index=1) or self.ssl_mode_() in {
            "require",
            "verify-ca",
            "verify-full",
        }

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

    def client_cert_(self) -> Optional[str]:
        """Return the client certificate file from the URL query string."""
        if not self.parsed_urls:
            return None
        return self.parsed_query.get("ssl_certfile", [""])[0] or None

    def client_cert(self, default=None) -> Attribute:
        """Return a dynamic setting for the client certificate."""
        return Attribute(self, self.client_cert_, default=default)

    def client_key_(self) -> Optional[str]:
        """Return the client key file from the URL query string."""
        if not self.parsed_urls:
            return None
        # ssl_check_hostname=false&ssl_cert_reqs=required&ssl_certfile=./localhost.crt&ssl_keyfile=./localhost.key&ssl_ca_certs=./CA.crt
        return self.parsed_query.get("ssl_keyfile", [""])[0] or None

    def client_key(self, default=None) -> Attribute:
        """Return a dynamic setting for the client key."""
        return Attribute(self, self.client_key_, default=default)

    def ca_cert_(self) -> Optional[str]:
        """Return the CA certificate file from the URL query string."""
        if not self.parsed_urls:
            return None
        return self.parsed_query.get("ssl_ca_certs", [""])[0] or None

    def ca_cert(self, default=None) -> Attribute:
        """Return a dynamic setting for the CA certificate."""
        return Attribute(self, self.ca_cert_, default=default)

    def ca_crl_(self) -> Optional[str]:
        """Return the CRL file from the URL query string."""
        if not self.parsed_urls:
            return None
        return self.parsed_query.get("ssl_crlfile", [""])[0] or None

    def ca_crl(self, default=None) -> Attribute:
        """Return a dynamic setting for the CRL file."""
        return Attribute(self, self.ca_crl_, default=default)

    def ssl_mode_(self) -> Optional[str]:
        """Return the SSL mode from the URL query string (mysql and postgres)."""
        if not self.parsed_urls:
            return None
        ssl_mode = self.parsed_query.get("ssl_mode", ["allow"])[0]
        if ssl_mode in {
            "disable",
            "allow",
            "prefer",
            "require",
            "verify-ca",
            "verify-full",
        }:
            return ssl_mode
        check_hostname = (
            self.parsed_query.get("ssl_check_hostname", ["true"])[0] != "false"
        )
        check_ca = self.parsed_query.get("ssl_cert_reqs", ["required"])[0] != "none"
        use_ssl = (
            self.use_tls_(index=1) or self.parsed_query.get("ssl", [""])[0] == "true"
        )
        avoid_ssl = self.parsed_query.get("ssl", [""])[0] == "false"
        if not avoid_ssl and check_hostname:
            return "verify-full"
        elif not avoid_ssl and check_ca:
            return "verify-ca"
        elif use_ssl:
            return "require"
        elif avoid_ssl:
            return "disable"
        return "prefer"

    def ssl_mode(self, default=None) -> Attribute:
        """Return a dynamic setting for the SSL mode."""
        return Attribute(self, self.ssl_mode_, default=default)


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
        "django.db.backends.postgresql": ["psycopg2-binary", "psycopg2", "psycopg"],
        "django.db.backends.oracle": ["cx_Oracle"],
        "django.db.backends.mysql": ["mysqlclient", "pymysql"],
    }


class RedisURL(URLSetting):
    """Specialized class for Redis URLs, since databases are identified by an integer."""

    def database_(self) -> Optional[int]:
        """Extract a valid database number for Redis connections."""
        v = self.get_attribute_single("path")
        if not v or not (matcher := re.match(r"/(0|[1-9]\d*)$", v)):
            return None
        return int(matcher.group(1))
