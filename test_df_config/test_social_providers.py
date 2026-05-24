"""Tests for df_config/guesses/social_providers.py."""

import os
import tempfile
from collections import OrderedDict
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from df_config.guesses.social_providers import (
    SOCIAL_PROVIDER_APPS,
    SOCIAL_PROVIDER_CONFIGURATIONS,
    FacebookConfiguration,
    GithubConfiguration,
    SocialProviderConfiguration,
    get_available_configurations,
    get_loaded_configurations,
    get_social_provider_apps,
    migrate,
)


class TestSocialProviderConfigurationBasic(TestCase):
    """Test SocialProviderConfiguration basic properties."""

    def setUp(self):
        self.config = SocialProviderConfiguration(
            provider_id="testprovider",
            provider_name="Test Provider",
            provider_app="allauth.socialaccount.providers.test",
        )

    def test_str(self):
        self.assertEqual(str(self.config), "Test Provider")

    def test_name_property(self):
        self.assertEqual(self.config.name, "df-Test Provider")

    def test_query_kwargs(self):
        result = self.config.query_kwargs()
        self.assertEqual(
            result, {"name": "df-Test Provider", "provider": "testprovider"}
        )

    def test_help_text(self):
        mock_merger = MagicMock()
        mock_merger.settings = {
            "SERVER_BASE_URL": "https://example.com/",
            "SERVER_NAME": "example.com",
            "DF_PROJECT_NAME": "MyProject",
        }
        # help_text imports merger locally from df_config.config.base
        with patch("df_config.config.base.merger", mock_merger):
            text = self.config.help_text
        self.assertIsInstance(text, str)

    def test_help_text_with_values(self):
        config = SocialProviderConfiguration(
            provider_id="myprovider",
            provider_name="My Provider",
            provider_app="allauth.socialaccount.providers.myprovider",
            values={"client_id": "abc123"},
        )
        mock_merger = MagicMock()
        mock_merger.settings = {
            "SERVER_BASE_URL": "https://mysite.com/",
            "SERVER_NAME": "mysite.com",
            "DF_PROJECT_NAME": "SomeApp",
            "provider_id": "myprovider",
            "provider_name": "My Provider",
        }
        with patch("df_config.config.base.merger", mock_merger):
            text = config.help_text
        self.assertIsInstance(text, str)


class TestGithubAndFacebookConfigurations(TestCase):
    """Test GithubConfiguration and FacebookConfiguration."""

    def test_github_id(self):
        self.assertEqual(GithubConfiguration.id, "github")

    def test_github_attributes(self):
        self.assertIn("client_id", GithubConfiguration.attributes)
        self.assertIn("secret", GithubConfiguration.attributes)

    def test_facebook_id(self):
        self.assertEqual(FacebookConfiguration.id, "facebook")

    def test_github_help_text(self):
        config = GithubConfiguration(
            provider_id="github",
            provider_name="Github",
            provider_app="allauth.socialaccount.providers.github",
        )
        mock_merger = MagicMock()
        mock_merger.settings = {
            "SERVER_BASE_URL": "https://example.com/",
            "SERVER_NAME": "example.com",
            "DF_PROJECT_NAME": "TestProject",
        }
        with patch("df_config.config.base.merger", mock_merger):
            text = config.help_text
        self.assertIn("example.com", text)
        self.assertIn("TestProject", text)

    def test_social_provider_configurations_list(self):
        self.assertIn(GithubConfiguration, SOCIAL_PROVIDER_CONFIGURATIONS)


class TestGetSocialProviderApps(TestCase):
    """Test get_social_provider_apps function."""

    def test_returns_set(self):
        result = get_social_provider_apps()
        self.assertIsInstance(result, set)

    def test_import_error_returns_empty_set(self):
        with patch.dict("sys.modules", {"allauth.socialaccount.providers": None}):
            result = get_social_provider_apps()
        self.assertEqual(result, set())

    def test_module_level_apps_is_set(self):
        self.assertIsInstance(SOCIAL_PROVIDER_APPS, set)


