import re
import urllib.parse
from typing import List, Optional

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
            return self.default
        return merger.analyze_raw_value(value, provider_name, setting_name)


class URLSetting:
    defaults = {
        "smtp": (25, False, False),
        "smtps": (465, True, False),
        "smtp+tls": (487, False, True),
        "http": (80, False, False),
        "https": (443, True, False),
        "redis": (6379, False, False),
        "rediss": (6379, True, False),
        "mysql": (3306, False, False),
        "psql": (5432, False, False),
        "oracle": (1521, False, False),
        "memcache": (11211, False, False),
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

    def load(self, merger):
        if self._loaded or not self.setting_name:
            return
        for required in self.required:
            merger.get_setting_value(required)
        self._url_str = merger.get_setting_value(self.setting_name)
        if self._url_str:
            self.parsed_url = urllib.parse.urlparse(self._url_str)
        else:
            self.parsed_url = None
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
        return self.parsed_url.scheme if self.parsed_url else None

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
        return self.defaults[self.parsed_url.scheme.lower()][0]

    def use_tls(self, default=False):
        return Attribute(self, self.use_tls_, default=default)

    def use_tls_(self):
        if not self.parsed_url:
            return False
        return self.defaults[self.parsed_url.scheme.lower()][2]

    def use_ssl(self, default=False):
        return Attribute(self, self.use_ssl_, default=default)

    def use_ssl_(self):
        if not self.parsed_url:
            return False
        return self.defaults[self.parsed_url.scheme.lower()][1]


class DatabaseURL:
    pass
