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
from importlib import import_module
from typing import Set
from urllib.parse import quote

import pkg_resources
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, StreamingHttpResponse
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


def read_file_in_chunks(fileobj, chunk_size=32768):
    """ read a file object in chunks of the given size.

    Return an iterator of data

    :param fileobj:
    :param chunk_size: max size of each chunk
    :type chunk_size: `int`
    """
    for data in iter(lambda: fileobj.read(chunk_size), b""):
        yield data


mimetypes.init()


def send_file(filepath, mimetype=None, force_download=False, attachment_filename=None):
    """Send a local file. This is not a Django view, but a function that is called at the end of a view.

    If `settings.USE_X_SEND_FILE` (mod_xsendfile is a mod of Apache), then return an empty HttpResponse with the
    correct header. The file is directly handled by Apache instead of Python.
    If `settings.X_ACCEL_REDIRECT_ARCHIVE` is defined (as a list of tuple (directory, alias_url)) and filepath is
    in one of the directories, return an empty HttpResponse with the correct header.
    This is only available with Nginx.

    Otherwise, return a StreamingHttpResponse to avoid loading the whole file in memory.

    :param filepath: absolute path of the file to send to the client.
    :param mimetype: MIME type of the file (returned in the response header)
    :param force_download: always force the client to download the file.
    :param attachment_filename: filename used in the "Content-Disposition" header (when used)
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
    response = None
    attachment_filename = attachment_filename or os.path.basename(filepath)
    if settings.USE_X_SEND_FILE:
        response = HttpResponse(content_type=mimetype)
        response["X-SENDFILE"] = filepath
    elif settings.X_ACCEL_REDIRECT:
        for dirpath, alias_url in settings.X_ACCEL_REDIRECT:
            dirpath = os.path.abspath(dirpath)
            if filepath.startswith(dirpath):
                response = HttpResponse(content_type=mimetype)
                response["X-Accel-Redirect"] = os.path.join(
                    alias_url, os.path.relpath(filepath, dirpath)
                )
                break
    if response is None:
        # noinspection PyTypeChecker
        fileobj = open(filepath, "rb")
        response = StreamingHttpResponse(
            read_file_in_chunks(fileobj), content_type=mimetype
        )
        response["Content-Length"] = os.path.getsize(filepath)
    encoded_filename = quote(attachment_filename, encoding="utf-8")
    header = "attachment" if force_download else "inline"

    if encoded_filename == attachment_filename:
        response["Content-Disposition"] = '{1}; filename="{0}"'.format(
            encoded_filename, header
        )
    else:
        response["Content-Disposition"] = "{1};filename*=UTF-8''\"{0}\"".format(
            encoded_filename, header
        )
    return response
