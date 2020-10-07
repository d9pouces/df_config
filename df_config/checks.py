# ##############################################################################
#  This file is part of Interdiode                                             #
#                                                                              #
#  Copyright (C) 2020 Matthieu Gallet <matthieu.gallet@19pouces.net>           #
#  All Rights Reserved                                                         #
#                                                                              #
# ##############################################################################
import os
import shutil
import sys

from django.core.checks import Error, register, Warning

from df_config.guesses.pipeline import (
    available_compilers,
    available_css_compressor,
    available_js_compressors,
)
from df_config.utils import is_package_present

settings_check_results = []


def missing_package(package_name, desc=""):
    if hasattr(sys, "real_prefix"):  # inside a virtualenv
        cmd = "Try 'python -m pip install %s' to install it." % package_name
    elif __file__.startswith(os.environ.get("HOME", "/home")):
        cmd = "Try 'python3 -m pip install --user %s' to install it." % package_name
    else:
        cmd = "Try 'sudo python3 -m pip install %s' to install it." % package_name
    return Warning(
        "Python package '%s' is required%s. %s" % (package_name, desc, cmd),
        obj="configuration",
    )


def get_pipeline_requirements():
    from df_config.config.base import merger

    engine_to_binaries = {}  # engine_to_binaries["eng.ine"] = "ENGINE_BINARY"
    engine_to_binaries.update({x[0]: x[1] for x in available_css_compressor if x[1]})
    engine_to_binaries.update({x[0]: x[1] for x in available_js_compressors if x[1]})
    engine_to_binaries.update({x[0]: x[1] for x in available_compilers if x[1]})
    engines = [
        merger.settings.get("PIPELINE_CSS_COMPRESSOR", ""),
        merger.settings.get("PIPELINE_JS_COMPRESSOR", ""),
    ]
    engines += merger.settings.get("PIPELINE_COMPILERS", [])
    pip_packages = {
        "pipeline.compressors.jsmin.JSMinCompressor": ("jsmin", "jsmin"),
        "pipeline.compressors.slimit.SlimItCompressor": ("slimit", "slimit"),
        "df_config.apps.pipeline.RcssCompressor": ("rcssmin", "rcssmin"),
        "df_config.apps.pipeline.PyScssCompiler": ("scss", "pyScss"),
    }
    result = {"gem": [], "pip": [], "npm": [], "other": [], "all": []}
    for engine in engines:
        if engine in engine_to_binaries:
            name = merger.settings.get(engine_to_binaries[engine], "program")
            result["all"].append(name)
        elif engine in pip_packages:
            result["pip"].append(pip_packages[engine])
    for v in result.values():
        v.sort()
    return result


# noinspection PyUnusedLocal
@register()
def pipeline_check(app_configs, **kwargs):
    return settings_check_results


# noinspection PyUnusedLocal
@register()
def pipeline_check(app_configs, **kwargs):
    """Check if dependencies used by `django-pipeline` are installed.
    """
    check_results = []
    requirements = get_pipeline_requirements()
    for name in requirements["all"]:
        if not shutil.which(name):
            check_results.append(
                Error(
                    "'%s' is required by 'django-pipeline' and is not found in PATH."
                    % name,
                    obj="configuration",
                )
            )
    for name, package in requirements["pip"]:
        if not is_package_present(name):
            check_results.append(missing_package(package, " by 'django-pipeline'"))
    return check_results
