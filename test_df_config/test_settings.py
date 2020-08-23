from unittest import TestCase

from df_config.manage import MODULE_VARIABLE_NAME, set_env
from test_df_config.test_values_providers import EnvPatch


class TestSetEnv(TestCase):

    def test_manage(self):

        with EnvPatch(**{MODULE_VARIABLE_NAME: "df_config"}):
            set_env()
            import django
            from django.template.loader import render_to_string
            from django.http import HttpRequest
            django.setup()
            request = HttpRequest()
            actual = render_to_string("df_config/_test.html", {"value": "test"}, request=request)
            expected = "<h1>test</h1>"
            self.assertEqual(expected, actual)
