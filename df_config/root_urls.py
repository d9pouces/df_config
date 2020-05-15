# ##############################################################################
#  This file is part of Interdiode                                             #
#                                                                              #
#  Copyright (C) 2020 Matthieu Gallet <matthieu.gallet@19pouces.net>           #
#  All Rights Reserved                                                         #
#                                                                              #
# ##############################################################################
"""Root URLs provided by DjangoFloor
=================================

By default, register URLs for the admin site, `jsi18n`, static and media files, favicon and robots.txt.
If DjangoDebugToolbar is present, then its URL is also registered.

"""

from df_config.utils import get_view_from_string
from django.conf import settings
from django.conf.urls import include, url
from django.urls import path
from django.utils.module_loading import autodiscover_modules, import_string
from django.views.i18n import JavaScriptCatalog
from django.views.static import serve


def common_static_urls():
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
    extra_urls = import_string(settings.DF_URL_CONF)
    urlpatterns += list(extra_urls)

if settings.USE_ALL_AUTH:
    # noinspection PyUnresolvedReferences
    urlpatterns += [
        path("admin/login/", "allauth.account.views.login"),
        path("accounts/", include("allauth.urls")),
    ]
else:
    urlpatterns += [path("auth/", include("django.contrib.auth.urls"))]
if settings.USE_SITE:
    urlpatterns += [
        path("chaining/", include("smart_selects.urls")),
        path("df_site/", include("df_site.urls")),
    ]
if settings.DF_ADMIN_SITE:
    admin_site = import_string(settings.DF_ADMIN_SITE)
    autodiscover_modules("admin", register_to=admin_site)
    urlpatterns += [path("admin/", include(admin_site.urls[:2]))]
if settings.DEBUG and settings.USE_DEBUG_TOOLBAR:
    # noinspection PyPackageRequirements,PyUnresolvedReferences
    import debug_toolbar
    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
if settings.DF_INDEX_VIEW:
    urlpatterns += [
        path("", get_view_from_string(settings.DF_INDEX_VIEW), name="index")
    ]
if settings.USE_WEBSOCKETS:
    from df_websockets.load import load_celery

    load_celery()

url_prefix = settings.URL_PREFIX[1:]

if url_prefix:
    urlpatterns = [url("^" + url_prefix, include(urlpatterns))]
