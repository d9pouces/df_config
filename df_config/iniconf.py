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
"""List of external settings (via .ini or environment variables)."""
import re
from ipaddress import ip_address
from typing import List

from django.core.exceptions import ImproperlyConfigured

from df_config.config.fields import (
    BooleanConfigField,
    CharConfigField,
    ChoiceConfigFile,
    ConfigField,
    DirectoryPathConfigField,
    FloatConfigField,
    IntegerConfigField,
    ListConfigField,
    bool_setting,
)


def x_accel_converter(value):
    """Return the list of file paths that can be accelerated when the X-Accel-redirect directive of nginx is used."""
    if bool_setting(value):
        return [("{MEDIA_ROOT}/", "{MEDIA_URL}")]
    return []


def normalize_listen_address(value: str) -> str:
    """Check if the listen address is a valid value."""
    address, sep, port = value.rpartition(":")
    if sep != ":" and address:
        raise ImproperlyConfigured(
            "Listen address must be in the form 'address:port' or 'port'."
        )
    elif not address:
        address = "0.0.0.0"
    if not re.match(r"^[1-9]\d*$", port) or not 1 <= int(port) <= 65535:
        raise ImproperlyConfigured("Listen port must be a valid port number.")
    try:
        address = ip_address(address)
    except ValueError:
        raise ImproperlyConfigured(
            "Listen address must be in the form 'address:port' or 'port'."
        )
    return f"{address.compressed}:{port}"


