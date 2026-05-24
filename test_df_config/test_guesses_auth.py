"""Unit tests for df_config/guesses/auth.py."""

import os
import pwd
from importlib.metadata import PackageNotFoundError
from unittest import TestCase
from unittest.mock import MagicMock, patch

from df_config.checks import settings_check_results
from df_config.guesses.auth import (
    AuthenticationBackends,
    CookieName,
    authentication_backends,
    ldap_attribute_map,
    ldap_boolean_attribute_map,
    ldap_group_class,
    ldap_group_search,
    ldap_user_search,
)


class TestCookieName(TestCase):
    def test_with_ssl(self):
        cn = CookieName("sessionid")
        self.assertEqual("__Secure-sessionid", cn({"USE_SSL": True}))

    def test_without_ssl(self):
        cn = CookieName("sessionid")
        self.assertEqual("sessionid", cn({"USE_SSL": False}))

    def test_repr(self):
        cn = CookieName("csrftoken")
        self.assertIn("CookieName", repr(cn))
        self.assertIn("csrftoken", repr(cn))


class TestAuthBackendsProcessDjango(TestCase):
    def test_allow_true(self):
        ab = AuthenticationBackends()
        result = ab.process_django({"DF_ALLOW_LOCAL_USERS": True})
        self.assertIn("django.contrib.auth.backends.ModelBackend", result)

    def test_allow_false(self):
        ab = AuthenticationBackends()
        self.assertEqual([], ab.process_django({"DF_ALLOW_LOCAL_USERS": False}))


class TestAuthBackendsProcessRemoteUser(TestCase):
    def test_with_header(self):
        ab = AuthenticationBackends()
        result = ab.process_remote_user({"DF_REMOTE_USER_HEADER": "HTTP_X_REMOTE_USER"})
        self.assertTrue(len(result) > 0)

    def test_without_header(self):
        ab = AuthenticationBackends()
        self.assertEqual([], ab.process_remote_user({"DF_REMOTE_USER_HEADER": ""}))


class TestAuthBackendsProcessAllauth(TestCase):
    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def test_no_allauth_no_apps(self):
        ab = AuthenticationBackends()
        self.assertEqual(
            [], ab.process_allauth({"USE_ALL_AUTH": False, "ALLAUTH_PROVIDER_APPS": []})
        )

    def test_use_all_auth_found(self):
        ab = AuthenticationBackends()
        with patch("df_config.guesses.auth.version", return_value="0.63.0"):
            result = ab.process_allauth(
                {"USE_ALL_AUTH": True, "ALLAUTH_PROVIDER_APPS": []}
            )
        self.assertIn("allauth.account.auth_backends.AuthenticationBackend", result)

    def test_use_all_auth_not_found(self):
        ab = AuthenticationBackends()
        with patch(
            "df_config.guesses.auth.version", side_effect=PackageNotFoundError()
        ):
            result = ab.process_allauth(
                {"USE_ALL_AUTH": True, "ALLAUTH_PROVIDER_APPS": []}
            )
        self.assertEqual([], result)

    def test_provider_apps_found(self):
        ab = AuthenticationBackends()
        with patch("df_config.guesses.auth.version", return_value="0.63.0"):
            result = ab.process_allauth(
                {"USE_ALL_AUTH": False, "ALLAUTH_PROVIDER_APPS": ["some.app"]}
            )
        self.assertIn("allauth.account.auth_backends.AuthenticationBackend", result)


class TestAuthBackendsProcessRadius(TestCase):
    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def test_no_server(self):
        ab = AuthenticationBackends()
        self.assertEqual([], ab.process_radius({"RADIUS_SERVER": ""}))

    def test_server_found(self):
        ab = AuthenticationBackends()
        with patch("df_config.guesses.auth.version", return_value="1.0"):
            result = ab.process_radius({"RADIUS_SERVER": "radius.example.com"})
        self.assertIn("radiusauth.backends.RADIUSBackend", result)

    def test_server_not_found(self):
        ab = AuthenticationBackends()
        with patch(
            "df_config.guesses.auth.version", side_effect=PackageNotFoundError()
        ):
            result = ab.process_radius({"RADIUS_SERVER": "radius.example.com"})
        self.assertEqual([], result)
        self.assertEqual(1, len(settings_check_results))


class TestAuthBackendsProcessLdap(TestCase):
    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def test_no_uri(self):
        ab = AuthenticationBackends()
        self.assertEqual([], ab.process_django_ldap({"AUTH_LDAP_SERVER_URI": ""}))

    def test_uri_found(self):
        ab = AuthenticationBackends()
        with patch("df_config.guesses.auth.version", return_value="4.6.0"):
            result = ab.process_django_ldap(
                {"AUTH_LDAP_SERVER_URI": "ldap://ldap.example.com"}
            )
        self.assertIn("django_auth_ldap.backend.LDAPBackend", result)

    def test_uri_not_found(self):
        ab = AuthenticationBackends()
        with patch(
            "df_config.guesses.auth.version", side_effect=PackageNotFoundError()
        ):
            result = ab.process_django_ldap(
                {"AUTH_LDAP_SERVER_URI": "ldap://ldap.example.com"}
            )
        self.assertEqual([], result)
        self.assertEqual(1, len(settings_check_results))


