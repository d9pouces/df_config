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
import os
import sys
from distutils.spawn import find_executable

from django.core.checks import Error, register

from df_config.utils import is_package_present

settings_check_results = []


def missing_package(package_name, desc=""):
    if hasattr(sys, "real_prefix"):  # inside a virtualenv
        cmd = "Try 'pip install %s' to install it." % package_name
    elif __file__.startswith(os.environ.get("HOME", "/home")):
        cmd = "Try 'pip3 install --user %s' to install it." % package_name
    else:
        cmd = "Try 'sudo pip3 install %s' to install it." % package_name
    return Error(
        "Python package '%s' is required%s. %s" % (package_name, desc, cmd),
        obj="configuration",
    )


def get_pipeline_requirements():
    from df_config.config.base import merger

    engines = [
        merger.settings.get("PIPELINE_CSS_COMPRESSOR", ""),
        merger.settings.get("PIPELINE_JS_COMPRESSOR", ""),
    ]
    engines += merger.settings.get("PIPELINE_COMPILERS", [])

    binaries = {
        "pipeline.compilers.coffee.CoffeeScriptCompiler": "COFFEE_SCRIPT_BINARY",
        "pipeline.compilers.livescript.LiveScriptCompiler": "LIVE_SCRIPT_BINARY",
        "pipeline.compilers.less.LessCompiler": "LESS_BINARY",
        "pipeline.compilers.sass.SASSCompiler": "SASS_BINARY",
        "pipeline.compilers.stylus.StylusCompiler": "STYLUS_BINARY",
        "pipeline.compilers.es6.ES6Compiler": "BABEL_BINARY",
        "pipeline.compressors.yuglify.YuglifyCompressor": "YUGLIFY_BINARY",
        "pipeline.compressors.yui.YUICompressor": "YUI_BINARY",
        "pipeline.compressors.closure.ClosureCompressor": "CLOSURE_BINARY",
        "pipeline.compressors.uglifyjs.UglifyJSCompressor": "UGLIFYJS_BINARY",
        "pipeline.compressors.csstidy.CSSTidyCompressor": "CSSTIDY_BINARY",
        "pipeline.compressors.cssmin.CSSMinCompressor": "CSSMIN_BINARY",
        "df_config.apps.pipeline.TypescriptCompiler": "TYPESCRIPT_BINARY",
        "pipeline_typescript.compilers.TypescriptCompiler": "PIPELINE_TYPESCRIPT_BINARY",
    }
    pip_packages = {
        "pipeline.compressors.jsmin.JSMinCompressor": ("jsmin", "jsmin"),
        "pipeline.compressors.slimit.SlimItCompressor": ("slimit", "slimit"),
        "df_config.apps.pipeline.RcssCompressor": ("rcssmin", "rcssmin"),
        "df_config.apps.pipeline.PyScssCompiler": ("scss", "pyScss"),
    }
    npm_packages = {"lsc": "lsc", "tsc": "typescript"}
    gem_packages = {}
    result = {"gem": [], "pip": [], "npm": [], "other": [], "all": []}
    for engine in engines:
        if engine in binaries:
            name = merger.settings.get(binaries[engine], "program")
            result["all"].append(name)
            if name in npm_packages:
                result["npm"].append(npm_packages[name])
            elif name in gem_packages:
                result["gem"].append(name)
            else:
                result["other"].append(name)
        elif engine in pip_packages:
            result["pip"].append(pip_packages[engine])
    for v in result.values():
        v.sort()
    return result


# noinspection PyUnusedLocal
@register()
def pipeline_check(app_configs, **kwargs):
    """Check if dependencies used by `django-pipeline` are installed.
    """
    check_results = []
    requirements = get_pipeline_requirements()
    for name in requirements["all"]:
        if not find_executable(name):
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
