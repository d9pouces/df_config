# ##############################################################################
#  This file is part of df_config                                              #
#                                                                              #
#  Copyright (C) 2020 Matthieu Gallet <df_config@19pouces.net>                    #
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
import datetime
import io
import os
import tempfile
from argparse import ArgumentParser
from importlib import resources
from unittest import TestCase

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.test import TestCase as DjangoTestCase
from django.test import override_settings
from django.utils.http import http_date
from django.views.generic import TemplateView

from df_config.utils import (
    RangedChunkReader,
    ensure_dir,
    get_view_from_string,
    is_package_present,
    remove_arguments_from_help,
    send_file,
    was_modified_since,
)

FILE_CONTENT = (
    b"111111111\n222222222\n333333333\n444444444\n555555555\n"
    b"666666666\n777777777\n888888888\n999999999\n"
)


class PatchedSettings:
    """Temporarily change some settings, and restore them when the context is exited."""

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


class TestRemoveArgumentsFromHelp(TestCase):
    def test_remove_arguments_from_help(self):
        parser = ArgumentParser()
        parser.add_argument("--settings", default=None)
        parser.add_argument("--traceback", default=None)
        parser.add_argument("--pythonpath", default=None)
        parser.add_argument("--filename", default=None)
        s = io.StringIO()
        parser.print_help(s)
        actual_value = s.getvalue()
        self.assertTrue("--settings" in actual_value)
        self.assertTrue("--traceback" in actual_value)
        self.assertTrue("--pythonpath" in actual_value)
        self.assertTrue("--filename" in actual_value)
        remove_arguments_from_help(
            parser, {"--settings", "--traceback", "--pythonpath"}
        )
        s = io.StringIO()
        parser.print_help(s)
        actual_value = s.getvalue()
        self.assertFalse("--settings" in actual_value)
        self.assertFalse("--traceback" in actual_value)
        self.assertFalse("--pythonpath" in actual_value)
        self.assertTrue("--filename" in actual_value)


class ExampleView(TemplateView):
    """A simple view for testing."""

    pass


def example_view(request):
    """A simple view for testing."""
    return HttpResponse()


class TestGetViewFromString(TestCase):
    def test_get_view_from_string(self):
        view = get_view_from_string("test_df_config.test_utils.ExampleView")
        self.assertEqual(view.view_class, ExampleView)
        view = get_view_from_string("test_df_config.test_utils.example_view")
        self.assertEqual(example_view, view)
        self.assertRaises(
            ImproperlyConfigured,
            lambda: get_view_from_string(
                "test_df_config.test_utils.TestGetViewFromString"
            ),
        )
        self.assertRaises(
            ImproperlyConfigured,
            lambda: get_view_from_string("test_df_config.test_utils.TestView2"),
        )


