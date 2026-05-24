"""Unit tests for df_config/guesses/social_providers.py."""

import os
import sys
import tempfile
from collections import OrderedDict
from unittest import TestCase
from unittest.mock import MagicMock, patch

from df_config.guesses.social_providers import (
    SOCIAL_PROVIDER_APPS,
    SOCIAL_PROVIDER_CONFIGURATIONS,
    FacebookConfiguration,
    GithubConfiguration,
    SocialProviderConfiguration,
    get_available_configurations,
    get_loaded_configurations,
    get_social_provider_apps,
)


class TestSocialProviderConfiguration(TestCase):
    def _make_config(self, **kwargs):
        defaults = {
            "provider_id": "myprovider",
            "provider_name": "My Provider",
            "provider_app": "allauth.socialaccount.providers.myprovider",
        }
        defaults.update(kwargs)
        return SocialProviderConfiguration(**defaults)

    def test_str(self):
        cfg = self._make_config(provider_name="GitHub")
        self.assertEqual("GitHub", str(cfg))

    def test_name_property(self):
        cfg = self._make_config(provider_name="GitHub")
        self.assertEqual("df-GitHub", cfg.name)

    def test_query_kwargs(self):
        cfg = self._make_config(provider_id="github", provider_name="GitHub")
        result = cfg.query_kwargs()
        self.assertEqual("df-GitHub", result["name"])
        self.assertEqual("github", result["provider"])


class TestGithubConfiguration(TestCase):
    def test_id(self):
        self.assertEqual("github", GithubConfiguration.id)

    def test_attributes(self):
        self.assertIn("client_id", GithubConfiguration.attributes)
        self.assertIn("secret", GithubConfiguration.attributes)


class TestFacebookConfiguration(TestCase):
    def test_id(self):
        self.assertEqual("facebook", FacebookConfiguration.id)

    def test_attributes(self):
        self.assertIn("client_id", FacebookConfiguration.attributes)
        self.assertIn("secret", FacebookConfiguration.attributes)


class TestGetSocialProviderApps(TestCase):
    def test_no_allauth_returns_empty_set(self):
        with patch.dict(
            sys.modules,
            {
                "allauth": None,
                "allauth.socialaccount": None,
                "allauth.socialaccount.providers": None,
            },
        ):
            result = get_social_provider_apps()
        self.assertIsInstance(result, set)

    def test_with_allauth_returns_set_of_strings(self):
        # If allauth IS installed, each result should be a string
        result = get_social_provider_apps()
        self.assertIsInstance(result, set)
        for item in result:
            self.assertIsInstance(item, str)


class TestGetAvailableConfigurations(TestCase):
    def test_empty_when_no_provider_apps(self):
        with patch("df_config.guesses.social_providers.SOCIAL_PROVIDER_APPS", set()):
            result = get_available_configurations()
        self.assertIsInstance(result, dict)

    def test_import_error_is_silenced(self):
        fake_app = "allauth.socialaccount.providers.nonexistent"
        with patch(
            "df_config.guesses.social_providers.SOCIAL_PROVIDER_APPS", {fake_app}
        ):
            result = get_available_configurations()
        self.assertIsInstance(result, dict)

    def test_returns_configured_provider(self):
        fake_app = "allauth.socialaccount.providers.github"
        mock_provider = MagicMock()
        mock_provider.id = "github"
        mock_provider.name = "GitHub"
        mock_module = MagicMock()
        mock_module.provider_classes = [mock_provider]
        with (
            patch(
                "df_config.guesses.social_providers.SOCIAL_PROVIDER_APPS", {fake_app}
            ),
            patch(
                "df_config.guesses.social_providers.importlib.import_module",
                return_value=mock_module,
            ),
        ):
            result = get_available_configurations()
        self.assertIn("github", result)
        cfg = result["github"]
        self.assertIsInstance(cfg, GithubConfiguration)

    def test_generic_config_for_unknown_provider(self):
        fake_app = "allauth.socialaccount.providers.unknown"
        mock_provider = MagicMock()
        mock_provider.id = "unknown_provider"
        mock_provider.name = "Unknown"
        mock_module = MagicMock()
        mock_module.provider_classes = [mock_provider]
        with (
            patch(
                "df_config.guesses.social_providers.SOCIAL_PROVIDER_APPS", {fake_app}
            ),
            patch(
                "df_config.guesses.social_providers.importlib.import_module",
                return_value=mock_module,
            ),
        ):
            result = get_available_configurations()
        self.assertIn("unknown_provider", result)
        self.assertIsInstance(result["unknown_provider"], SocialProviderConfiguration)


class TestGetLoadedConfigurations(TestCase):
    def test_no_config_file(self):
        with patch("df_config.guesses.social_providers.SOCIAL_PROVIDER_APPS", set()):
            from django.test import override_settings

            with override_settings(ALLAUTH_APPLICATIONS_CONFIG="/nonexistent/path.ini"):
                result = get_loaded_configurations()
        self.assertIsInstance(result, OrderedDict)
        self.assertEqual(0, len(result))

    def test_with_config_file(self):
        fake_app = "allauth.socialaccount.providers.github"
        mock_provider = MagicMock()
        mock_provider.id = "github"
        mock_provider.name = "GitHub"
        mock_module = MagicMock()
        mock_module.provider_classes = [mock_provider]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[github]\nclient_id = myid\nsecret = mysecret\n")
            fname = f.name

        try:
            from django.test import override_settings

            with (
                patch(
                    "df_config.guesses.social_providers.SOCIAL_PROVIDER_APPS",
                    {fake_app},
                ),
                patch(
                    "df_config.guesses.social_providers.importlib.import_module",
                    return_value=mock_module,
                ),
                override_settings(ALLAUTH_APPLICATIONS_CONFIG=fname),
            ):
                result = get_loaded_configurations()
            self.assertIn("github", result)
            cfg = result["github"]
            self.assertEqual("myid", cfg.values.get("client_id"))
        finally:
            os.unlink(fname)

    def test_unknown_section_skipped(self):
        fake_app = "allauth.socialaccount.providers.github"
        mock_module = MagicMock()
        mock_module.provider_classes = []

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[nonexistent_provider]\nclient_id = myid\n")
            fname = f.name

        try:
            from django.test import override_settings

            with (
                patch(
                    "df_config.guesses.social_providers.SOCIAL_PROVIDER_APPS",
                    {fake_app},
                ),
                patch(
                    "df_config.guesses.social_providers.importlib.import_module",
                    return_value=mock_module,
                ),
                override_settings(ALLAUTH_APPLICATIONS_CONFIG=fname),
            ):
                result = get_loaded_configurations()
            self.assertNotIn("nonexistent_provider", result)
        finally:
            os.unlink(fname)


class TestSocialProviderAppsGlobal(TestCase):
    def test_is_set(self):
        self.assertIsInstance(SOCIAL_PROVIDER_APPS, set)

    def test_configurations_list(self):
        self.assertIsInstance(SOCIAL_PROVIDER_CONFIGURATIONS, list)
        self.assertIn(GithubConfiguration, SOCIAL_PROVIDER_CONFIGURATIONS)
