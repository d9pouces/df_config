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

from django.contrib.staticfiles.management.commands.collectstatic import (
    Command as BaseCommand,
)

from df_config.config.base import merger


# noinspection PyClassHasNoInit
class Command(BaseCommand):
    def handle(self, **options):
        merger.call_method_on_config_values("pre_collectstatic")
        super().handle(**options)
        merger.call_method_on_config_values("post_collectstatic")
