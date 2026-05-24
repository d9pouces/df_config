"""Unit tests for df_config/config/url.py — URLSetting, RedisURL, Attribute."""

import io
from unittest import TestCase

from django.core.exceptions import ImproperlyConfigured

from df_config.config.merger import SettingMerger
from df_config.config.url import DatabaseURL, RedisURL, URLSetting
from df_config.config.values_providers import DictProvider


def _make_merger(settings_dict):
    provider = DictProvider(settings_dict, name="test")
    merger = SettingMerger(None, [provider], stdout=io.StringIO(), stderr=io.StringIO())
    merger.load_raw_settings()
    return merger


class TestURLSettingParseValue(TestCase):
    def test_empty_string(self):
        u = URLSetting()
        u.parse_value("")
        self.assertIsNone(u.parsed_urls)

    def test_none(self):
        u = URLSetting()
        u.parse_value(None)
        self.assertIsNone(u.parsed_urls)

    def test_self_reference(self):
        u = URLSetting()
        u.parse_value(u)
        self.assertIsNone(u.parsed_urls)

    def test_simple_url(self):
        u = URLSetting(url="http://localhost:8080/path")
        self.assertIsNotNone(u.parsed_urls)
        self.assertEqual(1, len(u.parsed_urls))

    def test_multiple_hosts(self):
        u = URLSetting(url="redis://a:6379,b:6380", split_char=",")
        self.assertEqual(2, len(u.parsed_urls))

    def test_no_split(self):
        u = URLSetting(url="redis://a:6379,b:6380", split_char="")
        self.assertEqual(1, len(u.parsed_urls))

    def test_query_parsed(self):
        u = URLSetting(url="redis://localhost/0?timeout=30")
        self.assertIn("timeout", u.parsed_query)


class TestURLSettingStr(TestCase):
    def test_str_with_url(self):
        u = URLSetting(url="http://example.com")
        self.assertEqual("http://example.com", str(u))

    def test_str_no_url(self):
        u = URLSetting()
        self.assertEqual("", str(u))

    def test_repr(self):
        u = URLSetting(setting_name="MY_URL")
        self.assertIn("MY_URL", repr(u))


class TestURLSettingAttributes(TestCase):
    def setUp(self):
        self.url = URLSetting(url="http://user:pass@host1:9000,host2:9001/mypath?a=1")

    def test_hostname(self):
        self.assertEqual("host1,host2", self.url.hostname_())

    def test_netloc(self):
        result = self.url.netloc_()
        self.assertIn("host1", result)
        self.assertIn("host2", result)

    def test_password(self):
        self.assertEqual("pass", self.url.password_())

    def test_username(self):
        self.assertEqual("user", self.url.username_())

    def test_path(self):
        self.assertEqual("/mypath", self.url.path_())

    def test_query(self):
        self.assertEqual("a=1", self.url.query_())

    def test_params(self):
        self.assertEqual("", self.url.params_())

    def test_scheme(self):
        self.assertEqual("http", self.url.scheme_())

    def test_port_explicit(self):
        result = self.url.port_()
        self.assertIn("9000", result)
        self.assertIn("9001", result)


class TestURLSettingDefaults(TestCase):
    def test_hostname_default_when_no_url(self):
        u = URLSetting()
        attr = u.hostname(default="mydefault")
        merger = _make_merger({"X": attr})
        result = attr.get_value(merger, "test", "X")
        self.assertEqual("mydefault", result)

    def test_port_default_when_no_url(self):
        u = URLSetting()
        attr = u.port(default=1234)
        merger = _make_merger({"X": attr})
        result = attr.get_value(merger, "test", "X")
        self.assertEqual(1234, result)


class TestURLSettingPortFromScheme(TestCase):
    def test_http_default_port(self):
        u = URLSetting(url="http://example.com/")
        self.assertEqual("80", u.port_())

    def test_https_default_port(self):
        u = URLSetting(url="https://example.com/")
        self.assertEqual("443", u.port_())

    def test_redis_default_port(self):
        u = URLSetting(url="redis://example.com/")
        self.assertEqual("6379", u.port_())


