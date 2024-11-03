# ##############################################################################
#  This file is part of Interdiode                                             #
#                                                                              #
#  Copyright (C) 2020 Matthieu Gallet <matthieu.gallet@19pouces.net>           #
#  All Rights Reserved                                                         #
#                                                                              #
# ##############################################################################
"""Root URLs provided by df_config.

By default, register URLs for the admin site, `jsi18n`, static and media files, favicon and robots.txt.
If DjangoDebugToolbar is present, then its URL is also registered.

"""

from django.conf import settings
from django.conf.urls import include
from django.urls import path, re_path
from django.utils.module_loading import autodiscover_modules, import_string
from django.views.i18n import JavaScriptCatalog
from django.views.static import serve

from df_config.utils import get_view_from_string


class RootUrls(list):
    """Root URLs provided by df_config.

    By default, register URLs for the admin site, `jsi18n`, static and media files, favicon and robots.txt.
    If DjangoDebugToolbar is present, then its URL is also registered.

    """

    def load_all_defaults(self):
        """Load all default URLs."""
        self.load_file_servers()
        self.load_wellknown_urls()
        self.load_settings_views()
        self.load_auth_urls()
        self.load_admin_site()
        self.load_prometheus()
        self.load_debug_toolbar()
        self.load_websockets()
        self.load_index_view()

    def load_file_servers(self):
        """Register URLs for static and media files."""
        if getattr(settings, "DF_JS_CATALOG_VIEWS", []):
            catalog_view = JavaScriptCatalog.as_view(
                packages=settings.DF_JS_CATALOG_VIEWS
            )
            self.append(
                path("jsi18n/", catalog_view, name="jsi18n"),
            )
        if settings.MEDIA_URL:
            self.append(
                path(
                    "%s<path:path>" % settings.MEDIA_URL[1:],
                    serve,
                    name="serve_media",
                    kwargs={"document_root": settings.MEDIA_ROOT},
                )
            )
        if settings.STATIC_URL:
            self.append(
                path(
                    "%s<path:path>" % settings.STATIC_URL[1:],
                    serve,
                    name="serve_static",
                    kwargs={"document_root": settings.STATIC_ROOT},
                )
            )

    def load_wellknown_urls(self):
        """Provide standard static URLs that should be exposed by every site."""
        self.extend(common_static_urls())

    def load_settings_views(self):
        """Register URLs for views defined in the settings."""
        if getattr(settings, "DF_URL_CONF", None):
            try:
                extra_urls = import_string(settings.DF_URL_CONF)
                self.extend(extra_urls)
            except ModuleNotFoundError:
                pass

    def load_auth_urls(self):
        """Register URLs for authentication."""
        if getattr(settings, "USE_ALL_AUTH", False):
            from allauth.account.views import login

            self.extend(
                [
                    path("admin/login/", login),
                    path("accounts/", include("allauth.urls")),
                ]
            )
        else:
            self.extend([path("auth/", include("django.contrib.auth.urls"))])

    def load_admin_site(self):
        """Register the admin site if it is enabled."""
        if getattr(settings, "DF_ADMIN_SITE", None):
            admin_site = import_string(settings.DF_ADMIN_SITE)
            autodiscover_modules("admin", register_to=admin_site)
            self.append(path("admin/", include(admin_site.urls[:2])))

    def load_prometheus(self):
        """Register the django-prometheus URL if it is enabled."""
        if (
            getattr(settings, "USE_PROMETHEUS", False)
            and getattr(settings, "PROMETHEUS_URL_PREFIX", None) is not None
        ):
            self.append(
                path(settings.PROMETHEUS_URL_PREFIX, include("django_prometheus.urls"))
            )

    def load_debug_toolbar(self):
        """Register the debug toolbar if it is enabled."""
        if getattr(settings, "DEBUG") and getattr(settings, "USE_DEBUG_TOOLBAR"):
            import debug_toolbar

            self.append(path("__debug__/", include(debug_toolbar.urls)))

    @staticmethod
    def load_websockets():
        """Load the websockets thins when df_websockets is used."""
        if getattr(settings, "USE_WEBSOCKETS", False):
            try:
                from df_websockets.load import load_celery

                load_celery()
            except ImportError:
                # noinspection PyUnresolvedReferences
                from df_websockets.tasks import import_signals_and_functions

                import_signals_and_functions()

    def load_index_view(self):
        """Register a view for the index page."""
        if getattr(settings, "DF_INDEX_VIEW", None):
            self.append(
                path("", get_view_from_string(settings.DF_INDEX_VIEW), name="index")
            )

    def prefixed(self):
        """Add a prefix to all URLs."""
        url_prefix = (getattr(settings, "URL_PREFIX", "") or "")[1:]
        if url_prefix:
            return [re_path("^" + url_prefix, include(self))]
        return self


def common_static_urls():
    """Provide standard static URLs that should be exposed by every site."""
    values = (
        "robots.txt",
        "apple-touch-icon.png",
        "apple-touch-icon-precomposed.png",
        "favicon.ico",
    )
    return [
        path(
            filename,
            serve,
            kwargs={
                "document_root": settings.STATIC_ROOT,
                "path": "favicon/%s" % filename,
            },
        )
        for filename in values
    ]


_urlpatterns = RootUrls()
_urlpatterns.load_all_defaults()
urlpatterns = _urlpatterns.prefixed()
