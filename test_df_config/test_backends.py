from django.http import HttpRequest
from django.test import override_settings

from test_df_config.test_middleware import RequestCycleTestCase


class TestMiddleware(RequestCycleTestCase):
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
        self.assertEqual(
            set(), set(request.user.groups.all().values_list("name", flat=True))
        )

    @override_settings(
        DF_REMOTE_USER_HEADER="HTTP_REMOTE_USER",
        DEBUG=False,
    )
    def test_middleware_remote_user_valid(self):
        request = HttpRequest()
        request.META["HTTP_REMOTE_USER"] = "40thieves"
        response = self.process(request)
        self.assertEqual(200, response.status_code)
        self.assertTrue(request.user.is_authenticated)
        self.assertEqual("40thieves", request.user.username)
        self.assertEqual(
            {"Group1", "Group2"},
            set(request.user.groups.all().values_list("name", flat=True)),
        )
