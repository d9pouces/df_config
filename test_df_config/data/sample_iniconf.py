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
from df_config.config.fields import CharConfigField

MAPPING = [
    CharConfigField(
        "global.admin_email",
        "ADMIN_EMAIL",
        help_str="e-mail address for receiving logged errors",
    ),
    CharConfigField(
        "global.data",
        "LOCAL_PATH",
        help_str="where all data will be stored (static/uploaded/temporary files, …). "
        "If you change it, you must run the collectstatic and migrate commands again.\n",
    ),
]
