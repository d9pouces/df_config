# ##############################################################################
#  This file is part of df_config                                              #
#                                                                              #
#  Copyright (C) 2020 Matthieu Gallet <df_config@19pouces.net>                    #
#  All Rights Reserved                                                         #
#                                                                              #
#  You may use, distribute and modify this code under the                      #
#  terms of the (BSD-like) CeCILL-B license.                                   #
#                                                                              #
#  You should have received a copy of the CeCILL-B license with                #
#  this file. If not, please visit:                                            #
#  https://cecill.info/licences/Licence_CeCILL-B_V1-en.txt (English)           #
#  or https://cecill.info/licences/Licence_CeCILL-B_V1-fr.txt (French)         #
#                                                                              #
# ##############################################################################


# noinspection PyMethodMayBeStatic
import grp
import os
import pwd
from importlib.metadata import PackageNotFoundError, version

from django.core.checks import Error
from django.utils.module_loading import import_string

from df_config.checks import missing_package, settings_check_results


class CookieName:
    """Provide cookie names that are different when SSL is used."""

    required_settings = ["USE_SSL"]

    def __init__(self, cookie_name: str):
        self.cookie_name = cookie_name

    def __call__(self, settings_dict) -> str:
        if settings_dict["USE_SSL"]:
            return "__Secure-%s" % self.cookie_name
        return self.cookie_name

    def __repr__(self):
        return f"{self.__class__.__name__}({self.cookie_name!r})"


# noinspection PyMethodMayBeStatic
class AuthenticationBackends:
    required_settings = [
        "ALLAUTH_PROVIDER_APPS",
        "DF_REMOTE_USER_HEADER",
        "AUTH_LDAP_SERVER_URI",
        "USE_PAM_AUTHENTICATION",
        "DF_ALLOW_LOCAL_USERS",
        "USE_ALL_AUTH",
        "RADIUS_SERVER",
    ]

    def __call__(self, settings_dict):
        backends = []
        backends += self.process_remote_user(settings_dict)
        backends += self.process_radius(settings_dict)
        backends += self.process_django(settings_dict)
        backends += self.process_django_ldap(settings_dict)
        backends += self.process_allauth(settings_dict)
        backends += self.process_pam(settings_dict)
        return backends

    def process_django(self, settings_dict):
        if settings_dict["DF_ALLOW_LOCAL_USERS"]:
            return ["django.contrib.auth.backends.ModelBackend"]
        return []

    def process_remote_user(self, settings_dict):
        if settings_dict["DF_REMOTE_USER_HEADER"]:
            return ["df_config.apps.backends.DefaultGroupsRemoteUserBackend"]
        return []

    def process_allauth(self, settings_dict):
        if (
            not settings_dict["USE_ALL_AUTH"]
            and not settings_dict["ALLAUTH_PROVIDER_APPS"]
        ):
            return []
        try:
            version("django-allauth")
            return ["allauth.account.auth_backends.AuthenticationBackend"]
        except PackageNotFoundError:
            return []

    def process_radius(self, settings_dict):
        if not settings_dict["RADIUS_SERVER"]:
            return []
        try:
            version("django-radius")
        except PackageNotFoundError:
            settings_check_results.append(
                missing_package("django-radius", " to use RADIUS authentication")
            )
            return []
        return ["radiusauth.backends.RADIUSBackend"]

    def process_django_ldap(self, settings_dict):
        if not settings_dict["AUTH_LDAP_SERVER_URI"]:
            return []
        try:
            version("django-auth-ldap")
        except PackageNotFoundError:
            settings_check_results.append(
                missing_package("django-auth-ldap", " to use LDAP authentication")
            )
            return []
        return ["django_auth_ldap.backend.LDAPBackend"]

    def process_pam(self, settings_dict):
        if not settings_dict["USE_PAM_AUTHENTICATION"]:
            return []
        try:
            version("django_pam")
        except PackageNotFoundError:
            settings_check_results.append(
                missing_package("django-pam", " to use PAM authentication")
            )
            return []
        # check if the current user is in the shadow group
        username = pwd.getpwuid(os.getuid()).pw_name
        if not any(
            x.gr_name == "shadow" and username in x.gr_mem for x in grp.getgrall()
        ):
            settings_check_results.append(
                Error(
                    'The user "%s" must belong to the "shadow" group to use PAM '
                    "authentication." % username,
                    obj="configuration",
                )
            )
            return []
        return ["django_pam.auth.backends.PAMBackend"]

    def __repr__(self):
        return "%s.%s" % (self.__module__, "authentication_backends")