class TestAuthBackendsProcessPam(TestCase):
    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def test_pam_disabled(self):
        ab = AuthenticationBackends()
        self.assertEqual([], ab.process_pam({"USE_PAM_AUTHENTICATION": False}))

    def test_pam_not_installed(self):
        ab = AuthenticationBackends()
        with patch(
            "df_config.guesses.auth.version", side_effect=PackageNotFoundError()
        ):
            result = ab.process_pam({"USE_PAM_AUTHENTICATION": True})
        self.assertEqual([], result)
        self.assertEqual(1, len(settings_check_results))

    def test_pam_user_in_shadow(self):
        ab = AuthenticationBackends()
        username = pwd.getpwuid(os.getuid()).pw_name
        shadow_grp = MagicMock()
        shadow_grp.gr_name = "shadow"
        shadow_grp.gr_mem = [username]
        with (
            patch("df_config.guesses.auth.version", return_value="1.0"),
            patch("grp.getgrall", return_value=[shadow_grp]),
        ):
            result = ab.process_pam({"USE_PAM_AUTHENTICATION": True})
        self.assertIn("django_pam.auth.backends.PAMBackend", result)

    def test_pam_user_not_in_shadow(self):
        ab = AuthenticationBackends()
        shadow_grp = MagicMock()
        shadow_grp.gr_name = "shadow"
        shadow_grp.gr_mem = []
        with (
            patch("df_config.guesses.auth.version", return_value="1.0"),
            patch("grp.getgrall", return_value=[shadow_grp]),
        ):
            result = ab.process_pam({"USE_PAM_AUTHENTICATION": True})
        self.assertEqual([], result)
        self.assertEqual(1, len(settings_check_results))


class TestAuthBackendsCallAndRepr(TestCase):
    def setUp(self):
        self._saved = list(settings_check_results)
        settings_check_results[:] = []

    def tearDown(self):
        settings_check_results[:] = self._saved

    def test_call_all_disabled(self):
        ab = AuthenticationBackends()
        result = ab(
            {
                "ALLAUTH_PROVIDER_APPS": [],
                "DF_REMOTE_USER_HEADER": "",
                "AUTH_LDAP_SERVER_URI": "",
                "USE_PAM_AUTHENTICATION": False,
                "DF_ALLOW_LOCAL_USERS": False,
                "USE_ALL_AUTH": False,
                "RADIUS_SERVER": "",
            }
        )
        self.assertEqual([], result)

    def test_repr(self):
        ab = AuthenticationBackends()
        self.assertIn("authentication_backends", repr(ab))


class TestLdapUserSearch(TestCase):
    def test_no_uri(self):
        self.assertIsNone(
            ldap_user_search(
                {
                    "AUTH_LDAP_SERVER_URI": "",
                    "AUTH_LDAP_USER_SEARCH_BASE": "dc=example,dc=com",
                    "AUTH_LDAP_FILTER": "(uid=%(user)s)",
                }
            )
        )

    def test_no_base(self):
        self.assertIsNone(
            ldap_user_search(
                {
                    "AUTH_LDAP_SERVER_URI": "ldap://ldap.example.com",
                    "AUTH_LDAP_USER_SEARCH_BASE": "",
                    "AUTH_LDAP_FILTER": "(uid=%(user)s)",
                }
            )
        )

    def test_import_error(self):
        import sys

        with patch.dict(
            sys.modules,
            {"ldap": None, "django_auth_ldap": None, "django_auth_ldap.config": None},
        ):
            result = ldap_user_search(
                {
                    "AUTH_LDAP_SERVER_URI": "ldap://ldap.example.com",
                    "AUTH_LDAP_USER_SEARCH_BASE": "dc=example,dc=com",
                    "AUTH_LDAP_FILTER": "(uid=%(user)s)",
                }
            )
        self.assertIsNone(result)

    def test_success(self):
        import sys

        mock_ldap = MagicMock()
        mock_ldap.SCOPE_SUBTREE = 2
        mock_search_cls = MagicMock()
        mock_config = MagicMock()
        mock_config.LDAPSearch = mock_search_cls
        with patch.dict(
            sys.modules,
            {
                "ldap": mock_ldap,
                "django_auth_ldap": MagicMock(),
                "django_auth_ldap.config": mock_config,
            },
        ):
            ldap_user_search(
                {
                    "AUTH_LDAP_SERVER_URI": "ldap://ldap.example.com",
                    "AUTH_LDAP_USER_SEARCH_BASE": "dc=example,dc=com",
                    "AUTH_LDAP_FILTER": "(uid=%(user)s)",
                }
            )
        mock_search_cls.assert_called_once()


