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

from django.conf import settings

try:
    from allauth.account.adapter import DefaultAccountAdapter
except ImportError:
    DefaultAccountAdapter = object


class AccountAdapter(DefaultAccountAdapter):
    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def is_open_for_signup(self, request):
        return settings.DF_ALLOW_USER_CREATION and settings.DF_ALLOW_LOCAL_USERS
