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

"""Default values for all Django settings
======================================

Define settings for deploying most of df_config-based websites or for running them in `DEBUG` mode.
Most of them are used by Django, some of them by common third-party packages and the other ones are
used by DjangoFloor.

df_config also allows references between settings: for example, you only defines `SERVER_BASE_URL`
(like 'https://www.example.com/site/' ) and `SERVER_NAME` ('www.example.com'), `SERVER_PORT` ('443'),
`USE_SSL` ('True'), `SERVER_PROTOCOL` ('https') and `URL_PREFIX` ('/site/') are deduced.

These settings are defined in :mod:`df_config.config.defaults`.
Settings that should be customized on each installation (like the server name or the database password) can be
written in .ini files. The mapping between the Python setting and the [section/option] system is defined in
:mod:`df_config.iniconf`.

.. literalinclude:: ../../../../../df_config/config/defaults.py
   :language: python
   :lines: 41-1000

"""
import os

from df_config.guesses.djt import guess_djt_panels
from django.utils.translation import gettext_lazy as _

# ######################################################################################################################
#
# detect if some external packages are available, to automatically customize some settings
#
# ######################################################################################################################
from df_config.config.dynamic_settings import (
    AutocreateFile,
    CallableSetting,
    Directory,
    ExpandIterable,
    Path,
    SettingReference,
)
from df_config.guesses.apps import allauth_provider_apps, installed_apps, middlewares
from df_config.guesses.auth import (
    authentication_backends,
    ldap_attribute_map,
    ldap_boolean_attribute_map,
    ldap_group_class,
    ldap_group_search,
    ldap_user_search,
    CookieName,
)
from df_config.guesses.databases import (
    cache_redis_url,
    cache_setting,
    celery_broker_url,
    databases,
    session_redis_dict,
    websocket_redis_dict,
    websocket_redis_channels, celery_result_url,
)
from df_config.guesses.log import log_configuration
from df_config.guesses.misc import (
    DefaultListenAddress,
    allowed_hosts,
    excluded_django_commands,
    project_name,
    required_packages,
    secure_hsts_seconds,
    smart_hostname,
    template_setting,
    url_parse_prefix,
    url_parse_server_name,
    url_parse_server_port,
    url_parse_server_protocol,
    url_parse_ssl,
    use_x_forwarded_for,
    AutocreateSecretKey,
    get_asgi_application,
    get_wsgi_application,
    use_sentry,
    web_server, csp_connect,
)
from df_config.guesses.pipeline import (
    pipeline_compilers,
    pipeline_css_compressor,
    pipeline_js_compressor,
)
from df_config.guesses.staticfiles import (
    pipeline_enabled,
    static_finder,
    static_storage,
)
from df_config.utils import guess_version, is_package_present

try:
    import django_redis  # does not work with is_package_present (???)

    USE_REDIS_CACHE = True
except ImportError:
    django_redis = None
    USE_REDIS_CACHE = False
USE_CELERY = is_package_present("celery")
USE_REDIS_SESSIONS = is_package_present("redis_sessions")
USE_PIPELINE = is_package_present("pipeline")
USE_DEBUG_TOOLBAR = is_package_present("debug_toolbar")
USE_ALL_AUTH = is_package_present("allauth")
USE_WEBSOCKETS = is_package_present("df_websockets")
USE_SITE = is_package_present("df_site")
USE_WHITENOISE = is_package_present("whitenoise")
USE_CSP = is_package_present("csp")

# ######################################################################################################################
#
# settings that could be kept as-is for most projects
# of course, you can override them in your default settings
#
# ######################################################################################################################
ADMINS = (("admin", "{ADMIN_EMAIL}"),)
ALLOWED_HOSTS = CallableSetting(allowed_hosts)
CACHE_URL = CallableSetting(cache_redis_url)
CACHES = CallableSetting(cache_setting)
CSRF_COOKIE_DOMAIN = "{SERVER_NAME}"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_NAME = CallableSetting(CookieName("csrftoken"))
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = SettingReference("USE_SSL")
CSRF_TRUSTED_ORIGINS = ["{SERVER_NAME}", "{SERVER_NAME}:{SERVER_PORT}"]
DATABASES = CallableSetting(databases)

