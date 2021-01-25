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
import base64
import binascii
import logging

from django.conf import settings
from django.contrib import auth
from django.contrib.auth.middleware import (
    RemoteUserMiddleware as BaseRemoteUserMiddleware,
)
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.utils.functional import cached_property

logger = logging.getLogger("django.request")


class DFConfigMiddleware(BaseRemoteUserMiddleware):
    """Like :class:`django.contrib.auth.middleware.RemoteUserMiddleware` but:

    * can use any header defined by the setting `DF_REMOTE_USER_HEADER`,
    * handle the HTTP_X_FORWARDED_FOR HTTP header (set the right client IP)
    * handle HTTP basic authentication
    * set response header for Internet Explorer (to use its most recent render engine)
    """

    @cached_property
    def header(self):
        header = settings.DF_REMOTE_USER_HEADER
        if header:
            header = header.upper().replace("-", "_")
        return header

    def process_request(self, request: HttpRequest):
        request.remote_username = None

        if settings.USE_X_FORWARDED_FOR and "HTTP_X_FORWARDED_FOR" in request.META:
            request.META["REMOTE_ADDR"] = (
                request.META["HTTP_X_FORWARDED_FOR"].split(",")[0].strip()
            )

        if settings.USE_HTTP_BASIC_AUTH and "HTTP_AUTHORIZATION" in request.META:
            authentication = request.META["HTTP_AUTHORIZATION"]
            authmeth, sep, auth_data = authentication.partition(" ")
            if sep == " " and authmeth.lower() == "basic":
                try:
                    auth_data = base64.b64decode(auth_data.strip()).decode("utf-8")
                except binascii.Error:
                    auth_data = ""
                except UnicodeDecodeError:
                    auth_data = ""
                username, sep, password = auth_data.partition(":")
                if sep == ":":
                    user = auth.authenticate(username=username, password=password)
                    if user:
                        request.user = user
                        auth.login(request, user)
        username = getattr(settings, "DF_FAKE_AUTHENTICATION_USERNAME", None)
        if self.header and username and settings.DEBUG:
            remote_addr = request.META.get("REMOTE_ADDR")
            if remote_addr in settings.INTERNAL_IPS:
                request.META[self.header] = username
            elif remote_addr:
                logger.warning(
                    "Unable to use `settings.DF_FAKE_AUTHENTICATION_USERNAME`. "
                    "You should add %s to the list `settings.INTERNAL_IPS`."
                    % remote_addr
                )

        if self.header and self.header in request.META:
            remote_username = request.META.get(self.header)
            if (
                not remote_username or remote_username == "(null)"
            ):  # special case due to apache2+auth_mod_kerb :-(
                return
            remote_username = self.format_remote_username(remote_username)
            # noinspection PyTypeChecker
            self.remote_user_authentication(request, remote_username)

    # noinspection PyUnusedLocal,PyMethodMayBeStatic
    def process_response(self, request, response):
        response["X-UA-Compatible"] = "IE=edge,chrome=1"
        return response

    def remote_user_authentication(self, request, username):
        # AuthenticationMiddleware is required so that request.user exists.
        # noinspection PyTypeChecker
        if not hasattr(request, "user"):
            raise ImproperlyConfigured(
                "The Django remote user auth middleware requires the"
                " authentication middleware to be installed.  Edit your"
                " MIDDLEWARE_CLASSES setting to insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the RemoteUserMiddleware class."
            )
        # If the user is already authenticated and that user is the user we are
        # getting passed in the headers, then the correct user is already
        # persisted in the session and we don't need to continue.
        if request.user.is_authenticated:
            cleaned_username = self.clean_username(username, request)
            if request.user.get_username() == cleaned_username:
                request.remote_username = cleaned_username
                return
            else:
                self._remove_invalid_user(request)
        # We are seeing this user for the first time in this session, attempt
        # to authenticate the user.
        user = auth.authenticate(remote_user=username)
        if user:
            # User is valid.  Set request.user and persist user in the session
            # by logging the user in.
            request.user = user
            auth.login(request, user)
            request.remote_username = user.username

    # noinspection PyMethodMayBeStatic
    def format_remote_username(self, remote_username):
        return remote_username.partition("@")[0]
