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
"""Define a new authentication backend that add the newly created user to the selected groups."""
import logging

from django.conf import settings
from django.contrib.auth.backends import RemoteUserBackend
from django.contrib.auth.models import Group
from django.http import HttpRequest
from django.utils.functional import cached_property

logger = logging.getLogger("django.request")

_CACHED_GROUPS = {}


class DefaultGroupsRemoteUserBackend(RemoteUserBackend):
    """Add groups to new users.

    Based on :class:`django.contrib.auth.backends.RemoteUserBackend`.
    Only overrides the `configure_user` method to add the required groups.
    """

    @property
    def create_unknown_user(self):
        """Return True if the user should be automatically created."""
        return getattr(settings, "DF_ALLOW_USER_CREATION", True)

    @cached_property
    def ldap_backend(self):
        """Return the LDAP backend if it is enabled."""
        # noinspection PyUnresolvedReferences,PyPackageRequirements
        from django_auth_ldap.backend import LDAPBackend

        return LDAPBackend()

    def authenticate(self, *args, **kwargs):
        """Authenticate the user and update it if needed."""
        remote_user = kwargs.get("remote_user")
        if (
            remote_user
            and getattr(settings, "AUTH_LDAP_SERVER_URI", None)
            and getattr(settings, "AUTH_LDAP_ALWAYS_UPDATE_USER", None)
        ):
            user = self.ldap_backend.populate_user(remote_user)
            if user:
                return user
        return super().authenticate(*args, remote_user)

    def configure_user(self, request, user=None, created=True):
        """Configure a user after creation and returns the updated user.

        By default, returns the user unmodified; only add it to the default group.
        """
        if user is None and not isinstance(request, HttpRequest):  # for compatibility
            user = request
        if user is None:
            return
        for group_name in getattr(settings, "DF_DEFAULT_GROUPS", []):
            if group_name not in _CACHED_GROUPS:
                _CACHED_GROUPS[group_name] = Group.objects.get_or_create(
                    name=str(group_name)
                )[0]
            user.groups.add(_CACHED_GROUPS[group_name])
        return user
