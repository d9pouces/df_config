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
import argparse
import mimetypes
import os
import re
from email.utils import mktime_tz, parsedate_tz
from importlib import import_module
from typing import Iterable, Set, Tuple
from urllib.parse import quote

import pkg_resources
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseNotModified,
    StreamingHttpResponse,
)
from django.utils.http import http_date
from django.utils.module_loading import import_string


class RemovedInDjangoFloor200Warning(DeprecationWarning):
    """Used for displaying functions or modules that will be removed in a near future."""

    pass


def ensure_dir(path, parent=True):
    """Ensure that the given directory exists

    :param path: the path to check
    :param parent: only ensure the existence of the parent directory

    """
    dirname = os.path.dirname(path) if parent else path
    if not os.path.isdir(dirname):
        os.makedirs(dirname)
    return path


def is_package_present(package_name):
    """Return True is the `package_name` package is present in your current Python environment."""
    try:
        import_module(package_name)
        return True
    except ImportError:
        return False


def remove_arguments_from_help(parser: argparse.ArgumentParser, arguments: Set):
    # noinspection PyProtectedMember
    for action in parser._actions:
        if arguments & set(action.option_strings):
            action.help = argparse.SUPPRESS


def guess_version(defined_settings):
    """Guesss the project version.
    Expect an installed version (findable with pkg_resources) or __version__ in `your_project/__init__.py`.
    If not found

    :param defined_settings: all already defined settings (dict)
    :type defined_settings: :class:`dict`
    :return: should be something like `"1.2.3"`
    :rtype: :class:`str`
    """
    try:
        project_distribution = pkg_resources.get_distribution(
            defined_settings["DF_MODULE_NAME"]
        )
        return project_distribution.version
    except pkg_resources.DistributionNotFound:
        pass
    try:
        return import_string("%s.__version__" % defined_settings["DF_MODULE_NAME"])
    except ImportError:
        return "1.0.0"


def get_view_from_string(view_as_str):
    try:
        view = import_string(view_as_str)
    except ImportError:
        raise ImproperlyConfigured("Unable to import %s" % view_as_str)
    if hasattr(view, "as_view") and callable(view.as_view):
        return view.as_view()
    elif callable(view):
        return view
    raise ImproperlyConfigured(
        '%s is not callabled and does not have an "as_view" attribute'
    )


class ChunkReader:
    """ read a file object in chunks of the given size.

    Return an iterator of data

    :param fileobj:
    :param chunk_size: max size of each chunk
    :type chunk_size: `int`
    """

    def __init__(self, fileobj, chunk_size=32768):
        self.fileobj = fileobj
        self.chunk_size = chunk_size

    def __iter__(self):
        for data in iter(lambda: self.fileobj.read(self.chunk_size), b""):
            yield data

    def close(self):
        self.fileobj.close()


class RangedChunkReader(ChunkReader):
    def __init__(self, fd, ranges: Iterable[Tuple[int, int]], chunk_size=32768):
        super().__init__(fd, chunk_size=chunk_size)
        self.ranges = ranges

    def __iter__(self):
        for start, end in self.ranges:
            self.fileobj.seek(start)
            while start <= end:
                size = min(self.chunk_size, end - start + 1)
                if size <= 0:
                    break
                yield self.fileobj.read(size)
                start += size


mimetypes.init()


_range_re = re.compile(r"^bytes=(\d*-\d*(?:,\s*\d*-\d*)*)$")
_if_modified_since_re = re.compile(
    r"^([^;]+)(; length=([0-9]+))?$", flags=re.IGNORECASE
)


def was_modified_since(header=None, mtime=0.0, size=None):
    """
    Was something modified since the user last downloaded it?
    header
      This is the value of the If-Modified-Since header.  If this is None,
      I'll just return True.
    mtime
      This is the modification time of the item we're talking about.
    size
      This is the size of the item we're talking about.
    """
    if header is None:
        return True
    matcher = _if_modified_since_re.match(header)
    if not matcher:
        return True
    try:
        header_date = parsedate_tz(matcher.group(1))
        if header_date is None:
            return True
        header_mtime = mktime_tz(header_date)
        header_len = matcher.group(3)
        if size is not None and header_len and int(header_len) != size:
            return True
        if mtime > header_mtime:
            return True
    except (AttributeError, ValueError, OverflowError):
        return True
    return False


