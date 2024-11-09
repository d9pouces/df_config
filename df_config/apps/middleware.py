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
"""Define a new authentication middleware that also complete the remote address of the request."""
import base64
import binascii
import logging
from functools import lru_cache

from django.conf import settings
from django.contrib import auth
from django.contrib.auth.middleware import RemoteUserMiddleware
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest

logger = logging.getLogger("django.request")


class DFConfigMiddleware(RemoteUserMiddleware):
    """Like :class:`django.contrib.auth.middleware.RemoteUserMiddleware`.

    Differences:
    * can use any header defined by the setting `DF_REMOTE_USER_HEADER`,
    * handle the HTTP_X_FORWARDED_FOR HTTP header (set the right client IP)
    * handle HTTP basic authentication
    * set response header for Internet Explorer (to use its most recent render engine)
    """

    @lru_cache()
    def get_remoteuser_header(self):
        """Return the header to use for the remote user."""
        # avoid cached_property to ease unittests
        header = getattr(settings, "DF_REMOTE_USER_HEADER", None)
        if header:
            header = header.upper().replace("-", "_")
        return header

    @lru_cache()
    def get_df_fake_authentication_username(self):
        """Return the username to add in the REMOTE_USER header for testing purpose."""
        # avoid cached_property to ease unittests
        return getattr(settings, "DF_FAKE_AUTHENTICATION_USERNAME", None)
        # can emulate an authentication by remote user, for testing purpose

    def process_request(self, request: HttpRequest):
        """Set request.user using the REMOTE_USER header and the remote address."""
        request.remote_username = None

        use_x_forwarded_for = getattr(settings, "USE_X_FORWARDED_FOR", False)
        if use_x_forwarded_for and "HTTP_X_FORWARDED_FOR" in request.META:
            request.META["REMOTE_ADDR"] = (
                request.META["HTTP_X_FORWARDED_FOR"].split(",")[0].strip()
            )
        use_http_basic_auth = getattr(settings, "USE_HTTP_BASIC_AUTH", False)
        if use_http_basic_auth and "HTTP_AUTHORIZATION" in request.META:
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

        remote_user_header = self.get_remoteuser_header()
        if (
            settings.DEBUG
            and remote_user_header
            and self.get_df_fake_authentication_username()
        ):
            # set the remote username for testing purpose
            remote_addr = request.META.get("REMOTE_ADDR")
            if remote_addr in settings.INTERNAL_IPS:
                request.META[
                    remote_user_header
                ] = self.get_df_fake_authentication_username()
            elif remote_addr:
                logger.warning(
                    "Unable to use `settings.DF_FAKE_AUTHENTICATION_USERNAME`. "
                    "You should add %s to the list `settings.INTERNAL_IPS`."
                    % remote_addr
                )

        if remote_user_header and remote_user_header in request.META:
            # authenticate the user using the remote user header
            remote_username = request.META.get(remote_user_header)
            if (
                not remote_username or remote_username == "(null)"
            ):  # special case due to apache2+auth_mod_kerb :-(
                return
            remote_username = self.format_remote_username(remote_username)
            # noinspection PyTypeChecker
            self.remote_user_authentication(request, remote_username)

    # noinspection PyUnusedLocal,PyMethodMayBeStatic
    def process_response(self, request, response):
        """Set the X-UA-Compatible header for Internet Explorer."""
        response["X-UA-Compatible"] = "IE=edge,chrome=1"
        return response

    def remote_user_authentication(self, request, username):
        """Set request.user using the REMOTE_USER header."""
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
        """Format the username by removing the realm."""
        return remote_username.partition("@")[0]