DEBUG = False
# you should create a "local_settings.py" with "DEBUG = True" at the root of your project
DEVELOPMENT = True
# display all commands (like "migrate" or "runserver") in manage.py
# if False, development-specific commands are hidden

DEFAULT_FROM_EMAIL = "webmaster@{SERVER_NAME}"
FILE_UPLOAD_TEMP_DIR = Directory("{LOCAL_PATH}/tmp-uploads")
INSTALLED_APPS = CallableSetting(installed_apps)
LANGUAGE_COOKIE_NAME = CallableSetting(CookieName("django_language"))
LANGUAGE_COOKIE_DOMAIN = "{SERVER_NAME}"
LANGUAGE_COOKIE_SAMESITE = "Lax"
LANGUAGE_COOKIE_SECURE = SettingReference("USE_SSL")
LOGGING = CallableSetting(log_configuration)
MANAGERS = SettingReference("ADMINS")
MEDIA_ROOT = Directory("{LOCAL_PATH}/media", mode=0o755)
MEDIA_URL = "/media/"
MIDDLEWARE = CallableSetting(middlewares)

ROOT_URLCONF = "df_config.root_urls"
SECRET_KEY = AutocreateSecretKey("{LOCAL_PATH}/secret_key.txt")
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = SettingReference("USE_SSL")
SECURE_HSTS_PRELOAD = SettingReference("USE_SSL")
SECURE_HSTS_SECONDS = CallableSetting(secure_hsts_seconds)
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)  # X-Forwarded-Proto or None
SECURE_SSL_REDIRECT = SettingReference("USE_SSL")
SECURE_FRAME_DENY = SettingReference("USE_SSL")
SERVER_EMAIL = "{ADMIN_EMAIL}"
SESSION_COOKIE_AGE = 1209600
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_NAME = CallableSetting(CookieName("sessionid"))
SESSION_COOKIE_DOMAIN = "{SERVER_NAME}"
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = SettingReference("USE_SSL")
TEMPLATES = CallableSetting(template_setting)
TEMPLATE_DEBUG = SettingReference("DEBUG")
TEMPLATE_DIRS = ()
TEMPLATE_CONTEXT_PROCESSORS = [
    "django.contrib.auth.context_processors.auth",
    "django.template.context_processors.debug",
    "django.template.context_processors.i18n",
    "django.template.context_processors.media",
    "django.template.context_processors.static",
    "django.template.context_processors.tz",
    "django.template.context_processors.request",
    "django.contrib.messages.context_processors.messages",
    "df_config.context_processors.config",
    ExpandIterable("DF_TEMPLATE_CONTEXT_PROCESSORS"),
]
TEST_RUNNER = "django.test.runner.DiscoverRunner"

USE_I18N = True
USE_L10N = True
USE_THOUSAND_SEPARATOR = True
USE_TZ = True
USE_X_FORWARDED_HOST = True  # X-Forwarded-Host
X_FRAME_OPTIONS = "SAMEORIGIN"
WSGI_APPLICATION = CallableSetting(get_wsgi_application)

# django.contrib.auth
AUTHENTICATION_BACKENDS = CallableSetting(authentication_backends)
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "{URL_PREFIX}"
# LOGOUT_REDIRECT_URL = '{URL_PREFIX}'

# django.contrib.sessions
SESSION_ENGINE = "django.contrib.sessions.backends.db"
if USE_REDIS_SESSIONS:
    SESSION_ENGINE = "redis_sessions.session"
SESSION_COOKIE_SECURE = SettingReference("USE_SSL")
CSRF_COOKIE_SECURE = SettingReference("USE_SSL")

# django.contrib.sites
SITE_ID = 1

# django.contrib.staticfiles
STATIC_ROOT = Directory("{LOCAL_PATH}/static", mode=0o755)
STATIC_URL = "/static/"
STATICFILES_STORAGE = CallableSetting(static_storage)
STATICFILES_FINDERS = CallableSetting(static_finder)

# celery
BROKER_URL = CallableSetting(celery_broker_url)
CELERY_DEFAULT_QUEUE = "celery"
CELERY_TIMEZONE = "{TIME_ZONE}"
CELERY_RESULT_EXCHANGE = "{DF_MODULE_NAME}_results"
CELERY_RESULT_BACKEND = CallableSetting(celery_result_url)
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json", "yaml", "msgpack"]
CELERY_APP = "df_websockets"
CELERY_CREATE_DIRS = True
CELERY_TASK_SERIALIZER = "json"

