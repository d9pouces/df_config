"""Unit tests for df_config/guesses/apps.py."""

import os
import tempfile
from configparser import RawConfigParser
from importlib.metadata import PackageNotFoundError
from unittest import TestCase
from unittest.mock import MagicMock, patch

from df_config.checks import settings_check_results
from df_config.guesses.apps import (
    InstalledApps,
    Middlewares,
    allauth_provider_apps,
    allauth_version,
    installed_apps,
    middlewares,
)


class TestAllauthVersion(TestCase):
    def test_returns_list_of_ints(self):
        with patch("df_config.guesses.apps.version", return_value="0.63.2"):
            result = allauth_version()
        self.assertEqual([0, 63, 2], result)

    def test_package_not_found_returns_fallback(self):
        with patch(
            "df_config.guesses.apps.version", side_effect=PackageNotFoundError()
        ):
            result = allauth_version()
        self.assertEqual([1, 0, 0], result)

    def test_non_numeric_component(self):
        with patch("df_config.guesses.apps.version", return_value="1.0.0a1"):
            result = allauth_version()
        self.assertEqual(1, result[0])
        self.assertEqual(0, result[1])
        self.assertEqual(0, result[2])


class TestAllauthProviderApps(TestCase):
    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def test_no_config_file(self):
        result = allauth_provider_apps(
            {"ALLAUTH_APPLICATIONS_CONFIG": "/nonexistent/path.ini"}
        )
        self.assertEqual([], result)

    def test_valid_config_file_with_apps(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[github]\ndjango_app = allauth.socialaccount.providers.github\n")
            fname = f.name
        try:
            result = allauth_provider_apps({"ALLAUTH_APPLICATIONS_CONFIG": fname})
            self.assertIn("allauth.socialaccount.providers.github", result)
        finally:
            os.unlink(fname)

    def test_valid_config_file_no_django_app(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[github]\nclient_id = abc123\n")
            fname = f.name
        try:
            result = allauth_provider_apps({"ALLAUTH_APPLICATIONS_CONFIG": fname})
            self.assertEqual([], result)
        finally:
            os.unlink(fname)

    def test_invalid_config_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("INVALID\x00CONTENT")
            fname = f.name
        try:
            with patch(
                "df_config.guesses.apps.RawConfigParser.read",
                side_effect=Exception("parse error"),
            ):
                result = allauth_provider_apps({"ALLAUTH_APPLICATIONS_CONFIG": fname})
            self.assertEqual([], result)
            self.assertEqual(1, len(settings_check_results))
        finally:
            os.unlink(fname)


class TestInstalledAppsRepr(TestCase):
    def test_repr(self):
        ia = InstalledApps()
        self.assertIn("installed_apps", repr(ia))


class TestInstalledAppsProcessThirdParties(TestCase):
    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def test_all_disabled(self):
        ia = InstalledApps()
        settings_dict = {
            k: False
            for k in [
                "USE_WEBSOCKETS",
                "USE_DEBUG_TOOLBAR",
                "DEBUG",
                "USE_PIPELINE",
                "USE_PAM_AUTHENTICATION",
                "USE_CORS_HEADER",
                "USE_DAPHNE",
                "USE_DJANGO_PROBES",
                "USE_CSP",
                "USE_PROMETHEUS",
            ]
        }
        result = ia.process_third_parties(settings_dict)
        self.assertEqual([], result)

    def test_enabled_but_package_missing(self):
        ia = InstalledApps()
        with patch("df_config.guesses.apps.is_package_present", return_value=False):
            result = ia.process_third_parties(
                {
                    "USE_WEBSOCKETS": True,
                    "USE_DEBUG_TOOLBAR": False,
                    "DEBUG": False,
                    "USE_PIPELINE": False,
                    "USE_PAM_AUTHENTICATION": False,
                    "USE_CORS_HEADER": False,
                    "USE_DAPHNE": False,
                    "USE_DJANGO_PROBES": False,
                    "USE_CSP": False,
                    "USE_PROMETHEUS": False,
                }
            )
        self.assertEqual([], result)
        self.assertEqual(1, len(settings_check_results))

    def test_enabled_and_package_present(self):
        ia = InstalledApps()
        with patch("df_config.guesses.apps.is_package_present", return_value=True):
            result = ia.process_third_parties(
                {
                    "USE_WEBSOCKETS": True,
                    "USE_DEBUG_TOOLBAR": False,
                    "DEBUG": False,
                    "USE_PIPELINE": False,
                    "USE_PAM_AUTHENTICATION": False,
                    "USE_CORS_HEADER": False,
                    "USE_DAPHNE": False,
                    "USE_DJANGO_PROBES": False,
                    "USE_CSP": False,
                    "USE_PROMETHEUS": False,
                }
            )
        self.assertIn("df_websockets", result)

    def test_csp_old_version_skipped(self):
        ia = InstalledApps()
        with (
            patch("df_config.guesses.apps.is_package_present", return_value=True),
            patch("df_config.guesses.apps.version", return_value="3.7.0"),
        ):
            result = ia.process_third_parties(
                {
                    "USE_WEBSOCKETS": False,
                    "USE_DEBUG_TOOLBAR": False,
                    "DEBUG": False,
                    "USE_PIPELINE": False,
                    "USE_PAM_AUTHENTICATION": False,
                    "USE_CORS_HEADER": False,
                    "USE_DAPHNE": False,
                    "USE_DJANGO_PROBES": False,
                    "USE_CSP": True,
                    "USE_PROMETHEUS": False,
                }
            )
        # csp <= 3 → skipped (continues)
        self.assertNotIn("csp", result)

    def test_csp_package_not_found_skipped(self):
        ia = InstalledApps()
        # When version() raises PackageNotFoundError → continue (csp not added)
        with (
            patch("df_config.guesses.apps.is_package_present", return_value=True),
            patch("df_config.guesses.apps.version", side_effect=PackageNotFoundError()),
        ):
            result = ia.process_third_parties(
                {
                    "USE_WEBSOCKETS": False,
                    "USE_DEBUG_TOOLBAR": False,
                    "DEBUG": False,
                    "USE_PIPELINE": False,
                    "USE_PAM_AUTHENTICATION": False,
                    "USE_CORS_HEADER": False,
                    "USE_DAPHNE": False,
                    "USE_DJANGO_PROBES": False,
                    "USE_CSP": True,
                    "USE_PROMETHEUS": False,
                }
            )
        self.assertNotIn("csp", result)


class TestInstalledAppsProcessDjangoAllauth(TestCase):
    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def test_no_allauth_no_apps(self):
        ia = InstalledApps()
        result = ia.process_django_allauth(
            {"USE_ALL_AUTH": False, "ALLAUTH_PROVIDER_APPS": []}
        )
        self.assertEqual([], result)

    def test_allauth_not_installed(self):
        ia = InstalledApps()
        with patch(
            "df_config.guesses.apps.version", side_effect=PackageNotFoundError()
        ):
            result = ia.process_django_allauth(
                {"USE_ALL_AUTH": True, "ALLAUTH_PROVIDER_APPS": []}
            )
        self.assertEqual([], result)
        self.assertEqual(1, len(settings_check_results))

    def test_allauth_installed_no_providers(self):
        ia = InstalledApps()
        with (
            patch("df_config.guesses.apps.version", return_value="0.63.0"),
            patch("df_config.guesses.apps.is_package_present", return_value=False),
        ):
            result = ia.process_django_allauth(
                {"USE_ALL_AUTH": True, "ALLAUTH_PROVIDER_APPS": []}
            )
        self.assertIn("allauth", result)
        self.assertIn("allauth.account", result)

    def test_allauth_with_mfa(self):
        ia = InstalledApps()

        def fake_present(pkg):
            return pkg in ("pypng", "qrcode")

        with (
            patch("df_config.guesses.apps.version", return_value="0.63.0"),
            patch(
                "df_config.guesses.apps.is_package_present", side_effect=fake_present
            ),
        ):
            result = ia.process_django_allauth(
                {"USE_ALL_AUTH": True, "ALLAUTH_PROVIDER_APPS": []}
            )
        self.assertIn("allauth.mfa", result)

    def test_allauth_with_social_apps(self):
        ia = InstalledApps()
        social_app = "allauth.socialaccount.providers.github"
        ia.social_apps = {social_app}
        with (
            patch("df_config.guesses.apps.version", return_value="0.63.0"),
            patch("df_config.guesses.apps.is_package_present", return_value=False),
        ):
            result = ia.process_django_allauth(
                {
                    "USE_ALL_AUTH": True,
                    "ALLAUTH_PROVIDER_APPS": [social_app],
                }
            )
        self.assertIn("allauth.socialaccount", result)
        self.assertIn(social_app, result)


class TestInstalledAppsCall(TestCase):
    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def _base_settings(self):
        return {
            "SESSION_ENGINE": "django.contrib.sessions.backends.cache",
            "USE_ALL_AUTH": False,
            "ALLAUTH_PROVIDER_APPS": [],
            "USE_WEBSOCKETS": False,
            "USE_DEBUG_TOOLBAR": False,
            "DEBUG": False,
            "USE_PIPELINE": False,
            "USE_PAM_AUTHENTICATION": False,
            "USE_CORS_HEADER": False,
            "USE_DAPHNE": False,
            "USE_DJANGO_PROBES": False,
            "USE_CSP": False,
            "USE_PROMETHEUS": False,
            "DF_ADMIN_APP_CONFIG": "django.contrib.admin",
            "DF_INSTALLED_APPS": [],
        }

    def test_call_basic(self):
        ia = InstalledApps()
        with patch("df_config.guesses.apps.is_package_present", return_value=False):
            result = ia(self._base_settings())
        self.assertIn("df_config", result)

    def test_call_with_db_sessions(self):
        ia = InstalledApps()
        settings = self._base_settings()
        settings["SESSION_ENGINE"] = "django.contrib.sessions.backends.db"
        with patch("df_config.guesses.apps.is_package_present", return_value=False):
            result = ia(settings)
        self.assertIn("django.contrib.sessions", result)


class TestMiddlewaresRepr(TestCase):
    def test_repr(self):
        m = Middlewares()
        self.assertIn("middlewares", repr(m))


class TestMiddlewaresProcessThirdParties(TestCase):
    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def test_all_disabled(self):
        m = Middlewares()
        settings_dict = {
            k: False
            for k in [
                "USE_WHITENOISE",
                "USE_WEBSOCKETS",
                "USE_CSP",
                "USE_CORS_HEADER",
                "USE_ALL_AUTH",
            ]
        }
        result = m.process_third_parties(settings_dict)
        self.assertEqual([], result)

    def test_enabled_but_missing(self):
        m = Middlewares()
        with patch("df_config.guesses.apps.is_package_present", return_value=False):
            result = m.process_third_parties(
                {
                    "USE_WHITENOISE": True,
                    "USE_WEBSOCKETS": False,
                    "USE_CSP": False,
                    "USE_CORS_HEADER": False,
                    "USE_ALL_AUTH": False,
                }
            )
        self.assertEqual([], result)
        self.assertEqual(1, len(settings_check_results))

    def test_enabled_and_present(self):
        m = Middlewares()
        with patch("df_config.guesses.apps.is_package_present", return_value=True):
            result = m.process_third_parties(
                {
                    "USE_WHITENOISE": True,
                    "USE_WEBSOCKETS": False,
                    "USE_CSP": False,
                    "USE_CORS_HEADER": False,
                    "USE_ALL_AUTH": False,
                }
            )
        self.assertIn("whitenoise.middleware.WhiteNoiseMiddleware", result)


class TestMiddlewaresCall(TestCase):
    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def _base_settings(self):
        return {
            "USE_WHITENOISE": False,
            "USE_WEBSOCKETS": False,
            "USE_CSP": False,
            "USE_CORS_HEADER": False,
            "USE_ALL_AUTH": False,
            "USE_PROMETHEUS": False,
            "USE_DEBUG_TOOLBAR": False,
            "INSTALLED_APPS": [],
            "DF_MIDDLEWARE": [],
        }

    def test_call_basic(self):
        m = Middlewares()
        with patch("df_config.guesses.apps.is_package_present", return_value=False):
            result = m(self._base_settings())
        self.assertIn("django.middleware.common.CommonMiddleware", result)

    def test_call_with_debug_toolbar(self):
        m = Middlewares()
        settings = self._base_settings()
        settings["USE_DEBUG_TOOLBAR"] = True
        with patch("df_config.guesses.apps.is_package_present", return_value=False):
            result = m(settings)
        self.assertIn("debug_toolbar.middleware.DebugToolbarMiddleware", result)

    def test_call_with_prometheus(self):
        m = Middlewares()
        settings = self._base_settings()
        settings["USE_PROMETHEUS"] = True
        with patch("df_config.guesses.apps.is_package_present", return_value=False):
            result = m(settings)
        self.assertIn("django_prometheus.middleware.PrometheusBeforeMiddleware", result)
        self.assertIn("django_prometheus.middleware.PrometheusAfterMiddleware", result)

    def test_call_with_allauth_usersessions(self):
        m = Middlewares()
        settings = self._base_settings()
        settings["INSTALLED_APPS"] = ["allauth.usersessions"]
        with patch("df_config.guesses.apps.is_package_present", return_value=False):
            result = m(settings)
        self.assertIn("allauth.usersessions.middleware.UserSessionsMiddleware", result)
