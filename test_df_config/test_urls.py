from unittest import TestCase

from df_config.urls import urlpatterns


class TestUrls(TestCase):
    def test_urls(self):
        self.assertEqual([], urlpatterns)