# df_config
DF_PROJECT_VERSION = CallableSetting(guess_version)
DATA_PATH = Directory("{LOCAL_PATH}/data")
SERVER_NAME = CallableSetting(url_parse_server_name)  # ~ www.example.org
SERVER_PORT = CallableSetting(url_parse_server_port)  # ~ 443
SERVER_PROTOCOL = CallableSetting(url_parse_server_protocol)  # ~ "https"
URL_PREFIX = CallableSetting(url_parse_prefix)
# something like "/prefix/" (but probably just "/")
USE_SSL = CallableSetting(url_parse_ssl)  # ~ True
USE_X_SEND_FILE = False  # Apache module
X_ACCEL_REDIRECT = []  # paths used by nginx
USE_HTTP_BASIC_AUTH = False  # HTTP-Authorization
USE_X_FORWARDED_FOR = CallableSetting(use_x_forwarded_for)  # X-Forwarded-For
DF_FAKE_AUTHENTICATION_USERNAME = None
DF_ALLOW_USER_CREATION = True

DF_SERVER = CallableSetting(
    web_server
)  # must be "gunicorn" or "daphne" / used by the server command
DF_REMOVED_DJANGO_COMMANDS = CallableSetting(excluded_django_commands)
DF_ALLOW_LOCAL_USERS = True
DF_CHECKED_REQUIREMENTS = CallableSetting(required_packages)

# df_websockets
WEBSOCKET_URL = "/ws/"  # set to None if you do not use websockets
# by default, use the same Redis as django-channels
WEBSOCKET_REDIS_CONNECTION = CallableSetting(websocket_redis_dict)
WEBSOCKET_SIGNAL_DECODER = "json.JSONDecoder"
WEBSOCKET_TOPIC_SERIALIZER = "df_websockets.topics.serialize_topic"
WEBSOCKET_SIGNAL_ENCODER = "django.core.serializers.json.DjangoJSONEncoder"
WEBSOCKET_REDIS_PREFIX = "ws"
WEBSOCKET_REDIS_EXPIRE = 36000
WINDOW_INFO_MIDDLEWARES = [
    "df_websockets.ws_middleware.WindowKeyMiddleware",
    "df_websockets.ws_middleware.DjangoAuthMiddleware",
    "df_websockets.ws_middleware.Djangoi18nMiddleware",
    "df_websockets.ws_middleware.BrowserMiddleware",
]
ASGI_APPLICATION = CallableSetting(get_asgi_application)

# django-channels
# noinspection PyUnresolvedReferences
CHANNEL_REDIS = CallableSetting(websocket_redis_channels)
CHANNEL_LAYERS = {"default": SettingReference("CHANNEL_REDIS")}

# django-pipeline
PIPELINE = {
    "PIPELINE_ENABLED": SettingReference("PIPELINE_ENABLED"),
    "JAVASCRIPT": SettingReference("PIPELINE_JS"),
    "STYLESHEETS": SettingReference("PIPELINE_CSS"),
    "CSS_COMPRESSOR": SettingReference("PIPELINE_CSS_COMPRESSOR"),
    "JS_COMPRESSOR": SettingReference("PIPELINE_JS_COMPRESSOR"),
    "COMPILERS": SettingReference("PIPELINE_COMPILERS"),
}
PIPELINE_COMPILERS = CallableSetting(pipeline_compilers)
PIPELINE_CSS_COMPRESSOR = CallableSetting(pipeline_css_compressor)
PIPELINE_JS_COMPRESSOR = CallableSetting(pipeline_js_compressor)
PIPELINE_CSS = {
    "django.admin": {
        "source_filenames": ["admin/css/base.css", "admin/css/responsive.css"],
        "output_filename": "css/django-admin.css",
        "extra_context": {"media": "all"},
    },
    "default": {
        "source_filenames": [ExpandIterable("DF_CSS")],
        "output_filename": "css/default.css",
        "extra_context": {"media": "all"},
    },
}
PIPELINE_ENABLED = CallableSetting(pipeline_enabled)
PIPELINE_JS = {
    "django.admin": {
        "source_filenames": [],
        "output_filename": "js/django-admin.js",
        "integrity": "sha384",
        "crossorigin": "anonymous",
    },
    "default": {
        "source_filenames": [ExpandIterable("DF_JS")],
        "output_filename": "js/default.js",
        "integrity": "sha384",
        "crossorigin": "anonymous",
    },
}
LIVE_SCRIPT_BINARY = "lsc"
LESS_BINARY = "lessc"
SASS_BINARY = "sass"
STYLUS_BINARY = "stylus"
BABEL_BINARY = "babel"
YUGLIFY_BINARY = "yuglify"
YUI_BINARY = "yuicompressor"
CLOSURE_BINARY = "closure"
UGLIFYJS_BINARY = "uglifyjs"
CSSTIDY_BINARY = "csstidy"
COFFEE_SCRIPT_BINARY = "coffee"
CSSMIN_BINARY = "cssmin"
TYPESCRIPT_BINARY = "tsc"
TYPESCRIPT_ARGUMENTS = []
CSSNANO_BINARY = "cssnano"
CSSNANO_ARGUMENTS = []
TERSER_BINARY = "terser"
TERSER_ARGUMENTS = []

