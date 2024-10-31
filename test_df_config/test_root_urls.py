from unittest import TestCase

from django.test import override_settings
from django.urls.resolvers import URLResolver

from df_config.config.defaults import STATIC_ROOT
from df_config.root_urls import RootUrls


class TestRootUrls(TestCase):
    @override_settings(
        USE_WEBSOCKETS=False,
        USE_DEBUG_TOOLBAR=True,
        USE_PROMETHEUS=True,
        DF_ADMIN_SITE="django.contrib.admin.site",
        DF_URL_CONF="df_config.urls.urlpatterns",
        USE_ALL_AUTH=True,
        DEBUG=True,
        PROMETHEUS_URL_PREFIX="",
        URL_PREFIX="/",
        DF_INDEX_VIEW="df_config.utils.send_file",
        DF_JS_CATALOG_VIEWS=["django.contrib.admin"],
    )
    def test_root_urls_all(self):  #
        urlpatterns = RootUrls()
        urlpatterns.load_all_defaults()
        urlpatterns = urlpatterns.prefixed()
        expected = [
            "jsi18n/",
            "media/<path:path>",
            "static/<path:path>",
            "robots.txt",
            "apple-touch-icon.png",
            "apple-touch-icon-precomposed.png",
            "favicon.ico",
            "admin/login/",
            "accounts/",
            "admin/",
            "",
            "__debug__/",
            "",
        ]
        actual = [url.pattern._route for url in urlpatterns]
        self.assertEqual(actual, expected)

    @override_settings(
        USE_WEBSOCKETS=False,
        USE_DEBUG_TOOLBAR=False,
        USE_PROMETHEUS=True,
        DF_ADMIN_SITE=None,
        DF_URL_CONF=None,
        USE_ALL_AUTH=False,
        DEBUG=True,
        PROMETHEUS_URL_PREFIX="/prometheus",
        URL_PREFIX="/prefix/",
        DF_INDEX_VIEW=None,
        DF_JS_CATALOG_VIEWS=["django.contrib.admin"],
    )
    def test_root_urls_no_defaults(self):
        urlpatterns = RootUrls()
        urlpatterns.load_all_defaults()
        urlpatterns = urlpatterns.prefixed()
        self.assertEqual(1, len(urlpatterns))
        actual = [url.pattern._regex for url in urlpatterns]
        expected = ["^prefix/"]
        self.assertEqual(actual, expected)
        p: URLResolver = urlpatterns[0]
        expected = [
            "jsi18n/",
            "media/<path:path>",
            "static/<path:path>",
            "robots.txt",
            "apple-touch-icon.png",
            "apple-touch-icon-precomposed.png",
            "favicon.ico",
            "auth/",
            "/prometheus",
        ]
        actual = [url.pattern._route for url in p.urlconf_name]
        self.assertEqual(
            expected,
            actual,
        )

    @override_settings(
        USE_WEBSOCKETS=False,
        USE_DEBUG_TOOLBAR=False,
        USE_PROMETHEUS=True,
        DF_ADMIN_SITE=None,
        DF_URL_CONF=None,
        USE_ALL_AUTH=False,
        DEBUG=True,
        PROMETHEUS_URL_PREFIX="/prometheus",
        URL_PREFIX=None,
        DF_INDEX_VIEW=None,
        DF_JS_CATALOG_VIEWS=[],
        STATIC_URL=None,
        MEDIA_URL=None,
    )
    def test_root_urls_no_root_urls(self):
        urlpatterns = RootUrls()
        urlpatterns.load_all_defaults()
        urlpatterns = urlpatterns.prefixed()
        expected = [
            "robots.txt",
            "apple-touch-icon.png",
            "apple-touch-icon-precomposed.png",
            "favicon.ico",
            "auth/",
            "/prometheus",
        ]
        actual = [url.pattern._route for url in urlpatterns]
        self.assertEqual(
            expected,
            actual,
        )