class TestGetAvailableConfigurations(TestCase):
    """Test get_available_configurations function."""

    def test_returns_dict(self):
        with patch("df_config.guesses.social_providers.SOCIAL_PROVIDER_APPS", []):
            result = get_available_configurations()
        self.assertIsInstance(result, dict)

    def test_with_mocked_providers(self):
        mock_provider_cls = MagicMock()
        mock_provider_cls.id = "mockprovider"
        mock_provider_cls.name = "Mock Provider"

        mock_provider_module = MagicMock()
        mock_provider_module.provider_classes = [mock_provider_cls]

        with patch(
            "df_config.guesses.social_providers.SOCIAL_PROVIDER_APPS",
            ["allauth.socialaccount.providers.mock"],
        ):
            with patch("importlib.import_module", return_value=mock_provider_module):
                result = get_available_configurations()
        self.assertIn("mockprovider", result)
        config = result["mockprovider"]
        self.assertEqual(config.provider_id, "mockprovider")

    def test_import_error_skipped(self):
        with patch(
            "df_config.guesses.social_providers.SOCIAL_PROVIDER_APPS",
            ["allauth.socialaccount.providers.nonexistent"],
        ):
            with patch("importlib.import_module", side_effect=ImportError("no module")):
                result = get_available_configurations()
        self.assertEqual(result, {})

    def test_known_configuration_class_used(self):
        """GithubConfiguration should be used for provider_id='github'."""
        mock_provider_cls = MagicMock()
        mock_provider_cls.id = "github"
        mock_provider_cls.name = "Github"

        mock_provider_module = MagicMock()
        mock_provider_module.provider_classes = [mock_provider_cls]

        with patch(
            "df_config.guesses.social_providers.SOCIAL_PROVIDER_APPS",
            ["allauth.socialaccount.providers.github"],
        ):
            with patch("importlib.import_module", return_value=mock_provider_module):
                result = get_available_configurations()
        self.assertIn("github", result)
        self.assertIsInstance(result["github"], GithubConfiguration)