# Django-All-Auth
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[{SERVER_NAME}] "
ACCOUNT_EMAIL_VERIFICATION = None
ALLAUTH_PROVIDER_APPS = CallableSetting(allauth_provider_apps)
ALLAUTH_APPLICATIONS_CONFIG = AutocreateFile("{LOCAL_PATH}/social_auth.ini", mode=0o600)
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = "username_email"
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "{SERVER_PROTOCOL}"
ACCOUNT_ADAPTER = "df_config.apps.allauth.AccountAdapter"

# Django-Debug-Toolbar
DEBUG_TOOLBAR_CONFIG = {"JQUERY_URL": "{STATIC_URL}vendor/jquery/dist/jquery.min.js"}
DEBUG_TOOLBAR_PATCH_SETTINGS = False
DEBUG_TOOLBAR_PANELS = CallableSetting(guess_djt_panels)
INTERNAL_IPS = ("127.0.0.1", "::1", "localhost")

# django-auth-ldap
AUTH_LDAP_SERVER_URI = None
AUTH_LDAP_BIND_DN = ""
AUTH_LDAP_BIND_PASSWORD = ""
AUTH_LDAP_USER_SEARCH_BASE = "ou=users,dc=example,dc=com"
AUTH_LDAP_FILTER = "(uid=%(user)s)"
AUTH_LDAP_USER_SEARCH = CallableSetting(ldap_user_search)
AUTH_LDAP_USER_DN_TEMPLATE = None
AUTH_LDAP_START_TLS = False
AUTH_LDAP_USER_ATTR_MAP = CallableSetting(ldap_attribute_map)
AUTH_LDAP_USER_FLAGS_BY_GROUP = CallableSetting(ldap_boolean_attribute_map)
AUTH_LDAP_MIRROR_GROUPS = False
AUTH_LDAP_USER_IS_ACTIVE = None
AUTH_LDAP_USER_IS_STAFF = None
AUTH_LDAP_USER_IS_SUPERUSER = None
AUTH_LDAP_USER_FIRST_NAME = None
AUTH_LDAP_USER_LAST_NAME = None
AUTH_LDAP_USER_EMAIL = None
AUTH_LDAP_GROUP_TYPE = CallableSetting(ldap_group_class)
AUTH_LDAP_GROUP_NAME = "posix"
AUTH_LDAP_ALWAYS_UPDATE_USER = True
AUTH_LDAP_REQUIRE_GROUP = None
AUTH_LDAP_DENY_GROUP = None
# Cache group memberships for an hour to minimize LDAP traffic
AUTH_LDAP_CACHE_GROUPS = True
AUTH_LDAP_GROUP_CACHE_TIMEOUT = 3600
# Use LDAP group membership to calculate group permissions.
AUTH_LDAP_FIND_GROUP_PERMS = False
AUTH_LDAP_GROUP_SEARCH = CallableSetting(ldap_group_search)
AUTH_LDAP_GROUP_SEARCH_BASE = "ou=groups,dc=example,dc=com"
AUTH_LDAP_AUTHORIZE_ALL_USERS = True