def send_file(
    request: HttpRequest,
    filepath: str,
    mimetype=None,
    force_download=False,
    attachment_filename=None,
    chunk_size=32768,
    etag=None,
):
    """Send a local file. This is not a Django view, but a function that is called at the end of a view.

    If `settings.USE_X_SEND_FILE` (mod_xsendfile is a mod of Apache), then return an empty HttpResponse with the
    correct header. The file is directly handled by Apache instead of Python.
    If `settings.X_ACCEL_REDIRECT_ARCHIVE` is defined (as a list of tuple (directory, alias_url)) and filepath is
    in one of the directories, return an empty HttpResponse with the correct header.
    This is only available with Nginx.

    Otherwise, return a StreamingHttpResponse to avoid loading the whole file in memory.

    :param request: the original request (used to detect the "range" header)
    :param filepath: absolute path of the file to send to the client.
    :param mimetype: MIME type of the file (returned in the response header)
    :param force_download: always force the client to download the file.
    :param attachment_filename: filename used in the "Content-Disposition" header (when used)
    :param chunk_size: size of chunks for large files. Useful at least for unittests
    :rtype: :class:`django.http.response.StreamingHttpResponse` or :class:`django.http.response.HttpResponse`
    """
    if mimetype is None:
        (mimetype, encoding) = mimetypes.guess_type(filepath)
        if mimetype is None:
            mimetype = "text/plain"
    if isinstance(mimetype, bytes):
        # noinspection PyTypeChecker
        mimetype = mimetype.decode("utf-8")

    filepath = os.path.abspath(filepath)

    attachment_filename = attachment_filename or os.path.basename(filepath)
    if request.method == "HEAD":
        r = HttpResponse(content=b"", content_type=mimetype, status=200)
        if etag:
            r["ETag"] = str(etag)
        return r

    range_matcher = _range_re.match(request.META.get("HTTP_RANGE", ""))
    ranges = []
    if not os.path.isfile(filepath):
        return HttpResponse(status=404)
    stats = os.stat(filepath)
    filesize = stats.st_size
    if not was_modified_since(
        request.META.get("HTTP_IF_MODIFIED_SINCE"), mtime=stats.st_mtime, size=filesize
    ):
        return HttpResponseNotModified()
    if range_matcher:
        content_size = 0
        ranges_str = [x.strip() for x in range_matcher.group(1).split(",")]
        for range_str in ranges_str:
            start_str, sep, end_str = range_str.partition("-")
            end = int(end_str) if end_str else filesize - 1
            start = int(start_str) if start_str else filesize - end
            content_size += end - start + 1
            if end + 1 > filesize:
                response = HttpResponse(content_type=mimetype, status=416)
                response["Content-Range"] = "bytes */%s" % filesize

                return response
            ranges.append((start, end))
    else:
        content_size = filesize

    response = None
    if settings.USE_X_SEND_FILE and not ranges:
        response = HttpResponse(content_type=mimetype)
        response["X-SENDFILE"] = filepath
    elif settings.X_ACCEL_REDIRECT and not ranges:
        for dirpath, alias_url in settings.X_ACCEL_REDIRECT:
            dirpath = os.path.abspath(dirpath)
            if filepath.startswith(dirpath):
                response = HttpResponse(content_type=mimetype)
                response["X-Accel-Redirect"] = os.path.join(
                    alias_url, os.path.relpath(filepath, dirpath)
                )
                break
    if response is None:
        fileobj = open(filepath, "rb")
        status = 200
        if ranges:
            file_content = RangedChunkReader(fileobj, ranges, chunk_size=chunk_size)
            if len(ranges) == 1:
                status = 206
        else:
            file_content = ChunkReader(fileobj, chunk_size=chunk_size)
        response = StreamingHttpResponse(
            file_content, content_type=mimetype, status=status
        )
        if len(ranges) == 1:
            response["Content-Range"] = "bytes %d-%d/%d" % (
                ranges[0][0],
                ranges[0][1],
                filesize,
            )
        response["Content-Length"] = content_size
    response["Last-Modified"] = http_date(stats.st_mtime)
    encoded_filename = quote(attachment_filename, encoding="utf-8")
    header = "attachment" if force_download else "inline"
    if etag:
        response["ETag"] = str(etag)
    if encoded_filename == attachment_filename:
        response["Content-Disposition"] = '{1}; filename="{0}"'.format(
            encoded_filename, header
        )
    else:
        response["Content-Disposition"] = "{1};filename*=UTF-8''\"{0}\"".format(
            encoded_filename, header
        )
    return response