ALLAUTH_MAPPING = []
BASE_MAPPING = [
    CharConfigField(
        "global.admin_email",
        "ADMIN_EMAIL",
        help_str="e-mail address for receiving logged errors",
        env_name="ADMIN_EMAIL",
    ),
    CharConfigField(
        None,
        "SECRET_KEY",
        help_str="Secret key to provide cryptographic signing, and should be set to a unique, unpredictable value.",
        env_name="SECRET_KEY",
    ),
    DirectoryPathConfigField(
        "global.data",
        "LOCAL_PATH",
        help_str="where all data will be stored (static/uploaded/temporary files, …). "
        "If you change it, you must run the collectstatic and migrate commands again.\n",
    ),
    DirectoryPathConfigField(
        "global.upload_directory",
        "MEDIA_ROOT",
        help_str="where uploaded media files will be stored.",
        env_name="UPLOAD_DIRECTORY",
    ),
    CharConfigField(
        "global.s3_region",
        "MINIO_STORAGE_REGION",
        help_str="S3 storage regions, when S3 storage is used for storing uplaoded media.",
        env_name="S3_REGION",
    ),
    DirectoryPathConfigField(
        "global.data",
        "FILE_UPLOAD_TEMP_DIR",
        help_str="where temporary data will be stored.",
        env_name="TEMP_DIRECTORY",
    ),
    CharConfigField(
        "global.language_code",
        "LANGUAGE_CODE",
        help_str="default to fr_FR",
        env_name="LANGUAGE_CODE",
    ),
    CharConfigField(
        "global.listen_address",
        "LISTEN_ADDRESS",
        help_str="Address listen by your web server (like 127.0.0.1:8000 or :8000).",
        from_str=normalize_listen_address,
    ),
    CharConfigField(
        "global.server_url",
        "SERVER_BASE_URL",
        help_str="Public URL of your website. \n"
        'Default to "http://{listen_address}/" but should '
        "be different if you use a reverse proxy like "
        "Apache or Nginx. Example: http://www.example.org/.",
        env_name="SERVER_URL",
    ),
    CharConfigField(
        None,
        "HEROKU_APP_NAME",
        help_str="Heroku's application name, when deploying your on Heroku.",
        env_name="HEROKU_APP_NAME",
    ),
    CharConfigField(
        "global.time_zone",
        "TIME_ZONE",
        help_str="default to Europe/Paris",
        env_name="TIME_ZONE",
    ),
    CharConfigField(
        None,
        "EMAIL_HOST_URL",
        help_str="SMTP server for sending admin emails. \n"
        "smtp+tls://account@example.com:password@smtp.example.com:587/",
        env_name="EMAIL_HOST_URL",
    ),
    CharConfigField("email.host", "EMAIL_HOST", help_str="SMTP server"),
    CharConfigField("email.password", "EMAIL_HOST_PASSWORD", help_str="SMTP password"),
    IntegerConfigField(
        "email.port", "EMAIL_PORT", help_str="SMTP port (often 25, 465 or 587)"
    ),
    CharConfigField("email.user", "EMAIL_HOST_USER", help_str="SMTP user"),
    CharConfigField(
        "email.from",
        "DEFAULT_FROM_EMAIL",
        help_str="Displayed sender email",
        env_name="EMAIL_FROM",
    ),
    BooleanConfigField(
        "email.use_tls",
        "EMAIL_USE_TLS",
        help_str='"true" if your SMTP uses STARTTLS ' "(often on port 587)",
    ),
    BooleanConfigField(
        "email.use_ssl",
        "EMAIL_USE_SSL",
        help_str='"true" if your SMTP uses SSL (often on port 465)',
    ),
]
CELERY_MAPPING = [
    IntegerConfigField(
        "celery.db",
        "CELERY_DB",
        help_str="Database number of the Redis Celery DB\n"
        "Celery is used for processing background tasks and websockets.",
    ),
    CharConfigField("celery.host", "CELERY_HOST", help_str="Redis Celery DB host"),
    CharConfigField(
        "celery.password",
        "CELERY_PASSWORD",
        help_str="Redis Celery DB password (if required)",
    ),
    IntegerConfigField("celery.port", "CELERY_PORT", help_str="Redis Celery DB port"),
    IntegerConfigField(
        "celery.processes", "CELERY_PROCESSES", help_str="number of Celery processes"
    ),
]
DATABASE_MAPPING = [
    CharConfigField(
        None,
        "DATABASE_URL",
        help_str="URL of the database (e.g. (e.g. (postgres|mysql)://username:password@127.0.0.1:5432/database"
        "?ssl_mode=verify-full"
        "&ssl_certfile=./etc/client.crt"
        "&ssl_keyfile=./etc/client.key"
        "&ssl_ca_certs=./etc/ca.crt)",
        env_name="DATABASE_URL",
    ),
    CharConfigField(
        "database.db",
        "DATABASE_NAME",
        help_str="Database name (or path of the sqlite3 database)",
        env_name=None,
    ),
    CharConfigField(
        "database.engine",
        "DATABASE_ENGINE",
        help_str='Database engine ("mysql", "postgresql", "sqlite3", "oracle", or the dotted name of '
        "the Django backend)",
        env_name=None,
    ),
    CharConfigField(
        "database.host", "DATABASE_HOST", help_str="Database host", env_name=None
    ),
    CharConfigField(
        "database.password",
        "DATABASE_PASSWORD",
        help_str="Database password",
        env_name=None,
    ),
    IntegerConfigField(
        "database.port", "DATABASE_PORT", help_str="Database port", env_name=None
    ),
    CharConfigField(
        "database.user", "DATABASE_USER", help_str="Database user", env_name=None
    ),
]
DJANGO_AUTH_MAPPING = [
    BooleanConfigField(
        "auth.local_users",
        "DF_ALLOW_LOCAL_USERS",
        help_str='Set to "false" to deactivate local database of users.',
    ),
    BooleanConfigField(
        "auth.create_users",
        "DF_ALLOW_USER_CREATION",
        help_str='Set to "false" if users cannot create their account themselvers, or '
        "only if existing users can by authenticated by the reverse-proxy.",
    ),
    IntegerConfigField(
        "auth.session_duration",
        "SESSION_COOKIE_AGE",
        help_str="Duration of the connection sessions "
        "(in seconds, default to 1,209,600 s / 14 days)",
    ),
    BooleanConfigField(
        "auth.allow_basic_auth",
        "USE_HTTP_BASIC_AUTH",
        help_str='Set to "true" if you want to allow HTTP basic auth, using the Django database.',
    ),
]  # type: List[ConfigField]
LDAP_AUTH_MAPPING = [
    CharConfigField(
        "auth.ldap_server_url",
        "AUTH_LDAP_SERVER_URI",
        help_str='URL of your LDAP server, like "ldap://ldap.example.com". '
        'Python packages "pyldap" and "django-auth-ldap" must be installed.'
        "Can be used for retrieving attributes of users authenticated by the reverse proxy",
    ),
    CharConfigField(
        "auth.ldap_bind_dn",
        "AUTH_LDAP_BIND_DN",
        help_str="Bind dn for LDAP authentication",
    ),
    CharConfigField(
        "auth.ldap_bind_password",
        "AUTH_LDAP_BIND_PASSWORD",
        help_str="Bind password for LDAP authentication",
    ),
    CharConfigField(
        "auth.ldap_user_search_base",
        "AUTH_LDAP_USER_SEARCH_BASE",
        help_str="Search base for LDAP authentication by direct after an search, "
        'like "ou=users,dc=example,dc=com".',
    ),
    CharConfigField(
        "auth.ldap_filter",
        "AUTH_LDAP_FILTER",
        help_str='Filter for LDAP authentication, like "(uid=%%(user)s)" (the default),'
        ' the double "%%" is required in .ini files.',
    ),
    CharConfigField(
        "auth.ldap_direct_bind",
        "AUTH_LDAP_USER_DN_TEMPLATE",
        help_str="Set it for a direct LDAP bind and to skip the LDAP search, "
        'like "uid=%%(user)s,ou=users,dc=example,dc=com". '
        '%%(user)s is the only allowed variable and the double "%%" is required in .ini files.',
    ),
    BooleanConfigField(
        "auth.ldap_start_tls",
        "AUTH_LDAP_START_TLS",
        help_str='Set to "true" if you want to use StartTLS.',
    ),
    CharConfigField(
        "auth.ldap_first_name_attribute",
        "AUTH_LDAP_USER_FIRST_NAME",
        help_str='LDAP attribute for the user\'s first name, like "givenName".',
    ),
    CharConfigField(
        "auth.ldap_last_name_attribute",
        "AUTH_LDAP_USER_LAST_NAME",
        help_str='LDAP attribute for the user\'s last name, like "sn".',
    ),
    CharConfigField(
        "auth.ldap_email_attribute",
        "AUTH_LDAP_USER_EMAIL",
        help_str='LDAP attribute for the user\'s email, like "email".',
    ),
    CharConfigField(
        "auth.ldap_is_active_group",
        "AUTH_LDAP_USER_IS_ACTIVE",
        help_str='LDAP group DN for active users, like "cn=active,ou=groups,dc=example,dc=com"',
    ),
    CharConfigField(
        "auth.ldap_is_staff_group",
        "AUTH_LDAP_USER_IS_STAFF",
        help_str='LDAP group DN for staff users, like "cn=staff,ou=groups,dc=example,dc=com".',
    ),
    CharConfigField(
        "auth.ldap_is_superuser_group",
        "AUTH_LDAP_USER_IS_SUPERUSER",
        help_str='LDAP group DN for superusers, like "cn=superuser,ou=groups,dc=example,dc=com".',
    ),
    CharConfigField(
        "auth.ldap_require_group",
        "AUTH_LDAP_REQUIRE_GROUP",
        help_str="only authenticates users belonging to this group. Must be something like "
        '"cn=enabled,ou=groups,dc=example,dc=com".',
    ),
    CharConfigField(
        "auth.ldap_deny_group",
        "AUTH_LDAP_DENY_GROUP",
        help_str="authentication is denied for users belonging to this group. Must be something like "
        '"cn=disabled,ou=groups,dc=example,dc=com".',
    ),
    BooleanConfigField(
        "auth.ldap_mirror_groups",
        "AUTH_LDAP_MIRROR_GROUPS",
        help_str="Mirror LDAP groups at each user login",
    ),
    CharConfigField(
        "auth.ldap_group_search_base",
        "AUTH_LDAP_GROUP_SEARCH_BASE",
        help_str='Search base for LDAP groups, like "ou=groups,dc=example,dc=com"',
    ),
    ChoiceConfigFile(
        "auth.ldap_group_type",
        "AUTH_LDAP_GROUP_NAME",
        choices={
            "posix": "django_auth_ldap.config.PosixGroupType",
            "nis": "django_auth_ldap.config.NISGroupType",
            "GroupOfNames": "django_auth_ldap.config.GroupOfNamesType",
            "NestedGroupOfNames": "django_auth_ldap.config.NestedGroupOfNamesType",
            "GroupOfUniqueNames": "django_auth_ldap.config.GroupOfUniqueNamesType",
            "NestedGroupOfUniqueNames": "django_auth_ldap.config.NestedGroupOfUniqueNamesType",
            "ActiveDirectory": "django_auth_ldap.config.ActiveDirectoryGroupType",
            "NestedActiveDirectory": "django_auth_ldap.config.NestedActiveDirectoryGroupType",
            "OrganizationalRole": "django_auth_ldap.config.OrganizationalRoleGroupType",
            "NestedOrganizationalRole": "django_auth_ldap.config.NestedOrganizationalRoleGroupType",
        },
        help_str="Type of LDAP groups.",
    ),
]
HTTP_AUTH_MAPPING = [
    CharConfigField(
        "auth.remote_user_header",
        "DF_REMOTE_USER_HEADER",
        help_str='Set it if the reverse-proxy authenticates users, a common value is "HTTP_REMOTE_USER". '
        "Note: the HTTP_ prefix is automatically added, just set REMOTE_USER in the "
        "reverse-proxy configuration. ",
        env_name="REMOTE_USER_HEADER",
    ),
    ListConfigField(
        "auth.remote_user_groups",
        "DF_DEFAULT_GROUPS",
        help_str="Comma-separated list of groups, for new users that are automatically created "
        "when authenticated by remote_user_header. Ignored if groups are read from a LDAP "
        "server. ",
        env_name="REMOTE_USER_GROUPS_HEADER",
    ),
]
LOG_MAPPING = [
    CharConfigField(
        "global.log_remote_url",
        "LOG_REMOTE_URL",
        help_str="Send logs to a syslog service. \n"
        "Examples: syslog+tcp://localhost:514/user, syslog:///local7 "
        "or syslog:///dev/log/daemon.",
        env_name="LOG_REMOTE_URL",
    ),
    CharConfigField(
        "global.log_sentry_dsn",
        "SENTRY_DSN",
        help_str="sentry DSN (see https://sentry.io/)",
        env_name="SENTRY_DSN",
    ),
    CharConfigField(
        "global.log_directory",
        "LOG_DIRECTORY",
        help_str="Write all local logs to this directory.",
        env_name="LOG_DIRECTORY",
    ),
    ChoiceConfigFile(
        "global.log_level",
        "LOG_LEVEL",
        help_str="Log level (one of 'debug', 'info', 'warn', 'error' or 'critical').",
        choices={
            "debug": "DEBUG",
            "info": "INFO",
            "warn": "WARN",
            "error": "ERROR",
            "critical": "CRITICAL",
        },
        env_name="LOG_LEVEL",
    ),
    BooleanConfigField(
        "global.log_remote_access",
        "LOG_REMOTE_ACCESS",
        help_str="If true, log of HTTP connections are also sent to syslog/logd.",
    ),
    FloatConfigField(
        "global.log_slow_query_duration_in_s",
        "LOG_SLOW_QUERY_DURATION_IN_S",
        help_str="Log slow queries that take more than this time (in seconds).",
        env_name="LOG_SLOW_QUERY_DURATION_IN_S",
    ),
]
PAM_AUTH_MAPPING = [
    BooleanConfigField(
        "auth.pam",
        "USE_PAM_AUTHENTICATION",
        help_str='Set to "true" if you want to activate PAM authentication',
    ),
]
RADIUS_AUTH_MAPPING = [
    CharConfigField(
        "auth.radius_server",
        "RADIUS_SERVER",
        help_str="IP or FQDN of the Radius server. "
        'Python package "django-radius" is required.',
    ),
    IntegerConfigField(
        "auth.radius_port", "RADIUS_PORT", help_str="port of the Radius server."
    ),
    CharConfigField(
        "auth.radius_secret",
        "RADIUS_SECRET",
        help_str="Shared secret if the Radius server",
    ),
]
REDIS_MAPPING = [
    CharConfigField(
        None,
        "COMMON_REDIS_URL",
        help_str="Redis database URL, for all Redis things (e.g. rediss://django:mysecret@redis.example.com:6379/0"
        "?ssl_check_hostname=true"
        "&ssl_cert_reqs=required"
        "&ssl_certfile=/etc/client.crt"
        "&ssl_keyfile=/etc/client.key"
        "&ssl_ca_certs=/etc/ca.crt).",
        env_name="REDIS_URL",
    ),
    IntegerConfigField(
        "cache.db",
        "CACHE_DB",
        help_str="Database number (redis only). \n"
        'Python package "django-redis" is also required to use Redis.',
    ),
    CharConfigField(
        "cache.host", "CACHE_HOST", help_str="cache server host (redis or memcache)"
    ),
    CharConfigField(
        "cache.password",
        "CACHE_PASSWORD",
        help_str="cache server password (if required by redis)",
    ),
    IntegerConfigField(
        "cache.port", "CACHE_PORT", help_str="cache server port (redis or memcache)"
    ),
    ChoiceConfigFile(
        "cache.engine",
        "CACHE_PROTOCOL",
        choices={
            "redis": "redis",
            "memcache": "memcache",
            "locmem": "locmem",
            "file": "file",
        },
        help_str='cache storage engine ("locmem", "redis" or "memcache")',
    ),
    IntegerConfigField(
        "sessions.db",
        "SESSION_REDIS_DB",
        help_str="Database number of the Redis sessions DB\n"
        'Python package "django-redis-sessions" is required.',
    ),
    CharConfigField(
        "sessions.host", "SESSION_REDIS_HOST", help_str="Redis sessions DB host"
    ),
    CharConfigField(
        "sessions.password",
        "SESSION_REDIS_PASSWORD",
        help_str="Redis sessions DB password (if required)",
    ),
    IntegerConfigField(
        "sessions.port", "SESSION_REDIS_PORT", help_str="Redis sessions DB port"
    ),
]
SENDFILE_MAPPING = [
    BooleanConfigField(
        "global.use_apache",
        "USE_X_SEND_FILE",
        help_str='"true" if Apache is used as reverse-proxy with mod_xsendfile.'
        "The X-SENDFILE header must be allowed from file directories",
    ),
    ConfigField(
        "global.use_nginx",
        "X_ACCEL_REDIRECT",
        from_str=x_accel_converter,
        to_str=lambda x: "True" if x else "False",
        help_str='"true" is nginx is used as reverse-proxy with x-accel-redirect.'
        "The media directory (and url) must be allowed in the Nginx configuration.",
    ),
]
AUTH_MAPPING = (
    DJANGO_AUTH_MAPPING
    + RADIUS_AUTH_MAPPING
    + LDAP_AUTH_MAPPING
    + PAM_AUTH_MAPPING
    + HTTP_AUTH_MAPPING
)
# empty settings (please use the `social_authentications` management command instead)
INI_MAPPING = (
    ALLAUTH_MAPPING
    + AUTH_MAPPING
    + BASE_MAPPING
    + DATABASE_MAPPING
    + LOG_MAPPING
    + REDIS_MAPPING
    + SENDFILE_MAPPING
)
DEFAULT_INI_MAPPING = (
    BASE_MAPPING
    + DATABASE_MAPPING
    + LOG_MAPPING
    + REDIS_MAPPING
    + SENDFILE_MAPPING
    + HTTP_AUTH_MAPPING
)
EMPTY_INI_MAPPING = []
