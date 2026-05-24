"""Unit tests for df_config/guesses/misc.py — 100% coverage."""

import sys
from importlib.metadata import PackageNotFoundError
from unittest import TestCase
from unittest.mock import MagicMock, patch

from df_config.checks import settings_check_results
from df_config.guesses.misc import (
    AutocreateSecretKey,
    ExcludedDjangoCommands,
    allowed_hosts,
    csp_connect,
    csrf_trusted_origins,
    excluded_django_commands,
    from_email,
    generate_secret_key,
    get_asgi_application,
    get_command_name,
    get_hostname,
    get_wsgi_application,
    is_valid_email,
    project_name,
    required_packages,
    secure_hsts_seconds,
    smart_base_url,
    smart_listen_address,
    template_setting,
    url_parse_prefix,
    url_parse_server_name,
    url_parse_server_port,
    url_parse_server_protocol,
    url_parse_ssl,
    use_sentry,
    use_x_forwarded_for,
    web_server,
)


class TestGetCommandName(TestCase):
    def test_argv_len_2_or_more(self):
        with patch.object(sys, "argv", ["prog", "runserver"]):
            self.assertEqual("runserver", get_command_name({}))

    def test_argv_len_1(self):
        with patch.object(sys, "argv", ["prog"]):
            self.assertEqual("prog", get_command_name({}))

    def test_argv_len_0(self):
        with patch.object(sys, "argv", []):
            self.assertEqual("undefined", get_command_name({}))


class TestGetHostname(TestCase):
    def test_get_hostname(self):
        with patch("socket.gethostname", return_value="myhost"):
            self.assertEqual("myhost", get_hostname({}))


class TestSmartBaseUrl(TestCase):
    def test_with_heroku(self):
        result = smart_base_url(
            {"HEROKU_APP_NAME": "myapp", "LISTEN_ADDRESS": "0.0.0.0:8000"}
        )
        self.assertEqual("https://myapp.herokuapp.com/", result)

    def test_without_heroku(self):
        result = smart_base_url(
            {"HEROKU_APP_NAME": "", "LISTEN_ADDRESS": "0.0.0.0:8000"}
        )
        self.assertEqual("http://0.0.0.0:8000/", result)


class TestSmartListenAddress(TestCase):
    def test_int_port(self):
        result = smart_listen_address({"LISTEN_PORT": 9000})
        self.assertEqual("0.0.0.0:9000", result)

    def test_str_port_valid(self):
        result = smart_listen_address({"LISTEN_PORT": "9001"})
        self.assertEqual("0.0.0.0:9001", result)

    def test_str_port_invalid(self):
        result = smart_listen_address({"LISTEN_PORT": "abc"})
        self.assertEqual("localhost:8000", result)

    def test_int_port_out_of_range(self):
        result = smart_listen_address({"LISTEN_PORT": 0})
        self.assertEqual("localhost:8000", result)

    def test_str_port_out_of_range(self):
        result = smart_listen_address({"LISTEN_PORT": "99999"})
        self.assertEqual("localhost:8000", result)


class TestTemplateSetting(TestCase):
    def test_debug_true(self):
        result = template_setting(
            {
                "DEBUG": True,
                "TEMPLATE_DIRS": [],
                "TEMPLATE_CONTEXT_PROCESSORS": ["ctx"],
            }
        )
        self.assertEqual(1, len(result))
        self.assertTrue(result[0]["OPTIONS"]["debug"])

    def test_debug_false(self):
        result = template_setting(
            {
                "DEBUG": False,
                "TEMPLATE_DIRS": [],
                "TEMPLATE_CONTEXT_PROCESSORS": ["ctx"],
            }
        )
        self.assertEqual(1, len(result))
        self.assertFalse(result[0]["OPTIONS"]["debug"])


class TestAllowedHosts(TestCase):
    def test_specific_ip(self):
        result = allowed_hosts(
            {
                "SERVER_NAME": "example.com",
                "LISTEN_ADDRESS": "192.168.1.1:8000",
            }
        )
        self.assertIn("192.168.1.1", result)
        self.assertIn("example.com", result)

    def test_wildcard_ip(self):
        result = allowed_hosts(
            {
                "SERVER_NAME": "example.com",
                "LISTEN_ADDRESS": "0.0.0.0:8000",
            }
        )
        self.assertNotIn("0.0.0.0", result)
        self.assertIn("example.com", result)

    def test_ipv6_wildcard(self):
        result = allowed_hosts(
            {
                "SERVER_NAME": "example.com",
                "LISTEN_ADDRESS": ":::8000",
            }
        )
        self.assertIn("example.com", result)