authentication_backends = AuthenticationBackends()


def ldap_user_search(settings_dict):
    if (
        settings_dict["AUTH_LDAP_SERVER_URI"]
        and settings_dict["AUTH_LDAP_USER_SEARCH_BASE"]
    ):
        try:
            # noinspection PyPackageRequirements,PyUnresolvedReferences
            import ldap

            # noinspection PyUnresolvedReferences
            from django_auth_ldap.config import LDAPSearch
        except ImportError:
            return None
        return LDAPSearch(
            settings_dict["AUTH_LDAP_USER_SEARCH_BASE"],
            ldap.SCOPE_SUBTREE,
            settings_dict["AUTH_LDAP_FILTER"],
        )
    return None


ldap_user_search.required_settings = [
    "AUTH_LDAP_USER_SEARCH_BASE",
    "AUTH_LDAP_SERVER_URI",
    "AUTH_LDAP_FILTER",
]


def ldap_group_search(settings_dict):
    if (
        settings_dict["AUTH_LDAP_SERVER_URI"]
        and settings_dict["AUTH_LDAP_GROUP_SEARCH_BASE"]
    ):
        try:
            # noinspection PyPackageRequirements,PyUnresolvedReferences
            import ldap

            # noinspection PyUnresolvedReferences
            from django_auth_ldap.config import LDAPSearch
        except ImportError:
            return None
        return LDAPSearch(
            settings_dict["AUTH_LDAP_GROUP_SEARCH_BASE"],
            ldap.SCOPE_SUBTREE,
            "(objectClass=*)",
        )
    return None


ldap_group_search.required_settings = [
    "AUTH_LDAP_GROUP_SEARCH_BASE",
    "AUTH_LDAP_SERVER_URI",
]


def ldap_attribute_map(settings_dict):
    result = {}
    if settings_dict["AUTH_LDAP_USER_FIRST_NAME"]:
        result["first_name"] = settings_dict["AUTH_LDAP_USER_FIRST_NAME"]
    if settings_dict["AUTH_LDAP_USER_LAST_NAME"]:
        result["last_name"] = settings_dict["AUTH_LDAP_USER_LAST_NAME"]
    if settings_dict["AUTH_LDAP_USER_EMAIL"]:
        result["email"] = settings_dict["AUTH_LDAP_USER_EMAIL"]
    return result


ldap_attribute_map.required_settings = [
    "AUTH_LDAP_USER_FIRST_NAME",
    "AUTH_LDAP_USER_LAST_NAME",
    "AUTH_LDAP_USER_EMAIL",
]


def ldap_boolean_attribute_map(settings_dict):
    result = {}
    if settings_dict["AUTH_LDAP_USER_IS_ACTIVE"]:
        result["is_active"] = settings_dict["AUTH_LDAP_USER_IS_ACTIVE"]
    if settings_dict["AUTH_LDAP_USER_IS_STAFF"]:
        result["is_staff"] = settings_dict["AUTH_LDAP_USER_IS_STAFF"]
    if settings_dict["AUTH_LDAP_USER_IS_ACTIVE"]:
        result["is_superuser"] = settings_dict["AUTH_LDAP_USER_IS_SUPERUSER"]
    return result


ldap_boolean_attribute_map.required_settings = [
    "AUTH_LDAP_USER_IS_ACTIVE",
    "AUTH_LDAP_USER_IS_STAFF",
    "AUTH_LDAP_USER_IS_SUPERUSER",
]


def ldap_group_class(settings_dict):
    if settings_dict["AUTH_LDAP_SERVER_URI"]:
        try:
            cls = import_string(settings_dict["AUTH_LDAP_GROUP_NAME"])
            return cls()
        except ImportError:
            return None
    return None


ldap_group_class.required_settings = ["AUTH_LDAP_GROUP_NAME", "AUTH_LDAP_SERVER_URI"]
