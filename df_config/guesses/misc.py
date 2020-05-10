# ##############################################################################
#  This file is part of df_config                                              #
#                                                                              #
#  Copyright (C) 2020 Matthieu Gallet <github@19pouces.net>                    #
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
import os
import re
from urllib.parse import urlparse

from django.utils.crypto import get_random_string
from pkg_resources import DistributionNotFound, VersionConflict, get_distribution

from df_config.checks import missing_package, settings_check_results
from df_config.config.dynamic_settings import DynamicSettting


def smart_hostname(settings_dict):
    """
    By default, use the listen address and port as server name.
    Use the "HEROKU_APP_NAME" environment variable if present.

    :param settings_dict:
    :return:
    """
    if "HEROKU_APP_NAME" in os.environ:
        return "https://%s.herokuapp.com/" % os.environ["HEROKU_APP_NAME"]
    return "http://%s/" % settings_dict["LISTEN_ADDRESS"]


smart_hostname.required_settings = ["LISTEN_ADDRESS"]


class DefaultListenAddress(DynamicSettting):
    def get_value(self, merger, provider_name: str, setting_name: str):
        port = os.environ.get("PORT", "")
        if re.match(r"^([1-9]\d*)$", port) and 1 <= int(port) <= 65535:
            return "0.0.0.0:%s" % port
        return "localhost:%d" % self.value


def template_setting(settings_dict):
    loaders = [
        "django.template.loaders.filesystem.Loader",
        "django.template.loaders.app_directories.Loader",
    ]
    if settings_dict["DEBUG"]:
        backend = {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "NAME": "default",
            "DIRS": settings_dict["TEMPLATE_DIRS"],
            "OPTIONS": {
                "context_processors": settings_dict["TEMPLATE_CONTEXT_PROCESSORS"],
                "loaders": loaders,
                "debug": True,
            },
        }
    else:
        backend = {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "NAME": "default",
            "DIRS": settings_dict["TEMPLATE_DIRS"],
            "OPTIONS": {
                "context_processors": settings_dict["TEMPLATE_CONTEXT_PROCESSORS"],
                "debug": False,
                "loaders": [("django.template.loaders.cached.Loader", loaders)],
            },
        }
    return [backend]


template_setting.required_settings = [
    "DEBUG",
    "TEMPLATE_DIRS",
    "TEMPLATE_CONTEXT_PROCESSORS",
]


def allowed_hosts(settings_dict):
    result = {"127.0.0.1", "::1", "localhost"}
    listened_ip, sep, port = settings_dict["LISTEN_ADDRESS"].rpartition(":")
    if sep == ":" and listened_ip not in ("::", "0.0.0.0"):
        result.add(listened_ip)
    result.add(settings_dict["SERVER_NAME"])
    return list(sorted(result))


allowed_hosts.required_settings = ["SERVER_NAME", "LISTEN_ADDRESS"]


def secure_hsts_seconds(settings_dict):
    if settings_dict["USE_SSL"]:
        return 86400
    return 0


secure_hsts_seconds.required_settings = ["USE_SSL"]


def url_parse_server_name(settings_dict):
    """Return the public hostname, given the public base URL

    >>> url_parse_server_name({'SERVER_BASE_URL': 'https://demo.example.org/'})
    'demo.example.org'

    """
    return urlparse(settings_dict["SERVER_BASE_URL"]).hostname


url_parse_server_name.required_settings = ["SERVER_BASE_URL"]


def url_parse_server_port(settings_dict):
    """Return the public port, given the public base URL

    >>> url_parse_server_port({'SERVER_BASE_URL': 'https://demo.example.org/', 'USE_SSL': True})
    443
    >>> url_parse_server_port({'SERVER_BASE_URL': 'http://demo.example.org/', 'USE_SSL': False})
    80
    >>> url_parse_server_port({'SERVER_BASE_URL': 'https://demo.example.org:8010/', 'USE_SSL': True})
    8010

    """
    return (
        urlparse(settings_dict["SERVER_BASE_URL"]).port
        or (settings_dict["USE_SSL"] and 443)
        or 80
    )


url_parse_server_port.required_settings = ["SERVER_BASE_URL", "USE_SSL"]


def url_parse_server_protocol(settings_dict):
    """Return the public HTTP protocol, given the public base URL

    >>> url_parse_server_protocol({'USE_SSL': True})
    'https'

    >>> url_parse_server_protocol({'USE_SSL': False})
    'http'

    """
    return "https" if settings_dict["USE_SSL"] else "http"


