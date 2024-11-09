from ipaddress import IPv4Address
from unittest import TestCase

from django.core.exceptions import ImproperlyConfigured
from hypothesis import given
from hypothesis import strategies as st

from df_config.iniconf import normalize_listen_address


class TestCheckListenAddress(TestCase):
    @given(st.ip_addresses())
    def test_check_listen_address(self, ip_addr: IPv4Address):
        base = f"{ip_addr.exploded}:5000"
        actual = normalize_listen_address(base)
        expected = f"{ip_addr.compressed}:5000"
        return self.assertEqual(actual, expected)

    def test_check_listen_address_invalid_address(self):
        self.assertRaises(
            ImproperlyConfigured, lambda: normalize_listen_address("0.0.0:8000")
        )

    def test_check_listen_address_invalid_port(self):
        self.assertRaises(
            ImproperlyConfigured, lambda: normalize_listen_address("0.0.0.0:653123")
        )

    def test_check_listen_address_only_port(self):
        self.assertEqual("0.0.0.0:8000", normalize_listen_address(":8000"))

    def test_check_listen_address_invalid(self):
        self.assertRaises(ImproperlyConfigured, lambda: normalize_listen_address("-"))

    def test_check_listen_address_only_port_2(self):
        self.assertEqual("0.0.0.0:8000", normalize_listen_address("8000"))