# django-cors-headers
CORS_ORIGIN_WHITELIST = ("{SERVER_NAME}", "{SERVER_NAME}:{SERVER_PORT}")
CORS_REPLACE_HTTPS_REFERER = False

# django-hosts
DEFAULT_HOST = "{SERVER_NAME}"
HOST_SCHEME = "{SERVER_PROTOCOL}://"
HOST_PORT = "{SERVER_PORT}"

# django—pam
USE_PAM_AUTHENTICATION = False

# django-radius
RADIUS_SERVER = None
RADIUS_PORT = None
RADIUS_SECRET = None

# django-redis-sessions
SESSION_REDIS = CallableSetting(session_redis_dict)

# django-smart-selects
USE_DJANGO_JQUERY = True
JQUERY_URL = False

# django-csp
CSP_CONNECT_SRC = CallableSetting(csp_connect)
CSP_BLOCK_ALL_MIXED_CONTENT = True

# ######################################################################################################################
#
# settings that should be customized for each project
# of course, you can redefine or override any setting
#
# ######################################################################################################################
# df_config
DF_CSS = []
DF_JS = []
DF_INDEX_VIEW = None
DF_SITE_SEARCH_VIEW = None  # 'djangofloor.views.search.UserSearchView'
DF_PROJECT_NAME = CallableSetting(project_name)
DF_URL_CONF = "{DF_MODULE_NAME}.urls.urlpatterns"
DF_ADMIN_SITE = "django.contrib.admin.site"
DF_JS_CATALOG_VIEWS = ["django.contrib.admin"]
# noinspection PyUnresolvedReferences
DF_INSTALLED_APPS = ["{DF_MODULE_NAME}"]  # your django app!
DF_MIDDLEWARE = []
DF_TEMPLATE_CONTEXT_PROCESSORS = []
DF_PIP_NAME = "{DF_MODULE_NAME}"  # anything such that "python -m pip install {DF_PIP_NAME}" installs your project
# only used in docs
DF_REMOTE_USER_HEADER = None  # HTTP_REMOTE_USER
DF_DEFAULT_GROUPS = [_("Users")]
NPM_FILE_PATTERNS = {
    "bootstrap-notify": ["*.js"],
    "font-awesome": ["css/*", "fonts/*"],
    "html5shiv": ["dist/*"],
    "jquery": ["dist/*"],
    "jquery-file-upload": ["css/*", "js/*"],
    "respond.js": ["dest/*"],
}
# used by the "npm" command: downloads these packages and copies the files matching any pattern in the list
LOG_REMOTE_ACCESS = True
LOG_DIRECTORY = Directory("{LOCAL_PATH}/log")
LOG_EXCLUDED_COMMANDS = {
    "clearsessions",
    "check",
    "compilemessages",
    "collectstatic",
    "config",
    "createcachetable",
    "changepassword",
    "createsuperuser",
    "dumpdb",
    "dbshell",
    "dumpdata",
    "flush",
    "loaddata",
    "inspectdb",
    "makemessages",
    "makemigrations",
    "migrate",
    "npm",
    "packaging",
    "ping_google",
    "remove_stale_contenttypes",
    "sendtestemail",
    "shell",
    "showmigrations",
    "sqlflush",
    "sqlmigrate",
    "sqlsequencereset",
    "squashmigrations",
    "startapp",
    "test",
    "testserver",
}