class TestCsrfTrustedOrigins(TestCase):
    def _call(self, port, use_ssl):
        return csrf_trusted_origins(
            {
                "SERVER_NAME": "example.com",
                "SERVER_PORT": port,
                "USE_SSL": use_ssl,
            }
        )

    def test_https_port_443(self):
        result = self._call(443, True)
        self.assertIn("https://example.com", result)

    def test_http_port_80(self):
        result = self._call(80, False)
        self.assertIn("http://example.com", result)

    def test_https_non_standard_port(self):
        result = self._call(8443, True)
        self.assertIn("https://example.com:8443", result)

    def test_http_non_standard_port(self):
        result = self._call(8080, False)
        self.assertIn("http://example.com:8080", result)

    def test_django_3_compat(self):
        import django

        with patch.object(django, "VERSION", (3, 2, 20, "final", 0)):
            result = self._call(80, False)
        self.assertIn("example.com", result)
        self.assertIn("example.com:80", result)


class TestSecureHstsSeconds(TestCase):
    def test_with_ssl(self):
        self.assertGreater(secure_hsts_seconds({"USE_SSL": True}), 0)

    def test_without_ssl(self):
        self.assertEqual(0, secure_hsts_seconds({"USE_SSL": False}))


class TestUrlParseFunctions(TestCase):
    def test_server_name(self):
        self.assertEqual(
            "demo.example.org",
            url_parse_server_name({"SERVER_BASE_URL": "https://demo.example.org/"}),
        )

    def test_server_name_no_hostname(self):
        self.assertEqual(
            "localhost",
            url_parse_server_name({"SERVER_BASE_URL": "http://"}),
        )

    def test_server_port_explicit(self):
        self.assertEqual(
            8010,
            url_parse_server_port(
                {"SERVER_BASE_URL": "https://demo.example.org:8010/", "USE_SSL": True}
            ),
        )

    def test_server_port_ssl_default(self):
        self.assertEqual(
            443,
            url_parse_server_port(
                {"SERVER_BASE_URL": "https://demo.example.org/", "USE_SSL": True}
            ),
        )

    def test_server_port_http_default(self):
        self.assertEqual(
            80,
            url_parse_server_port(
                {"SERVER_BASE_URL": "http://demo.example.org/", "USE_SSL": False}
            ),
        )

    def test_server_protocol_https(self):
        self.assertEqual("https", url_parse_server_protocol({"USE_SSL": True}))

    def test_server_protocol_http(self):
        self.assertEqual("http", url_parse_server_protocol({"USE_SSL": False}))

    def test_url_parse_prefix_with_slash(self):
        self.assertEqual(
            "/demo/",
            url_parse_prefix({"SERVER_BASE_URL": "https://demo.example.org/demo/"}),
        )

    def test_url_parse_prefix_without_slash(self):
        self.assertEqual(
            "/", url_parse_prefix({"SERVER_BASE_URL": "https://demo.example.org:8010"})
        )

    def test_url_parse_prefix_root(self):
        self.assertEqual(
            "/", url_parse_prefix({"SERVER_BASE_URL": "http://demo.example.org/"})
        )

    def test_url_parse_ssl_true(self):
        self.assertTrue(url_parse_ssl({"SERVER_BASE_URL": "https://demo.example.org/"}))

    def test_url_parse_ssl_false(self):
        self.assertFalse(url_parse_ssl({"SERVER_BASE_URL": "http://demo.example.org/"}))


class TestUseXForwardedFor(TestCase):
    def test_same_port(self):
        self.assertFalse(
            use_x_forwarded_for(
                {"SERVER_PORT": 8000, "LISTEN_ADDRESS": "localhost:8000"}
            )
        )

    def test_different_port(self):
        self.assertTrue(
            use_x_forwarded_for(
                {"SERVER_PORT": 443, "LISTEN_ADDRESS": "localhost:8000"}
            )
        )

    def test_invalid_port(self):
        from django.core.exceptions import ImproperlyConfigured

        with self.assertRaises(ImproperlyConfigured):
            use_x_forwarded_for({"SERVER_PORT": 443, "LISTEN_ADDRESS": "localhost:abc"})


class TestProjectName(TestCase):
    def test_project_name(self):
        self.assertEqual("My Project", project_name({"DF_MODULE_NAME": "my_project"}))


class TestAutocreateSecretKey(TestCase):
    def test_init(self):
        obj = AutocreateSecretKey("/tmp/secret.txt")
        self.assertIsNotNone(obj)


