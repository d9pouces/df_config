from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.test import TestCase, override_settings
from django.utils.module_loading import import_string

from df_config.apps import backends
from df_config.apps.middleware import DFConfigMiddleware


class RequestCycleTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mw_classes = [
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.middleware.locale.LocaleMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
            "django.middleware.security.SecurityMiddleware",
        ]

        cls.middlewares = []
        for mw_cls in mw_classes:
            cls.middlewares.append(import_string(mw_cls)(cls.get_response))

    def process(self, request: HttpRequest) -> HttpResponse:
        request.user = AnonymousUser()
        while backends._CACHED_GROUPS:  # clear the cache to avoid DB integrity problems
            backends._CACHED_GROUPS.popitem()
        request.META["SERVER_NAME"] = "localhost"
        request.META["SERVER_PORT"] = "8000"
        User.objects.create_user(username="aladdin", password="opensesame")
        for mw in self.middlewares:
            if hasattr(mw, "process_request"):
                mw.process_request(request)
        mw = DFConfigMiddleware(self.get_response)
        response = mw.process_request(request)
        if response is None:
            response = self.get_response(request)
        mw.process_response(request, response)
        return response

    @staticmethod
    def get_response(request_: HttpRequest):
        return HttpResponse()


class TestMiddleware(RequestCycleTestCase):
    @override_settings(USE_X_FORWARDED_FOR=True, USE_HTTP_BASIC_AUTH=True)
    def test_middleware_forwarded_for(self):
        request = HttpRequest()
        request.META[
            "HTTP_X_FORWARDED_FOR"
        ] = "203.0.113.195,2001:db8:85a3:8d3:1319:8a2e:370:7348,198.51.100.178"
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertEqual("203.0.113.195", request.META["REMOTE_ADDR"])

    @override_settings(USE_X_FORWARDED_FOR=False, USE_HTTP_BASIC_AUTH=True)
    def test_middleware_no_forwarded_for(self):
        request = HttpRequest()
        request.META[
            "HTTP_X_FORWARDED_FOR"
        ] = "203.0.113.195,2001:db8:85a3:8d3:1319:8a2e:370:7348,198.51.100.178"
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertFalse("REMOTE_ADDR" in request.META)

    @override_settings(USE_X_FORWARDED_FOR=False, USE_HTTP_BASIC_AUTH=True)
    def test_middleware_basic_auth(self):
        request = HttpRequest()
        request.META["HTTP_AUTHORIZATION"] = "Basic YWxhZGRpbjpvcGVuc2VzYW1l"
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertTrue(request.user.is_authenticated)
        self.assertEqual("aladdin", request.user.username)

    @override_settings(USE_X_FORWARDED_FOR=False, USE_HTTP_BASIC_AUTH=False)
    def test_middleware_basic_auth_not_setup(self):
        request = HttpRequest()
        request.META["HTTP_AUTHORIZATION"] = "Basic YWxhZGRpbjpvcGVuc2VzYW1l"
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertFalse(request.user.is_authenticated)
        self.assertNotEqual("aladdin", request.user.username)

    @override_settings(USE_X_FORWARDED_FOR=False, USE_HTTP_BASIC_AUTH=True)
    def test_middleware_basic_auth_invalid_password(self):
        request = HttpRequest()
        request.META["HTTP_AUTHORIZATION"] = "Basic YWxhZGRpbjpvcGVuc2VzYW2l"
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertFalse(request.user.is_authenticated)
        self.assertNotEqual("aladdin", request.user.username)

    @override_settings(USE_X_FORWARDED_FOR=False, USE_HTTP_BASIC_AUTH=True)
    def test_middleware_basic_auth_invalid_base64(self):
        request = HttpRequest()
        request.META["HTTP_AUTHORIZATION"] = "Basic eyJmb28iOiJiYXIiLCJiYXoiOiJiYXQifQ"
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertFalse(request.user.is_authenticated)
        self.assertNotEqual("aladdin", request.user.username)

    @override_settings(USE_X_FORWARDED_FOR=False, USE_HTTP_BASIC_AUTH=True)
    def test_middleware_basic_auth_invalid_utf8(self):
        request = HttpRequest()
        request.META["HTTP_AUTHORIZATION"] = "Basic 4oIo"
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertFalse(request.user.is_authenticated)
        self.assertNotEqual("aladdin", request.user.username)

    @override_settings(
        USE_X_FORWARDED_FOR=False,
        DF_FAKE_AUTHENTICATION_USERNAME="aladdin",
        DF_REMOTE_USER_HEADER="HTTP_REMOTE_USER",
        DEBUG=True,
        INTERNAL_IPS=["127.0.0.1"],
    )
    def test_middleware_fake_remote_user_valid(self):
        request = HttpRequest()
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertTrue(request.user.is_authenticated)
        self.assertEqual("aladdin", request.user.username)

    @override_settings(
        USE_X_FORWARDED_FOR=False,
        DF_FAKE_AUTHENTICATION_USERNAME="aladdin",
        DF_REMOTE_USER_HEADER="HTTP_REMOTE_USER",
        DEBUG=True,
        INTERNAL_IPS=["127.0.0.2"],
    )
    def test_middleware_fake_remote_user_invalid(self):
        request = HttpRequest()
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertNotEqual("aladdin", request.user.username)

    @override_settings(
        DF_REMOTE_USER_HEADER="HTTP_REMOTE_USER",
        DEBUG=False,
    )
    def test_middleware_remote_user_valid(self):
        request = HttpRequest()
        request.META["HTTP_REMOTE_USER"] = "aladdin"
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertTrue(request.user.is_authenticated)
        self.assertEqual("aladdin", request.user.username)

    @override_settings(
        DF_REMOTE_USER_HEADER="HTTP_REMOTE_USER",
        DEBUG=False,
        DF_ALLOW_USER_CREATION=True,
    )
    def test_middleware_remote_user_missing_created(self):
        request = HttpRequest()
        username = "40thieves"
        request.META["HTTP_REMOTE_USER"] = username
        self.assertEqual(0, User.objects.filter(username=username).count())
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertTrue(request.user.is_authenticated)
        self.assertEqual(username, request.user.username)
        self.assertEqual(1, User.objects.filter(username=username).count())

    @override_settings(
        DF_REMOTE_USER_HEADER="HTTP_REMOTE_USER",
        DEBUG=False,
        DF_ALLOW_USER_CREATION=True,
        USE_HTTP_BASIC_AUTH=True,
    )
    def test_middleware_remote_user_missing_created_authenticated(self):
        request = HttpRequest()
        username = "40thieves"
        request.META["HTTP_REMOTE_USER"] = username
        request.META["HTTP_AUTHORIZATION"] = "Basic YWxhZGRpbjpvcGVuc2VzYW1l"
        self.assertEqual(0, User.objects.filter(username=username).count())
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertTrue(request.user.is_authenticated)
        self.assertEqual(1, User.objects.filter(username=username).count())
        self.assertEqual(username, request.user.username)

    @override_settings(
        DF_REMOTE_USER_HEADER="HTTP_REMOTE_USER",
        DEBUG=False,
        DF_ALLOW_USER_CREATION=True,
    )
    def test_middleware_remote_user_invalid(self):
        request = HttpRequest()
        username = "40thieves"
        request.META["HTTP_REMOTE_USER"] = ""
        self.assertEqual(0, User.objects.filter(username=username).count())
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertFalse(request.user.is_authenticated)
        self.assertNotEqual(username, request.user.username)
        self.assertEqual(0, User.objects.filter(username=username).count())

    @override_settings(
        DF_REMOTE_USER_HEADER="HTTP_REMOTE_USER",
        DEBUG=False,
        DF_ALLOW_USER_CREATION=False,
    )
    def test_middleware_remote_user_missing_not_created(self):
        request = HttpRequest()
        username = "40thieves"
        request.META["HTTP_REMOTE_USER"] = username
        self.assertEqual(0, User.objects.filter(username=username).count())
        response = self.process(request)
        self.assertFalse(request.user.is_authenticated)
        self.assertEqual(200, response.status_code)
        self.assertNotEqual(username, request.user.username)
        self.assertEqual(0, User.objects.filter(username=username).count())

    @override_settings(
        DF_REMOTE_USER_HEADER="HTTP_REMOTE_USER",
        DEBUG=False,
        DF_ALLOW_USER_CREATION=False,
    )
    def test_middleware_remote_user_not_configured(self):
        request = HttpRequest()
        username = "40thieves"
        request.META["HTTP_REMOTE_USER"] = username
        mw = DFConfigMiddleware(self.get_response)
        self.assertRaises(ImproperlyConfigured, lambda: mw.process_request(request))