class TestSendFile(DjangoTestCase):
    def test_rangedfilereader(self):
        ref = resources.files("test_df_config.data").joinpath("range_data.txt")
        with resources.as_file(ref) as filename:
            filename = str(filename)
            with open(filename, "rb") as fd:
                reader = RangedChunkReader(fd, [(0, 9)], chunk_size=5)
                content = list(reader)
            self.assertEqual([b"11111", b"1111\n"], content)
            with open(filename, "rb") as fd:
                reader = RangedChunkReader(fd, [(0, 9), (20, 29)], chunk_size=5)
                content = list(reader)
            self.assertEqual([b"11111", b"1111\n", b"33333", b"3333\n"], content)

    @override_settings(USE_X_SEND_FILE=False, X_ACCEL_REDIRECT=[])
    def test_range(self):
        request = HttpRequest()
        ref = resources.files("test_df_config.data").joinpath("range_data.txt")
        with resources.as_file(ref) as filename:
            filename = str(filename)
            request.META = {"HTTP_RANGE": "bytes=20-29"}
            r = send_file(
                request,
                filename,
                mimetype="text/plain",
                attachment_filename="range_data.txt",
                etag="123456",
            )
            content = r.getvalue()
            self.assertEqual(b"333333333\n", content)

            expected_headers = {
                "Content-Type": "text/plain",
                "Content-Range": "bytes 20-29/90",
                "Content-Length": "10",
                "Last-Modified": http_date(os.stat(filename).st_mtime),
                "Content-Disposition": 'inline; filename="range_data.txt"',
                "ETag": "123456",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(206, r.status_code)
            r.close()
            request.META["HTTP_IF_MODIFIED_SINCE"] = "Wed, 21 Oct 2095 07:28:00 GMT"
            r = send_file(
                request,
                filename,
                mimetype="text/plain",
                attachment_filename="range_data.txt",
                etag="123456",
            )
            content = r.getvalue()
            self.assertEqual(b"", content)

            expected_headers = {
                "ETag": "123456",
                "Last-Modified": "Sun, 19 Jul 2020 13:16:34 GMT",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(304, r.status_code)
            r.close()

    @override_settings(USE_X_SEND_FILE=False, X_ACCEL_REDIRECT=[])
    def test_range_too_large(self):
        request = HttpRequest()
        ref = resources.files("test_df_config.data").joinpath("range_data.txt")
        with resources.as_file(ref) as filename:
            filename = str(filename)
            request.META = {"HTTP_RANGE": "bytes=180-289"}
            r = send_file(
                request,
                filename,
                mimetype="text/plain",
                attachment_filename="range_data.txt",
                etag="123456",
            )
            content = r.getvalue()
            self.assertEqual(b"", content)

            expected_headers = {
                "Content-Type": "text/plain",
                "Content-Range": "bytes */90",
                "Last-Modified": http_date(os.stat(filename).st_mtime),
                "ETag": "123456",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(416, r.status_code)
            r.close()
            request.META["HTTP_IF_MODIFIED_SINCE"] = "Wed, 21 Oct 2095 07:28:00 GMT"
            r = send_file(
                request,
                filename,
                mimetype="text/plain",
                attachment_filename="range_data.txt",
                etag="123456",
            )
            content = r.getvalue()
            self.assertEqual(b"", content)

            expected_headers = {
                "ETag": "123456",
                "Last-Modified": "Sun, 19 Jul 2020 13:16:34 GMT",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(304, r.status_code)
            r.close()

    @override_settings(USE_X_SEND_FILE=False, X_ACCEL_REDIRECT=[])
    def test_range_multiple(self):
        request = HttpRequest()
        ref = resources.files("test_df_config.data").joinpath("range_data.txt")
        with resources.as_file(ref) as filename:
            filename = str(filename)
            request.META = {"HTTP_RANGE": "bytes=0-9, 20-29, 40-49"}
            r = send_file(
                request,
                filename,
                mimetype="text/plain",
                attachment_filename="range_data.txt",
                etag="123456",
            )
            content = r.getvalue()
            self.assertEqual(b"111111111\n333333333\n555555555\n", content)
            expected_headers = {
                "Content-Type": "text/plain",
                "Content-Length": "30",
                "Last-Modified": http_date(os.stat(filename).st_mtime),
                "Content-Disposition": 'inline; filename="range_data.txt"',
                "ETag": "123456",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(200, r.status_code)
            r.close()
            request.META["HTTP_IF_MODIFIED_SINCE"] = "Wed, 21 Oct 2095 07:28:00 GMT"
            r = send_file(
                request,
                filename,
                mimetype="text/plain",
                attachment_filename="range_data.txt",
                etag="123456",
            )
            content = r.getvalue()
            self.assertEqual(b"", content)
            expected_headers = {
                "Last-Modified": http_date(os.stat(filename).st_mtime),
                "ETag": "123456",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(304, r.status_code)
            r.close()

    @override_settings(USE_X_SEND_FILE=False, X_ACCEL_REDIRECT=[])
    def test_range_multiple_head(self):
        request = HttpRequest()
        request.method = "HEAD"
        ref = resources.files("test_df_config.data").joinpath("range_data.txt")
        with resources.as_file(ref) as filename:
            filename = str(filename)
            request.META = {"HTTP_RANGE": "bytes=0-9, 20-29, 40-49"}
            r = send_file(
                request,
                filename,
                mimetype="text/plain",
                attachment_filename="range_data.txt",
                etag="123456",
                expires=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc),
            )
            content = r.getvalue()
            self.assertEqual(b"", content)
            expected_headers = {
                "Content-Length": "30",
                "Content-Type": "text/plain",
                "Expires": "Wed, 01 Jan 2020 00:00:00 GMT",
                "Last-Modified": http_date(os.stat(filename).st_mtime),
                "ETag": "123456",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(200, r.status_code)
            r.close()
            request.META["HTTP_IF_MODIFIED_SINCE"] = "Wed, 21 Oct 2095 07:28:00 GMT"
            r = send_file(
                request,
                filename,
                mimetype="text/plain",
                attachment_filename="range_data.txt",
                etag="123456",
                expires=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc),
            )
            content = r.getvalue()
            self.assertEqual(b"", content)
            expected_headers = {
                "Expires": "Wed, 01 Jan 2020 00:00:00 GMT",
                "Last-Modified": http_date(os.stat(filename).st_mtime),
                "ETag": "123456",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(304, r.status_code)
            r.close()

    @override_settings(USE_X_SEND_FILE=False, X_ACCEL_REDIRECT=[])
    def test_no_range(self):
        request = HttpRequest()
        ref = resources.files("test_df_config.data").joinpath("range_data.txt")
        with resources.as_file(ref) as filename:
            filename = str(filename)
            request.META = {}
            r = send_file(
                request,
                filename,
                mimetype="text/plain",
                attachment_filename="range_data.txt",
                etag="123456",
            )
            self.assertEqual(FILE_CONTENT, r.getvalue())
            expected_headers = {
                "Content-Type": "text/plain",
                "Content-Length": "90",
                "Last-Modified": http_date(os.stat(filename).st_mtime),
                "Content-Disposition": 'inline; filename="range_data.txt"',
                "ETag": "123456",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(200, r.status_code)
            r.close()

    @override_settings(USE_X_SEND_FILE=False, X_ACCEL_REDIRECT=[])
    def test_missing_file(self):
        request = HttpRequest()
        ref = resources.files("test_df_config.data").joinpath("range_data.txt")
        with resources.as_file(ref) as filename:
            filename = str(filename)
            request.META = {}
            r = send_file(
                request,
                filename + "2",
                mimetype="text/plain",
                attachment_filename="range_data.txt",
                etag="123456",
            )
            self.assertEqual(b"File not found.", r.getvalue())
            expected_headers = {"Content-Type": "text/plain; charset=utf-8"}
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(404, r.status_code)
            r.close()

    @override_settings(USE_X_SEND_FILE=False, X_ACCEL_REDIRECT=[])
    def test_no_range(self):
        request = HttpRequest()
        ref = resources.files("test_df_config.data").joinpath("range_data.txt")
        with resources.as_file(ref) as filename:
            filename = str(filename)
            request.META = {}
            r = send_file(
                request,
                filename,
                mimetype="text/plain",
                attachment_filename="range_data.txt",
                etag="123456",
            )
            self.assertEqual(FILE_CONTENT, r.getvalue())
            expected_headers = {
                "Content-Type": "text/plain",
                "Content-Length": "90",
                "Last-Modified": http_date(os.stat(filename).st_mtime),
                "Content-Disposition": 'inline; filename="range_data.txt"',
                "ETag": "123456",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(200, r.status_code)
            r.close()
            request.META["HTTP_IF_MODIFIED_SINCE"] = "Wed, 21 Oct 2095 07:28:00 GMT"
            r = send_file(
                request,
                filename,
                mimetype="text/plain",
                attachment_filename="range_data.txt",
                etag="123456",
            )
            self.assertEqual(b"", r.getvalue())
            expected_headers = {
                "Last-Modified": http_date(os.stat(filename).st_mtime),
                "ETag": "123456",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(304, r.status_code)
            r.close()

    @override_settings(USE_X_SEND_FILE=False, X_ACCEL_REDIRECT=[])
    def test_attachment_name(self):
        request = HttpRequest()
        ref = resources.files("test_df_config.data").joinpath("range_data.txt")
        with resources.as_file(ref) as filename:
            filename = str(filename)
            request.META = {}
            r = send_file(
                request,
                filename,
                mimetype="text/plain",
                attachment_filename="foo-ä-€.html",
                etag="123456",
            )
            self.assertEqual(FILE_CONTENT, r.getvalue())
            expected_headers = {
                "Content-Type": "text/plain",
                "Content-Length": "90",
                "Last-Modified": http_date(os.stat(filename).st_mtime),
                "Content-Disposition": "inline; filename*=\"UTF-8''foo-%C3%A4-%E2%82%AC.html\"",
                "ETag": "123456",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(200, r.status_code)
            r.close()
            request.META["HTTP_IF_MODIFIED_SINCE"] = "Wed, 21 Oct 2095 07:28:00 GMT"
            r = send_file(
                request,
                filename,
                mimetype="text/plain",
                attachment_filename="range_data.txt",
                etag="123456",
            )
            self.assertEqual(b"", r.getvalue())
            expected_headers = {
                "Last-Modified": http_date(os.stat(filename).st_mtime),
                "ETag": "123456",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(304, r.status_code)
            r.close()

    def test_apache_and_nginx(self, use_x_send_file=True):
        request = HttpRequest()
        ref = resources.files("test_df_config.data").joinpath("range_data.txt")
        with resources.as_file(ref) as filename:
            x_accel_redirect = (
                [] if use_x_send_file else [(str(filename.parent), "/redirect/")]
            )
            header_name = "X-SENDFILE" if use_x_send_file else "X-Accel-Redirect"
            header_value = (
                str(filename) if use_x_send_file else f"/redirect/{filename.name}"
            )
            filename = str(filename)
            request.META = {}
            with override_settings(
                USE_X_SEND_FILE=use_x_send_file, X_ACCEL_REDIRECT=x_accel_redirect
            ):
                r = send_file(
                    request,
                    filename,
                    mimetype="text/plain",
                    attachment_filename="range_data.txt",
                    etag="123456",
                )
            self.assertEqual(b"", r.getvalue())
            expected_headers = {
                "Content-Type": "text/plain",
                "Content-Length": "90",
                "Last-Modified": http_date(os.stat(filename).st_mtime),
                "Content-Disposition": 'inline; filename="range_data.txt"',
                "ETag": "123456",
                header_name: header_value,
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(200, r.status_code)
            r.close()
            request.META["HTTP_IF_MODIFIED_SINCE"] = "Wed, 21 Oct 2095 07:28:00 GMT"
            with override_settings(
                USE_X_SEND_FILE=use_x_send_file, X_ACCEL_REDIRECT=x_accel_redirect
            ):
                r = send_file(
                    request,
                    filename,
                    mimetype="text/plain",
                    attachment_filename="range_data.txt",
                    etag="123456",
                )
            self.assertEqual(b"", r.getvalue())
            expected_headers = {
                "Last-Modified": http_date(os.stat(filename).st_mtime),
                "ETag": "123456",
            }
            self.assertEqual(expected_headers, {x: y for (x, y) in r.items()})
            self.assertEqual(304, r.status_code)
            r.close()

    def test_nginx(self):
        self.test_apache_and_nginx(use_x_send_file=False)


class TestWasModifiedSince(TestCase):
    def test_was_modified_since(self):
        dt = datetime.datetime(2015, 10, 21, 9, 28, tzinfo=datetime.timezone.utc)
        mtime = dt.timestamp()
        actual = was_modified_since(header="Wed, 21 Oct 2015 07:28:00 GMT", mtime=mtime)
        self.assertTrue(actual)
        actual = was_modified_since(
            header="Wed, 21 Oct 2015 11:28:00 GMT", mtime=mtime, size=1000
        )
        self.assertFalse(actual)
        actual = was_modified_since(
            header="Wed, 21 Oct 2015 11:28:00 GMT;length=1000", mtime=mtime, size=1000
        )
        self.assertFalse(actual)
        actual = was_modified_since(
            header="Wed, 21 Oct 2015 11:28:00 GMT;length=1002", mtime=mtime, size=1000
        )
        self.assertTrue(actual)
        actual = was_modified_since(
            header="Wed, 21/10/2015 11:28:00 GMT", mtime=mtime, size=1000
        )
        self.assertTrue(actual)
        actual = was_modified_since(header=";;;", mtime=mtime, size=1000)
        self.assertTrue(actual)
