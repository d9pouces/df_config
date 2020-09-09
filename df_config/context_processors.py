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
from django.conf import settings


def config(request):
    """
    Adds a few values to the request context.
    """
    return {
        "ADMIN_EMAIL": settings.ADMIN_EMAIL,
        "DF_PROJECT_NAME": settings.DF_PROJECT_NAME,
        "DF_PROJECT_VERSION": settings.DF_PROJECT_VERSION,
        "SERVER_URL": settings.SERVER_BASE_URL,
        "SERVER_NAME": settings.SERVER_NAME,
    }