class TestLdapGroupSearch(TestCase):
    def test_no_uri(self):
        self.assertIsNone(
            ldap_group_search(
                {
                    "AUTH_LDAP_SERVER_URI": "",
                    "AUTH_LDAP_GROUP_SEARCH_BASE": "ou=groups,dc=example,dc=com",
                }
            )
        )

    def test_no_base(self):
        self.assertIsNone(
            ldap_group_search(
                {
                    "AUTH_LDAP_SERVER_URI": "ldap://ldap.example.com",
                    "AUTH_LDAP_GROUP_SEARCH_BASE": "",
                }
            )
        )

    def test_import_error(self):
        import sys

        with patch.dict(
            sys.modules,
            {"ldap": None, "django_auth_ldap": None, "django_auth_ldap.config": None},
        ):
            result = ldap_group_search(
                {
                    "AUTH_LDAP_SERVER_URI": "ldap://ldap.example.com",
                    "AUTH_LDAP_GROUP_SEARCH_BASE": "ou=groups,dc=example,dc=com",
                }
            )
        self.assertIsNone(result)

    def test_success(self):
        import sys

        mock_ldap = MagicMock()
        mock_ldap.SCOPE_SUBTREE = 2
        mock_search_cls = MagicMock()
        mock_config = MagicMock()
        mock_config.LDAPSearch = mock_search_cls
        with patch.dict(
            sys.modules,
            {
                "ldap": mock_ldap,
                "django_auth_ldap": MagicMock(),
                "django_auth_ldap.config": mock_config,
            },
        ):
            ldap_group_search(
                {
                    "AUTH_LDAP_SERVER_URI": "ldap://ldap.example.com",
                    "AUTH_LDAP_GROUP_SEARCH_BASE": "ou=groups,dc=example,dc=com",
                }
            )
        mock_search_cls.assert_called_once()


class TestLdapAttributeMap(TestCase):
    def test_all_fields(self):
        result = ldap_attribute_map(
            {
                "AUTH_LDAP_USER_FIRST_NAME": "givenName",
                "AUTH_LDAP_USER_LAST_NAME": "sn",
                "AUTH_LDAP_USER_EMAIL": "mail",
            }
        )
        self.assertEqual(
            {"first_name": "givenName", "last_name": "sn", "email": "mail"}, result
        )

    def test_no_fields(self):
        result = ldap_attribute_map(
            {
                "AUTH_LDAP_USER_FIRST_NAME": "",
                "AUTH_LDAP_USER_LAST_NAME": "",
                "AUTH_LDAP_USER_EMAIL": "",
            }
        )
        self.assertEqual({}, result)


class TestLdapBooleanAttributeMap(TestCase):
    def test_all_fields(self):
        result = ldap_boolean_attribute_map(
            {
                "AUTH_LDAP_USER_IS_ACTIVE": "userAccountControl",
                "AUTH_LDAP_USER_IS_STAFF": "memberOf",
                "AUTH_LDAP_USER_IS_SUPERUSER": "isSuperUser",
            }
        )
        self.assertIn("is_active", result)
        self.assertIn("is_staff", result)
        self.assertIn("is_superuser", result)

    def test_no_fields(self):
        result = ldap_boolean_attribute_map(
            {
                "AUTH_LDAP_USER_IS_ACTIVE": "",
                "AUTH_LDAP_USER_IS_STAFF": "",
                "AUTH_LDAP_USER_IS_SUPERUSER": "",
            }
        )
        self.assertEqual({}, result)


class TestLdapGroupClass(TestCase):
    def test_no_uri(self):
        self.assertIsNone(
            ldap_group_class(
                {
                    "AUTH_LDAP_SERVER_URI": "",
                    "AUTH_LDAP_GROUP_NAME": "some.GroupClass",
                }
            )
        )

    def test_import_error(self):
        with patch(
            "df_config.guesses.auth.import_string", side_effect=ImportError("no module")
        ):
            result = ldap_group_class(
                {
                    "AUTH_LDAP_SERVER_URI": "ldap://ldap.example.com",
                    "AUTH_LDAP_GROUP_NAME": "nonexistent.GroupClass",
                }
            )
        self.assertIsNone(result)

    def test_success(self):
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        with patch("df_config.guesses.auth.import_string", return_value=mock_cls):
            result = ldap_group_class(
                {
                    "AUTH_LDAP_SERVER_URI": "ldap://ldap.example.com",
                    "AUTH_LDAP_GROUP_NAME": "some.GroupClass",
                }
            )
        self.assertEqual(mock_instance, result)
