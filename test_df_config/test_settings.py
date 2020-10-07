from unittest import TestCase

from df_config.manage import MODULE_VARIABLE_NAME, set_env
from test_df_config.test_values_providers import EnvPatch


class TestSetEnv(TestCase):
    """check if all context processors are available"""

    def test_context_processors(self):

        with EnvPatch(**{MODULE_VARIABLE_NAME: "df_config"}):
            set_env()
            import django

            django.setup()
            from django.template.loader import render_to_string
            from django.http import HttpRequest

            request = HttpRequest()
            actual = render_to_string(
                "df_config/test.html", {"value": "test"}, request=request
            )
            expected = "<h1>test</h1>"
            self.assertEqual(expected, actual)
