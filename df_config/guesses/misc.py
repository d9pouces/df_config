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
"""Misc functions for the default settings."""
import re
import socket
import sys
from importlib.metadata import PackageNotFoundError, distribution, version
from typing import Dict, Iterable, List, Set
from urllib.parse import urlparse

# noinspection PyPackageRequirements
from django.core.checks import Warning

# noinspection PyPackageRequirements
from django.utils.crypto import get_random_string

from df_config.checks import missing_package, settings_check_results
from df_config.config.dynamic_settings import AutocreateFileContent
from df_config.utils import is_package_present


# noinspection PyUnusedLocal
def get_command_name(settings_dict) -> str:
    """Get the current name."""
    if len(sys.argv) >= 2:
        return sys.argv[1]
    return sys.argv[0] if len(sys.argv) >= 1 else "undefined"


# noinspection PyUnusedLocal
def get_hostname(settings_dict) -> str:
    """Get the current hostname."""
    return socket.gethostname()


def smart_base_url(settings_dict) -> str:
    """Return the external URL of the webserver.

    By default, use the listen address and port as server name.
    Use the "HEROKU_APP_NAME" environment variable if present.

    :param settings_dict:
    :return:
    """
    if settings_dict["HEROKU_APP_NAME"]:
        return "https://%(HEROKU_APP_NAME)s.herokuapp.com/" % settings_dict
    return "http://%(LISTEN_ADDRESS)s/" % settings_dict


smart_base_url.required_settings = ["LISTEN_ADDRESS", "HEROKU_APP_NAME"]


def smart_listen_address(settings_dict):
    """Return the address to listen to with the server command."""
    port = settings_dict["LISTEN_PORT"]
    if isinstance(port, int) and 1 <= port <= 65535:
        return f"0.0.0.0:{port}"
    elif port and re.match(r"^([1-9]\d*)$", port) and 1 <= int(port) <= 65535:
        return f"0.0.0.0:{port}"
    return "localhost:8000"


smart_listen_address.required_settings = ["LISTEN_PORT"]


def template_setting(settings_dict):
    """Return the template settings (taking the DEBUG setting into account)."""
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


def allowed_hosts(settings_dict) -> List[str]:
    """Return a list of allow hosts."""
    result = {"127.0.0.1", "::1", "localhost"}
    listened_ip, sep, port = settings_dict["LISTEN_ADDRESS"].rpartition(":")
    if sep == ":" and listened_ip not in ("::", "0.0.0.0"):
        result.add(listened_ip)
    result.add(settings_dict["SERVER_NAME"])
    return list(sorted(result))


allowed_hosts.required_settings = ["SERVER_NAME", "LISTEN_ADDRESS"]


def csrf_trusted_origins(settings_dict) -> List[str]:
    """Return a list of CSRF origins."""
    # noinspection PyPackageRequirements
    from django import VERSION

    if VERSION[0] >= 4:
        # do not append a slash at the end, so cannot reuse SERVER_BASE_URL
        if settings_dict["SERVER_PORT"] == 443 and settings_dict["USE_SSL"]:
            return [
                f"https://{settings_dict['SERVER_NAME']}",
                f"https://{settings_dict['SERVER_NAME']}:443",
            ]
        elif settings_dict["SERVER_PORT"] == 80 and not settings_dict["USE_SSL"]:
            return [
                f"http://{settings_dict['SERVER_NAME']}",
                f"http://{settings_dict['SERVER_NAME']}:80",
            ]
        elif settings_dict["USE_SSL"]:
            return [
                f"https://{settings_dict['SERVER_NAME']}:{settings_dict['SERVER_PORT']}"
            ]
        return [f"http://{settings_dict['SERVER_NAME']}:{settings_dict['SERVER_PORT']}"]
    return [
        f"{settings_dict['SERVER_NAME']}",
        f"{settings_dict['SERVER_NAME']}:{settings_dict['SERVER_PORT']}",
    ]


csrf_trusted_origins.required_settings = ["SERVER_NAME", "SERVER_PORT", "USE_SSL"]


def secure_hsts_seconds(settings_dict) -> int:
    """Return the duration of the HSTS, depending on the use of SSL."""
    if settings_dict["USE_SSL"]:
        return 86400 * 31 * 12
    return 0


secure_hsts_seconds.required_settings = ["USE_SSL"]


def url_parse_server_name(settings_dict) -> str:
    """Return the public hostname, given the public base URL.

    >>> url_parse_server_name({'SERVER_BASE_URL': 'https://demo.example.org/'})
    'demo.example.org'

    """
    return urlparse(settings_dict["SERVER_BASE_URL"]).hostname or "localhost"


url_parse_server_name.required_settings = ["SERVER_BASE_URL"]


def url_parse_server_port(settings_dict) -> int:
    """Return the public port, given the public base URL.

    >>> url_parse_server_port({'SERVER_BASE_URL': 'https://demo.example.org/', 'USE_SSL': True})
    443
    >>> url_parse_server_port({'SERVER_BASE_URL': 'http://demo.example.org/', 'USE_SSL': False})
    80
    >>> url_parse_server_port({'SERVER_BASE_URL': 'https://demo.example.org:8010/', 'USE_SSL': True})
    8010

    """
    port = urlparse(settings_dict["SERVER_BASE_URL"]).port
    https_port = settings_dict["USE_SSL"] and 443
    return port or https_port or 80


url_parse_server_port.required_settings = ["SERVER_BASE_URL", "USE_SSL"]


