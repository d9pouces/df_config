# ##############################################################################
#  This file is part of df_config                                              #
#                                                                              #
#  Copyright (C) 2020 Matthieu Gallet <github@19pouces.net>                    #
#  All Rights Reserved                                                         #
#                                                                              #
#  You may use, distribute and modify this code under the                      #
#  terms of the (BSD-like) CeCILL-B license.                                   #
#                                                                              #
#  You should have received a copy of the CeCILL-B license with                #
#  this file. If not, please visit:                                            #
#  https://cecill.info/licences/Licence_CeCILL-B_V1-en.txt (English)           #
#  or https://cecill.info/licences/Licence_CeCILL-B_V1-fr.txt (French)         #
#                                                                              #
# ##############################################################################
import os
import tempfile
from unittest import TestCase

import pkg_resources
from django.http import HttpRequest
from django.utils.http import http_date

from df_config.utils import RangedChunkReader, ensure_dir, is_package_present, send_file


class PatchSettings:
    """
    Temporarily change some settings, and restore them when the context is exited.

    """

    def __init__(self, **kwargs):
        self.patched_settings = kwargs
        self.original_settings = {}

    def __enter__(self):
        from django.conf import settings

        for k, v in self.patched_settings.items():
            if hasattr(settings, k):
                self.original_settings[k] = getattr(settings, k)
            setattr(settings, k, v)

    def __exit__(self, exc_type, exc_val, exc_tb):
        from django.conf import settings

        for k in self.patched_settings:
            if k in self.original_settings:
                setattr(settings, k, self.original_settings[k])
            else:
                delattr(settings, k)


class TestIsPackagePresent(TestCase):
    def test_is_package_present(self):
        self.assertTrue(is_package_present("df_config"))
        self.assertFalse(is_package_present("flask2"))


class TestEnsureDir(TestCase):
    def test_ensure_dir(self):
        with tempfile.TemporaryDirectory() as dirname:
            ensure_dir("%s/parent1/dirname" % dirname, parent=False)
            self.assertTrue(os.path.isdir("%s/parent1/dirname" % dirname))
            ensure_dir("%s/parent1/dirname" % dirname)
            self.assertTrue(os.path.isdir("%s/parent1/dirname" % dirname))
            ensure_dir("%s/parent2/filename" % dirname, parent=True)
            self.assertTrue(os.path.isdir("%s/parent2" % dirname))
            self.assertFalse(os.path.isdir("%s/parent2/filename" % dirname))


class TestSendFile(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_df_config.data.settings")

    def test_rangedfilereader(self):
        filename = pkg_resources.resource_filename(
            "test_df_config", "data/range_data.txt"
        )
        with open(filename, "rb") as fd:
            reader = RangedChunkReader(fd, [(0, 9)], chunk_size=5)
            content = list(reader)
        self.assertEqual([b"11111", b"1111\n"], content)
        with open(filename, "rb") as fd:
            reader = RangedChunkReader(fd, [(0, 9), (20, 29)], chunk_size=5)
            content = list(reader)
        self.assertEqual([b"11111", b"1111\n", b"33333", b"3333\n"], content)

    def test_range(self):
        request = HttpRequest()
        filename = pkg_resources.resource_filename(
            "test_df_config", "data/range_data.txt"
        )
        request.META = {"HTTP_RANGE": "bytes=20-29"}
        r = send_file(
            request,
            filename,
            mimetype="text/plain",
            attachment_filename="range_data.txt",
        )
        content = r.getvalue()
        self.assertEqual(b"333333333\n", content)

        expected_headers = [
            ("Content-Type", "text/plain"),
            ("Content-Range", "bytes 20-29/90"),
            ("Content-Length", "10"),
            ('Last-Modified', http_date(os.stat(filename).st_mtime)),
            ("Content-Disposition", 'inline; filename="range_data.txt"'),
        ]
        self.assertEqual(expected_headers, list(r.items()))
        self.assertEqual(206, r.status_code)
        r.close()

    def test_range_multiple(self):
        request = HttpRequest()
        filename = pkg_resources.resource_filename(
            "test_df_config", "data/range_data.txt"
        )
        request.META = {"HTTP_RANGE": "bytes=0-9, 20-29, 40-49"}
        r = send_file(
            request,
            filename,
            mimetype="text/plain",
            attachment_filename="range_data.txt",
        )
        content = r.getvalue()
        self.assertEqual(b"111111111\n333333333\n555555555\n", content)
        expected_headers = [
            ("Content-Type", "text/plain"),
            ("Content-Length", "30"),
            ('Last-Modified', http_date(os.stat(filename).st_mtime)),
            ("Content-Disposition", 'inline; filename="range_data.txt"'),
        ]
        self.assertEqual(expected_headers, list(r.items()))
        self.assertEqual(200, r.status_code)
        r.close()

    def test_no_range(self):
        request = HttpRequest()
        filename = pkg_resources.resource_filename(
            "test_df_config", "data/range_data.txt"
        )
        request.META = {}
        r = send_file(
            request,
            filename,
            mimetype="text/plain",
            attachment_filename="range_data.txt",
        )
        content = r.getvalue()
        self.assertEqual(
            b"111111111\n222222222\n333333333\n444444444\n555555555\n666666666\n777777777\n888888888\n999999999\n",
            content,
        )
        expected_headers = [
            ("Content-Type", "text/plain"),
            ("Content-Length", "90"),
            ('Last-Modified', http_date(os.stat(filename).st_mtime)),
            ("Content-Disposition", 'inline; filename="range_data.txt"'),
        ]
        self.assertEqual(expected_headers, list(r.items()))
        self.assertEqual(200, r.status_code)
        r.close()