url_parse_server_protocol.required_settings = ["USE_SSL"]


def url_parse_prefix(settings_dict):
    """Return the public URL prefix, given the public base URL

    >>> url_parse_prefix({'SERVER_BASE_URL': 'https://demo.example.org/demo/'})
    '/demo/'
    >>> url_parse_prefix({'SERVER_BASE_URL': 'http://demo.example.org/'})
    '/'
    >>> url_parse_prefix({'SERVER_BASE_URL': 'https://demo.example.org:8010'})
    '/'

    """
    p = urlparse(settings_dict["SERVER_BASE_URL"]).path
    if not p.endswith("/"):
        p += "/"
    return p


url_parse_prefix.required_settings = ["SERVER_BASE_URL"]


def url_parse_ssl(settings_dict):
    """Return True if the public URL uses https

    >>> url_parse_ssl({'SERVER_BASE_URL': 'https://demo.example.org/demo/'})
    True
    >>> url_parse_ssl({'SERVER_BASE_URL': 'http://demo.example.org/'})
    False

    """
    return urlparse(settings_dict["SERVER_BASE_URL"]).scheme == "https"


url_parse_ssl.required_settings = ["SERVER_BASE_URL"]


def use_x_forwarded_for(settings_dict):
    """Return `True` if this server is assumed to be behind a reverse proxy.
     Heuristic: the external port (in SERVER_PORT) is different from the actually listened port (in LISTEN_ADDRESS).

     >>> use_x_forwarded_for({'SERVER_PORT': 8000, 'LISTEN_ADDRESS': 'localhost:8000'})
     False
     >>> use_x_forwarded_for({'SERVER_PORT': 443, 'LISTEN_ADDRESS': 'localhost:8000'})
     True

    """
    listen_address, sep, listen_port = settings_dict["LISTEN_ADDRESS"].rpartition(":")
    if not re.match(r"\d+", listen_port):
        raise ValueError("Invalid LISTEN_ADDRESS port %s" % listen_port)
    return int(listen_port) != settings_dict["SERVER_PORT"]


use_x_forwarded_for.required_settings = ["SERVER_PORT", "LISTEN_ADDRESS"]


def project_name(settings_dict):
    """Transform the base module name into a nicer project name

    >>> project_name({'DF_MODULE_NAME': 'my_project'})
    'My Project'

    :param settings_dict:
    :return:
    """

    return " ".join(
        [
            x.capitalize()
            for x in settings_dict["DF_MODULE_NAME"].replace("_", " ").split()
        ]
    )


project_name.required_settings = ["DF_MODULE_NAME"]


def generate_secret_key(django_ready, length=60):
    if not django_ready:
        return get_random_string(length=length)
    from django.conf import settings

    return settings.SECRET_KEY


def required_packages(settings_dict):
    """
    Return a sorted list of the Python packages required by the current project (with their dependencies).
    A warning is added for each missing package.

    :param settings_dict:
    :return:
    """

    def get_requirements(package_name, parent=None):
        try:
            yield str(package_name)
            d = get_distribution(package_name)
            for r in d.requires():
                for required_package in get_requirements(r, parent=package_name):
                    yield str(required_package)
        except DistributionNotFound:
            settings_check_results.append(
                missing_package(str(package_name), " by %s" % parent)
            )
        except VersionConflict:
            settings_check_results.append(
                missing_package(str(package_name), " by %s" % parent)
            )

    return list(
        sorted(
            set(
                get_requirements(
                    settings_dict["DF_MODULE_NAME"],
                    parent=settings_dict["DF_MODULE_NAME"],
                )
            )
        )
    )


required_packages.required_settings = ["DF_MODULE_NAME"]


class ExcludedDjangoCommands:
    required_settings = ["DEVELOPMENT", "USE_CELERY", "DEBUG"]

    def __call__(self, settings_dict):
        result = {"startproject", "diffsettings"}
        if not settings_dict["DEVELOPMENT"]:
            result |= {
                "startapp",
                "findstatic",
                "npm",
                "makemigrations",
                "makemessages",
                "inspectdb",
                "compilemessages",
                "remove_stale_contenttypes",
                "squashmigrations",
            }
        if not settings_dict["USE_CELERY"]:
            result |= {"celery", "worker"}
        if not settings_dict["DEBUG"] and not settings_dict["DEVELOPMENT"]:
            result |= {"testserver", "test", "runserver"}
        return result

    def __repr__(self):
        return "%s.%s" % (self.__module__, "excluded_django_commands")


excluded_django_commands = ExcludedDjangoCommands()
