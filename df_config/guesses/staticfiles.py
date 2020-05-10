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


def static_storage(settings_dict):
    if settings_dict["PIPELINE_ENABLED"]:
        return "df_config.apps.pipeline.NicerPipelineCachedStorage"
    return "django.contrib.staticfiles.storage.StaticFilesStorage"


static_storage.required_settings = ["PIPELINE_ENABLED"]


def pipeline_enabled(settings_dict):
    return settings_dict["USE_PIPELINE"] and not settings_dict["DEBUG"]


pipeline_enabled.required_settings = ["DEBUG", "USE_PIPELINE"]


def static_finder(settings_dict):
    r = [
        "django.contrib.staticfiles.finders.FileSystemFinder",
        "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    ]
    if settings_dict["USE_PIPELINE"]:
        r.append("pipeline.finders.PipelineFinder")
    return r


static_finder.required_settings = ["DEBUG", "USE_PIPELINE"]
