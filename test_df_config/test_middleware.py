from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpRequest, HttpResponse
from django.test import TestCase, override_settings
from django.utils.module_loading import import_string

from df_config.apps.middleware import DFConfigMiddleware
from df_config.guesses.apps import middlewares


class TestMiddleware(TestCase):
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
            "df_config.apps.middleware.DFConfigMiddleware",
        ]

        cls.middlewares = []
        for mw_cls in mw_classes:
            cls.middlewares.append(import_string(mw_cls)(cls.get_response))

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

    def process(self, request: HttpRequest) -> HttpResponse:
        request.user = AnonymousUser()
        request.META["SERVER_NAME"] = "localhost"
        request.META["SERVER_PORT"] = "8000"
        User.objects.create_user(username="aladdin", password="opensesame")
        response = None
        for mw in self.middlewares:
            if hasattr(mw, "process_request"):
                response = mw.process_request(request)
        if response is None:
            response = self.get_response(request)
        self.middlewares[-1].process_response(request, response)
        return response

    @staticmethod
    def get_response(request_: HttpRequest):
        return HttpResponse()