class TestGenerateSecretKey(TestCase):
    def test_django_not_ready(self):
        key = generate_secret_key(django_ready=False, length=20)
        self.assertEqual(20, len(key))

    def test_django_ready(self):
        from django.conf import settings

        key = generate_secret_key(django_ready=True)
        self.assertEqual(settings.SECRET_KEY, key)


class TestRequiredPackages(TestCase):
    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def test_package_found_with_requires(self):
        mock_dist = MagicMock()
        mock_dist.requires = ["some-dep>=1.0"]
        with patch("df_config.guesses.misc.distribution") as mock_dist_fn:
            mock_dist_fn.side_effect = [mock_dist, PackageNotFoundError()]
            result = required_packages({"DF_MODULE_NAME": "test-pkg"})
        self.assertIn("test-pkg", result)

    def test_package_found_no_requires(self):
        mock_dist = MagicMock()
        mock_dist.requires = None
        with patch("df_config.guesses.misc.distribution", return_value=mock_dist):
            result = required_packages({"DF_MODULE_NAME": "test-pkg"})
        self.assertIn("test-pkg", result)

    def test_package_not_found(self):
        with patch(
            "df_config.guesses.misc.distribution", side_effect=PackageNotFoundError()
        ):
            result = required_packages({"DF_MODULE_NAME": "nonexistent-xyz"})
        # The name is yielded before distribution() raises, so it IS in the result
        self.assertIn("nonexistent-xyz", result)
        self.assertEqual(1, len(settings_check_results))

    def test_package_generic_exception(self):
        with patch(
            "df_config.guesses.misc.distribution", side_effect=RuntimeError("oops")
        ):
            result = required_packages({"DF_MODULE_NAME": "test-pkg"})
        # The name is yielded before distribution() raises, so it IS in the result
        self.assertIn("test-pkg", result)
        self.assertEqual(1, len(settings_check_results))

    def test_already_checked(self):
        """Duplicate requirement names are not re-processed."""
        mock_dist = MagicMock()
        # requires references itself → should not recurse infinitely
        mock_dist.requires = ["test-pkg>=1.0"]
        with patch("df_config.guesses.misc.distribution", return_value=mock_dist):
            result = required_packages({"DF_MODULE_NAME": "test-pkg"})
        self.assertIn("test-pkg", result)


class TestExcludedDjangoCommands(TestCase):
    def test_production_no_celery_no_debug(self):
        result = excluded_django_commands(
            {
                "DEVELOPMENT": False,
                "USE_CELERY": False,
                "DEBUG": False,
            }
        )
        self.assertIn("startapp", result)
        self.assertIn("celery", result)
        self.assertIn("runserver", result)

    def test_development_with_celery_debug(self):
        result = excluded_django_commands(
            {
                "DEVELOPMENT": True,
                "USE_CELERY": True,
                "DEBUG": True,
            }
        )
        self.assertNotIn("startapp", result)
        self.assertNotIn("celery", result)
        self.assertNotIn("runserver", result)

    def test_production_with_celery_debug(self):
        result = excluded_django_commands(
            {
                "DEVELOPMENT": False,
                "USE_CELERY": True,
                "DEBUG": True,
            }
        )
        self.assertIn("startapp", result)
        self.assertNotIn("celery", result)
        self.assertNotIn("runserver", result)

    def test_repr(self):
        r = repr(excluded_django_commands)
        self.assertIn("excluded_django_commands", r)


class TestGetAsgiApplication(TestCase):
    def test_with_websockets(self):
        result = get_asgi_application({"USE_WEBSOCKETS": True})
        self.assertIn("df_websockets", result)

    def test_without_websockets(self):
        result = get_asgi_application({"USE_WEBSOCKETS": False})
        self.assertIn("df_config", result)


class TestGetWsgiApplication(TestCase):
    def test_wsgi(self):
        result = get_wsgi_application({})
        self.assertIn("df_config", result)


