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
"""Check installed modules and settings to provide lists of middlewares/installed apps."""
import os
from collections import OrderedDict
from configparser import RawConfigParser
from importlib.metadata import PackageNotFoundError, version

from django.core.checks import Error

from df_config.checks import missing_package, settings_check_results
from df_config.config.dynamic_settings import ExpandIterable
from df_config.guesses.social_providers import SOCIAL_PROVIDER_APPS
from df_config.utils import is_package_present


def allauth_provider_apps(settings_dict):
    """Provide configured authentications for django_allauth."""
    parser = RawConfigParser()
    config = settings_dict["ALLAUTH_APPLICATIONS_CONFIG"]
    if not os.path.isfile(config):
        return []
    # noinspection PyBroadException
    try:
        parser.read([config])
    except Exception:  # nosec  # nosec
        settings_check_results.append(
            Error(
                f"Invalid config file '{config}.",
                obj="configuration",
                id="df_config.E003",
            )
        )
        return []
    return [
        parser.get(section, "django_app")
        for section in parser.sections()
        if parser.has_option(section, "django_app")
    ]


allauth_provider_apps.required_settings = ["ALLAUTH_APPLICATIONS_CONFIG"]


class InstalledApps:
    """Provide a complete `INSTALLED_APPS` list, transparently adding common third-party packages.

    Specifically handle apps required by django-allauth (one by allowed method).
    """

    default_apps = [
        ExpandIterable("DF_INSTALLED_APPS"),
    ]
    base_django_apps = [
        "df_config",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.messages",
        "django.contrib.humanize",
        "django.contrib.sitemaps",
        "django.contrib.sites",
        "django.contrib.staticfiles",
        "django.contrib.admin",
    ]
    common_third_parties = OrderedDict(
        [
            ("USE_WEBSOCKETS", ["df_websockets", "channels"]),
            ("USE_DEBUG_TOOLBAR", ["debug_toolbar.apps.DebugToolbarConfig"]),
            ("USE_PIPELINE", ["pipeline"]),
            ("USE_PAM_AUTHENTICATION", ["django_pam"]),
            ("USE_CORS_HEADER", ["corsheaders"]),
            ("USE_DAPHNE", ["daphne"]),
            ("USE_DJANGO_PROBES", ["django_probes"]),
            ("USE_CSP", "csp"),
            ("USE_PROMETHEUS", "django_prometheus"),
        ]
    )
    required_settings = [
        "ALLAUTH_PROVIDER_APPS",
        "DF_INSTALLED_APPS",
        "SESSION_ENGINE",
        "USE_ALL_AUTH",
    ] + list(common_third_parties)
    social_apps = SOCIAL_PROVIDER_APPS

    def __call__(self, settings_dict):
        """Check available packages and return the list of installed apps."""
        apps = self.default_apps
        if settings_dict["SESSION_ENGINE"] == "django.contrib.sessions.backends.db":
            apps += ["django.contrib.sessions"]
        apps += self.process_django_allauth(settings_dict)
        apps += self.process_third_parties(settings_dict)
        apps += self.base_django_apps
        return apps

    def process_third_parties(self, settings_dict):
        """Process third-party applications."""
        result = []
        for k, v in self.common_third_parties.items():
            package_name = v[0].partition(".")[0]
            if not settings_dict[k]:
                continue
            elif not is_package_present(package_name):
                settings_check_results.append(missing_package(package_name, ""))
                continue
            if package_name == "csp":
                try:
                    if version("django-csp")[0] <= "3":
                        # the csp app must be added to INSTALLED_APPS for django-csp >= 4
                        continue
                except PackageNotFoundError:
                    continue
            result += v
        return result

    def process_django_allauth(self, settings_dict):
        """Detect django-allauth applications."""
        if (
            not settings_dict["USE_ALL_AUTH"]
            and not settings_dict["ALLAUTH_PROVIDER_APPS"]
        ):
            return []
        try:
            version("django-allauth")
        except PackageNotFoundError:
            settings_check_results.append(
                missing_package(
                    "django-allauth", " to use OAuth2 or OpenID authentication"
                )
            )
            return []
        app = "django.contrib.sites"
        if app not in self.default_apps and app not in self.base_django_apps:
            settings_check_results.append(
                Error(
                    '"django.contrib.sites" app must be enabled.',
                    obj="configuration",
                    id="df_config.E001",
                )
            )
            return []
        result = ["allauth", "allauth.account"]
        if is_package_present("pypng") and is_package_present("qrcode"):
            result += ["allauth.mfa"]
        if settings_dict["ALLAUTH_PROVIDER_APPS"]:
            result += ["allauth.socialaccount"]
            result += [
                k
                for k in settings_dict["ALLAUTH_PROVIDER_APPS"]
                if k in self.social_apps
            ]
        return result

    def __repr__(self):
        """Represent the list of installed apps."""
        return "%s.%s" % (self.__module__, "installed_apps")


installed_apps = InstalledApps()


class Middlewares:
    """Detect common available middlewares."""

    use_cache_middleware = True
    base_django_middlewares = [
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.middleware.locale.LocaleMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
        "django.middleware.security.SecurityMiddleware",
        "df_config.apps.middleware.DFConfigMiddleware",
    ]
    common_third_parties = OrderedDict(
        [
            ("USE_WHITENOISE", "whitenoise.middleware.WhiteNoiseMiddleware"),
            ("USE_WEBSOCKETS", "df_websockets.middleware.WebsocketMiddleware"),
            ("USE_CSP", "csp.middleware.CSPMiddleware"),
            ("USE_CORS_HEADER", "corsheaders.middleware.CorsMiddleware"),
            ("USE_ALL_AUTH", "allauth.account.middleware.AccountMiddleware"),
        ]
    )
    required_settings = ["DF_MIDDLEWARE", "USE_PROMETHEUS", "INSTALLED_APPS"] + list(
        common_third_parties
    )

    def __call__(self, settings_dict):
        """Return the list of required middlewares."""
        mw_list = []
        mw_list += self.base_django_middlewares
        mw_list.append(ExpandIterable("DF_MIDDLEWARE"))
        mw_list += self.process_third_parties(settings_dict)
        if "allauth.usersessions" in settings_dict["INSTALLED_APPS"]:
            mw_list.append("allauth.usersessions.middleware.UserSessionsMiddleware")
        if settings_dict["USE_DEBUG_TOOLBAR"]:
            mw_list.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
        if self.use_cache_middleware:
            mw_list.insert(0, "django.middleware.cache.UpdateCacheMiddleware")
            mw_list.append("django.middleware.cache.FetchFromCacheMiddleware")
        if self.use_cache_middleware:
            mw_list.insert(0, "django.middleware.cache.UpdateCacheMiddleware")
            mw_list.append("django.middleware.cache.FetchFromCacheMiddleware")
        if settings_dict["USE_PROMETHEUS"]:
            mw_list.insert(0, "django_prometheus.middleware.PrometheusBeforeMiddleware")
            mw_list.append("django_prometheus.middleware.PrometheusAfterMiddleware")
        return mw_list

    def process_third_parties(self, settings_dict):
        """Process third-party middlewares."""
        result = []
        for k, v in self.common_third_parties.items():
            package_name = v.partition(".")[0]
            if not settings_dict[k]:
                continue
            elif not is_package_present(package_name):
                settings_check_results.append(missing_package(package_name, ""))
                continue
            result.append(v)
        return result

    def __repr__(self):
        """Represent the Middleware magic setting."""
        return "%s.%s" % (self.__module__, "middlewares")


middlewares = Middlewares()