class TestURLSettingPortInt(TestCase):
    def test_port_int_explicit(self):
        u = URLSetting(url="http://example.com:9090/")
        self.assertEqual(9090, u.port_int_())

    def test_port_int_from_scheme(self):
        u = URLSetting(url="http://example.com/")
        self.assertEqual(80, u.port_int_())

    def test_port_int_multiple_urls_raises(self):
        u = URLSetting(url="http://host1:80,host2:81")
        with self.assertRaises(ImproperlyConfigured):
            u.port_int_()

    def test_port_int_no_url(self):
        u = URLSetting()
        self.assertIsNone(u.port_int_())


class TestURLSettingUseTls(TestCase):
    def test_http_no_tls(self):
        u = URLSetting(url="http://example.com/")
        self.assertFalse(u.use_tls_())

    def test_smtp_tls(self):
        u = URLSetting(url="smtp+tls://example.com/")
        self.assertTrue(u.use_tls_())

    def test_no_url_no_tls(self):
        u = URLSetting()
        self.assertFalse(u.use_tls_())


class TestURLSettingUseSSL(TestCase):
    def test_https_use_ssl(self):
        u = URLSetting(url="https://example.com/")
        self.assertTrue(u.use_ssl_())

    def test_http_no_ssl_explicit(self):
        u = URLSetting(url="http://example.com/?ssl=false")
        self.assertFalse(u.use_ssl_())


class TestURLSettingSslMode(TestCase):
    def test_allow_by_default(self):
        # ssl_mode defaults to "allow" when not specified in the query string
        u = URLSetting(url="http://example.com/")
        self.assertEqual("allow", u.ssl_mode_())

    def test_explicit_ssl_mode_disable(self):
        u = URLSetting(url="http://example.com/?ssl_mode=disable")
        self.assertEqual("disable", u.ssl_mode_())

    def test_explicit_ssl_mode_require(self):
        u = URLSetting(url="http://example.com/?ssl_mode=require")
        self.assertEqual("require", u.ssl_mode_())

    def test_explicit_ssl_mode_verify_ca(self):
        u = URLSetting(url="http://example.com/?ssl_mode=verify-ca")
        self.assertEqual("verify-ca", u.ssl_mode_())

    def test_explicit_ssl_mode_verify_full(self):
        u = URLSetting(url="http://example.com/?ssl_mode=verify-full")
        self.assertEqual("verify-full", u.ssl_mode_())

    def test_explicit_ssl_mode_prefer(self):
        u = URLSetting(url="http://example.com/?ssl_mode=prefer")
        self.assertEqual("prefer", u.ssl_mode_())

    def test_no_url(self):
        u = URLSetting()
        self.assertIsNone(u.ssl_mode_())

    def test_unknown_ssl_mode_with_ssl_false_results_in_disable(self):
        # When ssl_mode is invalid (not one of the known values), the logic falls through
        # ssl=false AND check_hostname=false AND ssl_cert_reqs=none → disable
        u = URLSetting(
            url="http://example.com/?ssl_mode=unknown&ssl=false&ssl_check_hostname=false&ssl_cert_reqs=none"
        )
        self.assertEqual("disable", u.ssl_mode_())

    def test_unknown_ssl_mode_with_ssl_true_results_in_require(self):
        u = URLSetting(
            url="http://example.com/?ssl_mode=unknown&ssl=true&ssl_check_hostname=false&ssl_cert_reqs=none"
        )
        self.assertEqual("require", u.ssl_mode_())

    def test_unknown_ssl_mode_check_ca_results_in_verify_ca(self):
        u = URLSetting(
            url="http://example.com/?ssl_mode=unknown&ssl_check_hostname=false"
        )
        self.assertEqual("verify-ca", u.ssl_mode_())

    def test_unknown_ssl_mode_check_hostname_results_in_verify_full(self):
        # ssl_mode=unknown → falls through, check_hostname=true (default) → verify-full
        u = URLSetting(url="http://example.com/?ssl_mode=unknown")
        self.assertEqual("verify-full", u.ssl_mode_())