# ######################################################################################################################
#
# settings that should be customized for each deployment
# {DF_MODULE_NAME}.iniconf:INI_MAPPING should be a list of ConfigField, allowing to define these settings in a .ini file
#
# ######################################################################################################################
ADMIN_EMAIL = "admin@{SERVER_NAME}"  # aliased in settings.ini as "[global]admin_email"
DATABASE_ENGINE = "sqlite3"  # aliased in settings.ini as "[database]engine"
DATABASE_NAME = Path(
    "{LOCAL_PATH}/database.sqlite3"
)  # aliased in settings.ini as "[database]name"
DATABASE_USER = ""  # aliased in settings.ini as "[database]user"
DATABASE_PASSWORD = ""  # aliased in settings.ini as "[database]password"
DATABASE_HOST = ""  # aliased in settings.ini as "[database]host"
DATABASE_PORT = ""  # aliased in settings.ini as "[database]port"
DATABASE_OPTIONS = {}
EMAIL_HOST = "localhost"  # aliased in settings.ini as "[email]host"
EMAIL_HOST_PASSWORD = ""  # aliased in settings.ini as "[email]password"
EMAIL_HOST_USER = ""  # aliased in settings.ini as "[email]user"
EMAIL_FROM = "{ADMIN_EMAIL}"  # aliased in settings.ini as "[email]from"
EMAIL_PORT = 25  # aliased in settings.ini as "[email]port"
EMAIL_SUBJECT_PREFIX = "[{SERVER_NAME}] "
EMAIL_USE_TLS = False  # aliased in settings.ini as "[email]use_tls"
EMAIL_USE_SSL = False  # aliased in settings.ini as "[email]use_ssl"
EMAIL_SSL_CERTFILE = None
EMAIL_SSL_KEYFILE = None
LANGUAGE_CODE = "en"  # aliased in settings.ini as "[global]language_code"
TIME_ZONE = "Europe/Paris"  # aliased in settings.ini as "[global]time_zone"
LOG_REMOTE_URL = None  # aliased in settings.ini as "[global]log_remote_url"
LOG_LEVEL = None
SERVER_BASE_URL = CallableSetting(
    smart_hostname
)  # aliased in settings.ini as "[global]server_url"

# df_config
LISTEN_ADDRESS = DefaultListenAddress(
    9000
)  # aliased in settings.ini as "[global]listen_address"
LOCAL_PATH = "./django_data"  # aliased in settings.ini as "[global]data"
__split_path = __file__.split(os.path.sep)
if "lib" in __split_path:
    prefix = os.path.join(*__split_path[: __split_path.index("lib")])
    LOCAL_PATH = Directory("/%s/var/{DF_MODULE_NAME}" % prefix)

# django-redis-sessions
SESSION_REDIS_PROTOCOL = "redis"
SESSION_REDIS_HOST = "localhost"  # aliased in settings.ini as "[session]host"
SESSION_REDIS_PORT = 6379  # aliased in settings.ini as "[session]port"
SESSION_REDIS_DB = 1  # aliased in settings.ini as "[session]db"
SESSION_REDIS_PASSWORD = None  # aliased in settings.ini as "[session]password"

# django_redis (cache)
CACHE_PROTOCOL = "redis"
CACHE_HOST = "localhost"  # aliased in settings.ini as "[cache]host"
CACHE_PORT = 6379  # aliased in settings.ini as "[cache]port"
CACHE_DB = 2  # aliased in settings.ini as "[cache]db"
CACHE_PASSWORD = None  # aliased in settings.ini as "[cache]password"

# websockets
WEBSOCKET_REDIS_PROTOCOL = "redis"
WEBSOCKET_REDIS_HOST = "localhost"  # aliased in settings.ini as "[websocket]host"
WEBSOCKET_REDIS_PORT = 6379  # aliased in settings.ini as "[websocket]port"
WEBSOCKET_REDIS_DB = 3  # aliased in settings.ini as "[websocket]db"
WEBSOCKET_REDIS_PASSWORD = None  # aliased in settings.ini as "[websocket]password"

# celery
CELERY_PROTOCOL = "redis"
CELERY_HOST = "localhost"  # aliased in settings.ini as "[celery]host"
CELERY_PORT = 6379  # aliased in settings.ini as "[celery]port"
CELERY_DB = 4  # aliased in settings.ini as "[celery]db"
CELERY_PASSWORD = None  # aliased in settings.ini as "[celery]password"
CELERY_USERNAME = None  # only useful for amqp
CELERY_PROCESSES = 4

# celery
CELERY_RESULT_PROTOCOL = SettingReference("CELERY_PROTOCOL")
CELERY_RESULT_HOST = SettingReference("CELERY_HOST")
CELERY_RESULT_PORT = SettingReference("CELERY_PORT")
CELERY_RESULT_DB = SettingReference("CELERY_DB")
CELERY_RESULT_PASSWORD = SettingReference("CELERY_PASSWORD")
CELERY_RESULT_USERNAME = SettingReference("CELERY_USERNAME")

# sentry.io
USE_SENTRY = CallableSetting(use_sentry)
SENTRY_DSN = None
