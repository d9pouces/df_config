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


catalog_view = JavaScriptCatalog.as_view(packages=settings.DF_JS_CATALOG_VIEWS)
urlpatterns = [
    path("jsi18n/", catalog_view, name="jsi18n"),
    path(
        "%s<path:path>" % settings.MEDIA_URL[1:],
        serve,
        name="serve_media",
        kwargs={"document_root": settings.MEDIA_ROOT},
    ),
    path(
        "%s<path:path>" % settings.STATIC_URL[1:],
        serve,
        name="serve_static",
        kwargs={"document_root": settings.STATIC_ROOT},
    ),
]

urlpatterns += common_static_urls()

if settings.DF_URL_CONF:
    try:
        extra_urls = import_string(settings.DF_URL_CONF)
        urlpatterns += list(extra_urls)
    except ModuleNotFoundError:
        pass

if settings.USE_ALL_AUTH:
    # noinspection PyUnresolvedReferences
    from allauth.account.views import login

    urlpatterns += [
        path("admin/login/", login),
        path("accounts/", include("allauth.urls")),
    ]
else:
    urlpatterns += [path("auth/", include("django.contrib.auth.urls"))]
if settings.DF_ADMIN_SITE:
    admin_site = import_string(settings.DF_ADMIN_SITE)
    autodiscover_modules("admin", register_to=admin_site)
    urlpatterns += [path("admin/", include(admin_site.urls[:2]))]
if settings.USE_PROMETHEUS and settings.PROMETHEUS_URL_PREFIX is not None:
    # noinspection PyUnresolvedReferences
    urlpatterns += [
        path(settings.PROMETHEUS_URL_PREFIX, include("django_prometheus.urls")),
    ]
if settings.DEBUG and settings.USE_DEBUG_TOOLBAR:
    # noinspection PyPackageRequirements,PyUnresolvedReferences
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
if settings.DF_INDEX_VIEW:
    urlpatterns += [
        path("", get_view_from_string(settings.DF_INDEX_VIEW), name="index")
    ]
if settings.USE_WEBSOCKETS:
    try:
        from df_websockets.load import load_celery

        load_celery()
    except ImportError:
        # noinspection PyUnresolvedReferences
        from df_websockets.tasks import import_signals_and_functions

        import_signals_and_functions()
        load_celery = None

url_prefix = settings.URL_PREFIX[1:]

if url_prefix:
    urlpatterns = [re_path("^" + url_prefix, include(urlpatterns))]