class TestURLSettingCertificates(TestCase):
    def test_client_cert(self):
        u = URLSetting(url="http://example.com/?ssl_certfile=./client.crt")
        self.assertEqual("./client.crt", u.client_cert_())

    def test_client_key(self):
        u = URLSetting(url="http://example.com/?ssl_keyfile=./client.key")
        self.assertEqual("./client.key", u.client_key_())

    def test_ca_cert(self):
        u = URLSetting(url="http://example.com/?ssl_ca_certs=./ca.crt")
        self.assertEqual("./ca.crt", u.ca_cert_())

    def test_ca_crl(self):
        u = URLSetting(url="http://example.com/?ssl_crlfile=./ca.crl")
        self.assertEqual("./ca.crl", u.ca_crl_())

    def test_no_url(self):
        u = URLSetting()
        self.assertIsNone(u.client_cert_())
        self.assertIsNone(u.client_key_())
        self.assertIsNone(u.ca_cert_())
        self.assertIsNone(u.ca_crl_())

    def test_missing_cert(self):
        u = URLSetting(url="http://example.com/")
        self.assertIsNone(u.client_cert_())


class TestURLSettingEngine(TestCase):
    def test_no_url_no_engine(self):
        u = URLSetting()
        self.assertIsNone(u.engine_())

    def test_http_engine(self):
        u = URLSetting(url="http://example.com/")
        self.assertEqual("http", u.engine_())


class TestURLSettingLoad(TestCase):
    def test_load_from_merger(self):
        u = URLSetting(setting_name="MY_URL")
        merger = _make_merger({"MY_URL": "http://example.com:1234/"})
        u.load(merger)
        self.assertIsNotNone(u.parsed_urls)
        self.assertEqual("1234", u.port_())

    def test_load_already_loaded(self):
        u = URLSetting(url="http://example.com:1111/")
        merger = _make_merger({"MY_URL": "http://example.com:2222/"})
        u.load(merger)
        self.assertEqual("1111", u.port_())

    def test_load_no_setting_name(self):
        u = URLSetting()
        merger = _make_merger({"MY_URL": "http://example.com:3333/"})
        u.load(merger)
        self.assertIsNone(u.parsed_urls)


class TestURLSettingNormalizeEngine(TestCase):
    def test_normalize_known_engine(self):
        engine = DatabaseURL.normalize_engine("postgres")
        self.assertEqual("django.db.backends.postgresql", engine)

    def test_normalize_alias(self):
        engine = DatabaseURL.normalize_engine("psql")
        self.assertEqual("django.db.backends.postgresql", engine)

    def test_normalize_sqlite(self):
        engine = DatabaseURL.normalize_engine("sqlite3")
        self.assertEqual("django.db.backends.sqlite3", engine)


class TestURLSettingDatabase(TestCase):
    def test_database_with_path(self):
        u = URLSetting(url="http://localhost/mydb")
        self.assertEqual("mydb", u.database_())

    def test_database_no_path(self):
        u = URLSetting(url="http://localhost/")
        self.assertIsNone(u.database_())

    def test_database_no_url(self):
        u = URLSetting()
        self.assertIsNone(u.database_())


class TestRedisURLDatabase(TestCase):
    def test_valid_db_0(self):
        r = RedisURL(url="redis://localhost/0")
        self.assertEqual(0, r.database_())

    def test_valid_db_5(self):
        r = RedisURL(url="redis://localhost/5")
        self.assertEqual(5, r.database_())

    def test_no_db(self):
        r = RedisURL(url="redis://localhost/")
        self.assertIsNone(r.database_())

    def test_no_url(self):
        r = RedisURL()
        self.assertIsNone(r.database_())

    def test_invalid_leading_zero(self):
        r = RedisURL(url="redis://localhost/05")
        self.assertIsNone(r.database_())

    def test_invalid_path(self):
        r = RedisURL(url="redis://localhost/notanumber")
        self.assertIsNone(r.database_())


class TestRedisURLScheme(TestCase):
    def test_redis_scheme(self):
        r = RedisURL(url="redis://localhost/0")
        self.assertEqual("redis", r.scheme_())

    def test_rediss_scheme(self):
        r = RedisURL(url="rediss://localhost/0")
        self.assertEqual("rediss", r.scheme_())


class TestAttributeRepr(TestCase):
    def test_repr(self):
        u = DatabaseURL("MY_URL")
        attr = u.hostname(default="localhost")
        r = repr(attr)
        self.assertIn("hostname", r)
        self.assertIn("MY_URL", r)
        self.assertIn("localhost", r)
