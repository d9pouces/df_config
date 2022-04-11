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
from django.apps import AppConfig
from django.db.models.signals import post_migrate, pre_migrate

# noinspection PyUnresolvedReferences
import df_config.checks
from df_config.config.base import merger


class MigrationCounter:
    def __init__(self):
        self.last_app_config = None

    # noinspection PyUnusedLocal
    def pre_migrate(self, *args, app_config: AppConfig = None, **kwargs):
        if self.last_app_config is None:  # this is the pre_migrate of first app
            merger.call_method_on_config_values("pre_migrate")
        self.last_app_config = app_config.name

    # noinspection PyUnusedLocal
    def post_migrate(self, *args, app_config: AppConfig = None, **kwargs):
        if (
            app_config.name == self.last_app_config
        ):  # this is the post_migrate of the last app
            merger.call_method_on_config_values("post_migrate")


migration_counter = MigrationCounter()

pre_migrate.connect(migration_counter.pre_migrate)
post_migrate.connect(migration_counter.post_migrate)