class TestUseSentry(TestCase):
    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def test_no_dsn(self):
        result = use_sentry({"SENTRY_DSN": "", "USE_CELERY": False, "DEBUG": False})
        self.assertFalse(result)

    def test_dsn_but_no_sentry_sdk(self):
        with patch("df_config.guesses.misc.is_package_present", return_value=False):
            result = use_sentry(
                {
                    "SENTRY_DSN": "https://key@sentry.io/1",
                    "USE_CELERY": False,
                    "DEBUG": False,
                }
            )
        self.assertFalse(result)
        self.assertEqual(1, len(settings_check_results))

    def test_dsn_with_sentry_sdk_no_celery(self):
        mock_sentry = MagicMock()
        mock_django_integration = MagicMock()
        mock_django_module = MagicMock()
        mock_django_module.DjangoIntegration = mock_django_integration
        with (
            patch("df_config.guesses.misc.is_package_present", return_value=True),
            patch.dict(
                sys.modules,
                {
                    "sentry_sdk": mock_sentry,
                    "sentry_sdk.integrations": MagicMock(),
                    "sentry_sdk.integrations.django": mock_django_module,
                },
            ),
        ):
            result = use_sentry(
                {
                    "SENTRY_DSN": "https://key@sentry.io/1",
                    "USE_CELERY": False,
                    "DEBUG": False,
                }
            )
        self.assertTrue(result)
        mock_sentry.init.assert_called_once()

    def test_dsn_with_sentry_sdk_and_celery(self):
        mock_sentry = MagicMock()
        mock_django_integration = MagicMock()
        mock_celery_integration = MagicMock()
        mock_django_module = MagicMock()
        mock_django_module.DjangoIntegration = mock_django_integration
        mock_celery_module = MagicMock()
        mock_celery_module.CeleryIntegration = mock_celery_integration
        with (
            patch("df_config.guesses.misc.is_package_present", return_value=True),
            patch.dict(
                sys.modules,
                {
                    "sentry_sdk": mock_sentry,
                    "sentry_sdk.integrations": MagicMock(),
                    "sentry_sdk.integrations.django": mock_django_module,
                    "sentry_sdk.integrations.celery": mock_celery_module,
                },
            ),
        ):
            result = use_sentry(
                {
                    "SENTRY_DSN": "https://key@sentry.io/1",
                    "USE_CELERY": True,
                    "DEBUG": True,
                }
            )
        self.assertTrue(result)


class TestWebServer(TestCase):
    def test_daphne_present(self):
        def mock_present(name):
            return name == "daphne"

        with patch(
            "df_config.guesses.misc.is_package_present", side_effect=mock_present
        ):
            result = web_server({})
        self.assertEqual("daphne", result)

    def test_gunicorn_present(self):
        def mock_present(name):
            return name == "gunicorn"

        with patch(
            "df_config.guesses.misc.is_package_present", side_effect=mock_present
        ):
            result = web_server({})
        self.assertEqual("gunicorn", result)

    def test_none_present(self):
        with patch("df_config.guesses.misc.is_package_present", return_value=False):
            result = web_server({})
        self.assertEqual("gunicorn", result)


class TestIsValidEmail(TestCase):
    def test_valid(self):
        self.assertTrue(is_valid_email("user@example.com"))

    def test_no_at(self):
        self.assertFalse(is_valid_email("userexample.com"))

    def test_empty(self):
        self.assertFalse(is_valid_email(""))

    def test_no_domain_dot(self):
        self.assertFalse(is_valid_email("user@localhost"))

    def test_too_long(self):
        self.assertFalse(is_valid_email("a" * 320 + "@example.com"))

    def test_invalid_user_part(self):
        self.assertFalse(is_valid_email("user name@example.com"))


class TestFromEmail(TestCase):
    def test_valid_email_user(self):
        result = from_email(
            {"EMAIL_HOST_USER": "admin@example.com", "SERVER_NAME": "myserver.com"}
        )
        self.assertEqual("admin@example.com", result)

    def test_invalid_email_user(self):
        result = from_email({"EMAIL_HOST_USER": "admin", "SERVER_NAME": "myserver.com"})
        self.assertEqual("webmaster@myserver.com", result)


class TestCspConnect(TestCase):
    def test_no_websockets(self):
        result = csp_connect(
            {
                "USE_SSL": False,
                "USE_WEBSOCKETS": False,
                "SERVER_NAME": "ex.com",
                "SERVER_PORT": 80,
            }
        )
        self.assertEqual(["'self'"], result)

    def test_websockets_ssl(self):
        result = csp_connect(
            {
                "USE_SSL": True,
                "USE_WEBSOCKETS": True,
                "SERVER_NAME": "ex.com",
                "SERVER_PORT": 443,
            }
        )
        self.assertIn("wss://ex.com:443", result)

    def test_websockets_no_ssl(self):
        result = csp_connect(
            {
                "USE_SSL": False,
                "USE_WEBSOCKETS": True,
                "SERVER_NAME": "ex.com",
                "SERVER_PORT": 80,
            }
        )
        self.assertIn("ws://ex.com:80", result)