class TestGetLoadedConfigurations(TestCase):
    """Test get_loaded_configurations function."""

    def test_no_config_file(self):
        with override_settings(ALLAUTH_APPLICATIONS_CONFIG="/nonexistent/path.ini"):
            with patch(
                "df_config.guesses.social_providers.get_available_configurations",
                return_value={},
            ):
                result = get_loaded_configurations()
        self.assertIsInstance(result, OrderedDict)
        self.assertEqual(len(result), 0)

    def test_with_config_file_known_provider(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[github]\n")
            f.write("client_id = my_client_id\n")
            f.write("secret = my_secret\n")
            config_path = f.name
        try:
            github_config = GithubConfiguration(
                provider_id="github",
                provider_name="Github",
                provider_app="allauth.socialaccount.providers.github",
            )
            with override_settings(ALLAUTH_APPLICATIONS_CONFIG=config_path):
                with patch(
                    "df_config.guesses.social_providers.get_available_configurations",
                    return_value={"github": github_config},
                ):
                    result = get_loaded_configurations()
            self.assertIn("github", result)
            provider = result["github"]
            self.assertEqual(provider.values.get("client_id"), "my_client_id")
            self.assertEqual(provider.values.get("secret"), "my_secret")
        finally:
            os.unlink(config_path)

    def test_config_file_unknown_section_ignored(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[unknownprovider]\n")
            f.write("client_id = some_id\n")
            config_path = f.name
        try:
            with override_settings(ALLAUTH_APPLICATIONS_CONFIG=config_path):
                with patch(
                    "df_config.guesses.social_providers.get_available_configurations",
                    return_value={},
                ):
                    result = get_loaded_configurations()
            self.assertEqual(len(result), 0)
        finally:
            os.unlink(config_path)

    def test_config_file_extra_keys_ignored(self):
        """Keys not in provider.attributes are filtered out."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[github]\n")
            f.write("client_id = abc\n")
            f.write("ignored_key = should_not_appear\n")
            config_path = f.name
        try:
            github_config = GithubConfiguration(
                provider_id="github",
                provider_name="Github",
                provider_app="allauth.socialaccount.providers.github",
            )
            with override_settings(ALLAUTH_APPLICATIONS_CONFIG=config_path):
                with patch(
                    "df_config.guesses.social_providers.get_available_configurations",
                    return_value={"github": github_config},
                ):
                    result = get_loaded_configurations()
            self.assertNotIn("ignored_key", result["github"].values)
        finally:
            os.unlink(config_path)


class TestMigrate(TestCase):
    """Test the migrate function (mocking SocialApp and Site)."""

    def _make_db_app(self, name, provider, pk, **attrs):
        app = MagicMock()
        app.name = name
        app.provider = provider
        app.pk = pk
        for k, v in attrs.items():
            setattr(app, k, v)
        return app

    def _build_mocks(self, db_apps=None, site=None, app_ids=None, through_ids=None):
        db_apps = db_apps or []
        app_ids = app_ids or []
        through_ids = through_ids or []

        mock_sa_cls = MagicMock()
        mock_filter_qs = MagicMock()
        mock_filter_qs.__iter__ = MagicMock(return_value=iter(db_apps))
        mock_filter_qs.values_list.return_value = [(i,) for i in app_ids]
        mock_sa_cls.objects.filter.return_value = mock_filter_qs

        mock_through = MagicMock()
        mock_through_qs = MagicMock()
        mock_through_qs.values_list.return_value = [(i,) for i in through_ids]
        mock_through.objects.filter.return_value = mock_through_qs
        mock_sa_cls.sites.through = mock_through

        mock_site_cls = MagicMock()
        mock_site_cls.objects.filter.return_value.first.return_value = site

        mock_allauth = MagicMock()
        mock_allauth.SocialApp = mock_sa_cls
        mock_sites = MagicMock()
        mock_sites.Site = mock_site_cls

        return mock_sa_cls, mock_site_cls, mock_allauth, mock_sites

    def _make_config(self, name="df-Github", provider_id="github", values=None):
        if values is None:
            values = {"client_id": "abc", "secret": "xyz"}
        config = MagicMock()
        config.name = name
        config.provider_id = provider_id
        config.values = values
        return config

    def test_no_configs_no_db_apps_no_site(self):
        """All empty → action_required=False."""
        mock_sa, mock_site_cls, mock_allauth, mock_sites = self._build_mocks()
        with patch(
            "df_config.guesses.social_providers.get_loaded_configurations",
            return_value=OrderedDict(),
        ):
            with patch.dict(
                "sys.modules",
                {
                    "allauth.socialaccount.models": mock_allauth,
                    "django.contrib.sites.models": mock_sites,
                },
            ):
                result = migrate(read_only=True)
        self.assertFalse(result)

    def test_db_app_not_in_config_read_only(self):
        """Extra DB app → action_required=True, no deletion (read_only)."""
        db_app = self._make_db_app("df-Github", "github", pk=1)
        mock_sa, mock_site_cls, mock_allauth, mock_sites = self._build_mocks(
            db_apps=[db_app], site=None
        )
        with patch(
            "df_config.guesses.social_providers.get_loaded_configurations",
            return_value=OrderedDict(),
        ):
            with patch.dict(
                "sys.modules",
                {
                    "allauth.socialaccount.models": mock_allauth,
                    "django.contrib.sites.models": mock_sites,
                },
            ):
                result = migrate(read_only=True)
        self.assertTrue(result)
        mock_sa.objects.filter.return_value.delete.assert_not_called()

    def test_db_app_not_in_config_not_read_only(self):
        """Extra DB app → deletes it when not read_only."""
        db_app = self._make_db_app("df-Github", "github", pk=1)
        mock_sa, mock_site_cls, mock_allauth, mock_sites = self._build_mocks(
            db_apps=[db_app], site=None
        )
        with patch(
            "df_config.guesses.social_providers.get_loaded_configurations",
            return_value=OrderedDict(),
        ):
            with patch.dict(
                "sys.modules",
                {
                    "allauth.socialaccount.models": mock_allauth,
                    "django.contrib.sites.models": mock_sites,
                },
            ):
                result = migrate(read_only=False)
        self.assertTrue(result)
        mock_sa.objects.filter.return_value.delete.assert_called_once()

    def test_create_new_app_read_only(self):
        """Config has app not in DB → action_required=True, no bulk_create (read_only)."""
        config = self._make_config()
        mock_sa, mock_site_cls, mock_allauth, mock_sites = self._build_mocks(site=None)
        with patch(
            "df_config.guesses.social_providers.get_loaded_configurations",
            return_value=OrderedDict([("github", config)]),
        ):
            with patch.dict(
                "sys.modules",
                {
                    "allauth.socialaccount.models": mock_allauth,
                    "django.contrib.sites.models": mock_sites,
                },
            ):
                result = migrate(read_only=True)
        self.assertTrue(result)
        mock_sa.objects.bulk_create.assert_not_called()

    def test_create_new_app_not_read_only(self):
        """Config has app not in DB → creates it with bulk_create."""
        config = self._make_config()
        mock_sa, mock_site_cls, mock_allauth, mock_sites = self._build_mocks(site=None)
        with patch(
            "df_config.guesses.social_providers.get_loaded_configurations",
            return_value=OrderedDict([("github", config)]),
        ):
            with patch.dict(
                "sys.modules",
                {
                    "allauth.socialaccount.models": mock_allauth,
                    "django.contrib.sites.models": mock_sites,
                },
            ):
                result = migrate(read_only=False)
        self.assertTrue(result)
        mock_sa.objects.bulk_create.assert_called_once()

    def test_app_in_db_and_config_no_change(self):
        """App matches exactly → action_required=False."""
        db_app = self._make_db_app("df-Github", "github", pk=1)
        db_app.client_id = "abc"
        db_app.secret = "xyz"
        config = self._make_config(values={"client_id": "abc", "secret": "xyz"})
        mock_sa, mock_site_cls, mock_allauth, mock_sites = self._build_mocks(
            db_apps=[db_app], site=None
        )
        with patch(
            "df_config.guesses.social_providers.get_loaded_configurations",
            return_value=OrderedDict([("github", config)]),
        ):
            with patch.dict(
                "sys.modules",
                {
                    "allauth.socialaccount.models": mock_allauth,
                    "django.contrib.sites.models": mock_sites,
                },
            ):
                result = migrate(read_only=True)
        self.assertFalse(result)
        db_app.save.assert_not_called()

    def test_app_in_db_needs_update_read_only(self):
        """App values differ → action_required=True, no save (read_only)."""
        db_app = self._make_db_app("df-Github", "github", pk=1)
        db_app.client_id = "old_id"
        db_app.secret = "old_secret"
        config = self._make_config(
            values={"client_id": "new_id", "secret": "new_secret"}
        )
        mock_sa, mock_site_cls, mock_allauth, mock_sites = self._build_mocks(
            db_apps=[db_app], site=None
        )
        with patch(
            "df_config.guesses.social_providers.get_loaded_configurations",
            return_value=OrderedDict([("github", config)]),
        ):
            with patch.dict(
                "sys.modules",
                {
                    "allauth.socialaccount.models": mock_allauth,
                    "django.contrib.sites.models": mock_sites,
                },
            ):
                result = migrate(read_only=True)
        self.assertTrue(result)
        db_app.save.assert_not_called()

    def test_app_in_db_needs_update_not_read_only(self):
        """App values differ → saves the updated app."""
        db_app = self._make_db_app("df-Github", "github", pk=1)
        db_app.client_id = "old_id"
        db_app.secret = "old_secret"
        config = self._make_config(
            values={"client_id": "new_id", "secret": "new_secret"}
        )
        mock_sa, mock_site_cls, mock_allauth, mock_sites = self._build_mocks(
            db_apps=[db_app], site=None
        )
        with patch(
            "df_config.guesses.social_providers.get_loaded_configurations",
            return_value=OrderedDict([("github", config)]),
        ):
            with patch.dict(
                "sys.modules",
                {
                    "allauth.socialaccount.models": mock_allauth,
                    "django.contrib.sites.models": mock_sites,
                },
            ):
                result = migrate(read_only=False)
        self.assertTrue(result)
        db_app.save.assert_called_once()

    def test_site_exists_no_through_records_not_read_only(self):
        """Site exists, no through records → creates them."""
        mock_site = MagicMock()
        mock_site.pk = 1
        app_ids = [10, 20]

        mock_sa, mock_site_cls, mock_allauth, mock_sites = self._build_mocks(
            db_apps=[], site=mock_site, app_ids=app_ids, through_ids=[]
        )
        # First filter call = for loop (empty), second = required_db_ids (with IDs)
        call_count = [0]
        first_iter = iter([])

        def filter_se(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                m = MagicMock()
                m.__iter__ = MagicMock(return_value=first_iter)
                m.values_list.return_value = []
                m.delete = MagicMock()
                return m
            else:
                m = MagicMock()
                m.values_list.return_value = [(i,) for i in app_ids]
                return m

        mock_sa.objects.filter.side_effect = filter_se

        with patch(
            "df_config.guesses.social_providers.get_loaded_configurations",
            return_value=OrderedDict(),
        ):
            with patch.dict(
                "sys.modules",
                {
                    "allauth.socialaccount.models": mock_allauth,
                    "django.contrib.sites.models": mock_sites,
                },
            ):
                result = migrate(read_only=False)
        self.assertTrue(result)
        mock_sa.sites.through.objects.bulk_create.assert_called_once()

    def test_site_exists_all_through_already_exist(self):
        """Site exists, all through records already present → action_required=False."""
        mock_site = MagicMock()
        mock_site.pk = 1
        app_ids = [10]
        through_ids = [10]

        mock_sa, mock_site_cls, mock_allauth, mock_sites = self._build_mocks(
            db_apps=[], site=mock_site, app_ids=app_ids, through_ids=through_ids
        )
        call_count = [0]
        first_iter = iter([])

        def filter_se(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                m = MagicMock()
                m.__iter__ = MagicMock(return_value=first_iter)
                m.values_list.return_value = []
                m.delete = MagicMock()
                return m
            else:
                m = MagicMock()
                m.values_list.return_value = [(i,) for i in app_ids]
                return m

        mock_sa.objects.filter.side_effect = filter_se

        with patch(
            "df_config.guesses.social_providers.get_loaded_configurations",
            return_value=OrderedDict(),
        ):
            with patch.dict(
                "sys.modules",
                {
                    "allauth.socialaccount.models": mock_allauth,
                    "django.contrib.sites.models": mock_sites,
                },
            ):
                result = migrate(read_only=False)
        self.assertFalse(result)
        mock_sa.sites.through.objects.bulk_create.assert_not_called()

    def test_site_exists_through_needed_read_only(self):
        """Site exists, through records needed → no bulk_create when read_only=True."""
        mock_site = MagicMock()
        mock_site.pk = 1
        app_ids = [10]

        mock_sa, mock_site_cls, mock_allauth, mock_sites = self._build_mocks(
            db_apps=[], site=mock_site, app_ids=app_ids, through_ids=[]
        )
        call_count = [0]
        first_iter = iter([])

        def filter_se(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                m = MagicMock()
                m.__iter__ = MagicMock(return_value=first_iter)
                m.values_list.return_value = []
                m.delete = MagicMock()
                return m
            else:
                m = MagicMock()
                m.values_list.return_value = [(i,) for i in app_ids]
                return m

        mock_sa.objects.filter.side_effect = filter_se

        with patch(
            "df_config.guesses.social_providers.get_loaded_configurations",
            return_value=OrderedDict(),
        ):
            with patch.dict(
                "sys.modules",
                {
                    "allauth.socialaccount.models": mock_allauth,
                    "django.contrib.sites.models": mock_sites,
                },
            ):
                result = migrate(read_only=True)
        self.assertTrue(result)
        mock_sa.sites.through.objects.bulk_create.assert_not_called()

    def test_no_site_found(self):
        """Site.objects.filter(pk=1).first() returns None → skip site block."""
        mock_sa, mock_site_cls, mock_allauth, mock_sites = self._build_mocks(site=None)
        with patch(
            "df_config.guesses.social_providers.get_loaded_configurations",
            return_value=OrderedDict(),
        ):
            with patch.dict(
                "sys.modules",
                {
                    "allauth.socialaccount.models": mock_allauth,
                    "django.contrib.sites.models": mock_sites,
                },
            ):
                result = migrate(read_only=True)
        self.assertFalse(result)
        mock_sa.sites.through.objects.bulk_create.assert_not_called()