def url_parse_server_protocol(settings_dict) -> str:
    """Return the public HTTP protocol, given the public base URL.

    >>> url_parse_server_protocol({'USE_SSL': True})
    'https'

    >>> url_parse_server_protocol({'USE_SSL': False})
    'http'

    """
    return "https" if settings_dict["USE_SSL"] else "http"


url_parse_server_protocol.required_settings = ["USE_SSL"]


def url_parse_prefix(settings_dict) -> str:
    """Return the public URL prefix, given the public base URL.

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


def url_parse_ssl(settings_dict) -> bool:
    """Return True if the public URL uses HTTPS.

    >>> url_parse_ssl({'SERVER_BASE_URL': 'https://demo.example.org/demo/'})
    True
    >>> url_parse_ssl({'SERVER_BASE_URL': 'http://demo.example.org/'})
    False

    """
    return urlparse(settings_dict["SERVER_BASE_URL"]).scheme == "https"


url_parse_ssl.required_settings = ["SERVER_BASE_URL"]


def use_x_forwarded_for(settings_dict) -> bool:
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


def project_name(settings_dict) -> str:
    """Transform the base module name into a nicer project name.

    >>> project_name({'DF_MODULE_NAME': 'my_project'})
    'My Project'
    """
    return " ".join(
        [
            x.capitalize()
            for x in settings_dict["DF_MODULE_NAME"].replace("_", " ").split()
        ]
    )


project_name.required_settings = ["DF_MODULE_NAME"]


class AutocreateSecretKey(AutocreateFileContent):
    """Generate a secret key and store it in a file."""

    def __init__(self, filename):
        """Generate a secret key and store it in a file."""
        super().__init__(filename, generate_secret_key, mode=0o600, length=60)


def generate_secret_key(django_ready, length=60) -> str:
    """Generate a default random secret key."""
    if not django_ready:
        return get_random_string(length=length)
    # noinspection PyPackageRequirements
    from django.conf import settings

    return settings.SECRET_KEY


def required_packages(settings_dict) -> List[str]:
    """Return a sorted list of the Python packages required by the current project.

    Issue  a warning for each missing package.
    """
    checked_packages: Set[str] = set()

    def get_requirements(package_name, parent=None) -> Iterable[str]:
        if package_name not in checked_packages:
            checked_packages.add(package_name)
            try:
                yield str(package_name)
                d = distribution(package_name)
                for r in d.requires:
                    r, __, __ = r.partition(";")
                    r, __, __ = r.partition("(")
                    r = r.strip()
                    for required_package in get_requirements(r, parent=package_name):
                        yield str(required_package)
            except PackageNotFoundError:
                settings_check_results.append(
                    missing_package(str(package_name), f" by {parent}")
                )
            except Exception as e:
                settings_check_results.append(
                    missing_package(str(package_name), f" by {parent} ({e})")
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
    """Exclude some Django commands that have no use of the end-user."""

    required_settings = ["DEVELOPMENT", "USE_CELERY", "DEBUG"]

    def __call__(self, settings_dict):
        """Exclude django commands in production mode."""
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
        """Return a useful representation."""
        return "%s.%s" % (self.__module__, "excluded_django_commands")


excluded_django_commands = ExcludedDjangoCommands()


def get_asgi_application(settings_dict) -> str:
    """Return the ASGI application (depends of the use of websockets)."""
    if settings_dict["USE_WEBSOCKETS"]:
        application = "df_websockets.routing.application"
    else:
        application = "df_config.application.asgi_application"
    return application


get_asgi_application.required_settings = ["USE_WEBSOCKETS"]


# noinspection PyUnusedLocal
def get_wsgi_application(settings_dict) -> str:
    """Return the WSGI application."""
    return "df_config.application.wsgi_application"


get_wsgi_application.required_settings = []


def use_sentry(settings_dict: Dict) -> bool:
    """Guess if Sentry is available."""
    sentry_dsn = settings_dict["SENTRY_DSN"]
    if not sentry_dsn:
        return False
    if not is_package_present("sentry_sdk"):
        settings_check_results.append(
            Warning("sentry_sdk must be installed.", obj="configuration")
        )
        return False
    # noinspection PyUnresolvedReferences
    import sentry_sdk

    # noinspection PyUnresolvedReferences
    from sentry_sdk.integrations.django import DjangoIntegration

    integrations = [DjangoIntegration()]
    if settings_dict["USE_CELERY"]:
        # noinspection PyUnresolvedReferences
        from sentry_sdk.integrations.celery import CeleryIntegration

        integrations.append(CeleryIntegration())
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=integrations,
        traces_sample_rate=1.0,
        debug=settings_dict["DEBUG"],
        send_default_pii=True,
    )
    return True


use_sentry.required_settings = ["SENTRY_DSN", "USE_CELERY", "DEBUG"]


# noinspection PyUnusedLocal
def web_server(settings_dict) -> str:
    """Provide a valid server (daphne if available, uvicorn or gunicorn)."""
    for server_name in "daphne", "gunicorn", "uvicorn":
        if is_package_present(server_name):
            return server_name
    return "gunicorn"


web_server.required_settings = []


def csp_connect(settings_dict) -> List[str]:
    """Return a valid value for the CSP connect option."""
    values = ["'self'"]
    if settings_dict.get("USE_SSL") and settings_dict.get("USE_WEBSOCKETS"):
        values.append("wss://%(SERVER_NAME)s:%(SERVER_PORT)s" % settings_dict)
    elif settings_dict.get("USE_WEBSOCKETS"):
        values.append("ws://%(SERVER_NAME)s:%(SERVER_PORT)s" % settings_dict)
    return values


web_server.required_settings = [
    "USE_SSL",
    "SERVER_NAME",
    "USE_WEBSOCKETS",
    "SERVER_PORT",
]
