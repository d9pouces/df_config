"""Unit tests for df_config/context_processors.py."""

from unittest import TestCase

from django.http import HttpRequest
from django.test import override_settings

from df_config.context_processors import config


class TestConfigContextProcessor(TestCase):
    @override_settings(
        ADMIN_EMAIL="admin@example.com",
        DF_PROJECT_NAME="MyProject",
        DF_PROJECT_VERSION="1.2.3",
        SERVER_BASE_URL="https://example.com/",
        SERVER_NAME="example.com",
    )
    def test_config_returns_all_keys(self):
        request = HttpRequest()
        result = config(request)
        self.assertIn("ADMIN_EMAIL", result)
        self.assertIn("DF_PROJECT_NAME", result)
        self.assertIn("DF_PROJECT_VERSION", result)
        self.assertIn("SERVER_URL", result)
        self.assertIn("SERVER_NAME", result)

    @override_settings(
        ADMIN_EMAIL="admin@example.com",
        DF_PROJECT_NAME="MyProject",
        DF_PROJECT_VERSION="1.2.3",
        SERVER_BASE_URL="https://example.com/",
        SERVER_NAME="example.com",
    )
    def test_config_values_are_correct(self):
        request = HttpRequest()
        result = config(request)
        self.assertEqual("admin@example.com", result["ADMIN_EMAIL"])
        self.assertEqual("MyProject", result["DF_PROJECT_NAME"])
        self.assertEqual("1.2.3", result["DF_PROJECT_VERSION"])
        self.assertEqual("https://example.com/", result["SERVER_URL"])
        self.assertEqual("example.com", result["SERVER_NAME"])

    @override_settings(
        ADMIN_EMAIL="other@domain.org",
        DF_PROJECT_NAME="AnotherApp",
        DF_PROJECT_VERSION="0.1.0",
        SERVER_BASE_URL="http://localhost:8000/",
        SERVER_NAME="localhost",
    )
    def test_config_reflects_settings(self):
        request = HttpRequest()
        result = config(request)
        self.assertEqual("other@domain.org", result["ADMIN_EMAIL"])
        self.assertEqual("AnotherApp", result["DF_PROJECT_NAME"])
        self.assertEqual("0.1.0", result["DF_PROJECT_VERSION"])
        self.assertEqual("http://localhost:8000/", result["SERVER_URL"])
        self.assertEqual("localhost", result["SERVER_NAME"])

    @override_settings(
        ADMIN_EMAIL="admin@example.com",
        DF_PROJECT_NAME="MyProject",
        DF_PROJECT_VERSION="1.0",
        SERVER_BASE_URL="https://example.com/",
        SERVER_NAME="example.com",
    )
    def test_config_returns_dict(self):
        request = HttpRequest()
        result = config(request)
        self.assertIsInstance(result, dict)
        self.assertEqual(5, len(result))
