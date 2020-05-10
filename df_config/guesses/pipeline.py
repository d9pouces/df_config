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
import shutil
from typing import Dict, List, Optional, Tuple, Union

from df_config.utils import is_package_present

available_css_compressor = [
    ("df_config.apps.pipeline.CssNanoCompressor", "CSSNANO_BINARY", None),
    ("pipeline.compressors.yuglify.YuglifyCompressor", "YUGLIFY_BINARY", None),
    ("pipeline.compressors.yui.YUICompressor", "YUI_BINARY", None),
    ("pipeline.compressors.csstidy.CSSTidyCompressor", "CSSTIDY_BINARY", None),
    ("pipeline.compressors.cssmin.CSSMinCompressor", "CSSMIN_BINARY", None),
    ("df_config.apps.pipeline.RcssCompressor", None, "rcssmin"),
    ("pipeline.compressors.NoopCompressor", None, None),
]
available_js_compressors = [
    ("df_config.apps.pipeline.TerserCompressor", "TERSER_BINARY", None),
    ("pipeline.compressors.uglifyjs.UglifyJSCompressor", "UGLIFYJS_BINARY", None),
    ("pipeline.compressors.yuglify.YuglifyCompressor", "YUGLIFY_BINARY", None),
    ("pipeline.compressors.yui.YUICompressor", "YUI_BINARY", None),
    ("pipeline.compressors.closure.ClosureCompressor", "CLOSURE_BINARY", None),
    ("pipeline.compressors.jsmin.JSMinCompressor", None, "jsmin"),
    ("pipeline.compressors.slimit.SlimItCompressor", None, "slimit"),
    ("pipeline.compressors.NoopCompressor", None, None),
]
available_compilers = [
    ("pipeline.compilers.coffee.CoffeeScriptCompiler", "COFFEE_SCRIPT_BINARY", None),
    ("pipeline.compilers.livescript.LiveScriptCompiler", "LIVE_SCRIPT_BINARY", None),
    ("pipeline.compilers.less.LessCompiler", "LESS_BINARY", None),
    ("pipeline.compilers.sass.SASSCompiler", "SASS_BINARY", None),
    ("pipeline.compilers.stylus.StylusCompiler", "STYLUS_BINARY", None),
    ("pipeline.compilers.es6.ES6Compiler", "BABEL_BINARY", None),
    ("df_config.apps.pipeline.TypescriptCompiler", "TYPESCRIPT_BINARY", None),
    ("df_config.apps.pipeline.PyScssCompiler", None, "scss"),
]


def required_settings(
        candidates: List[Tuple[str, Optional[str], Optional[str]]]
) -> List[str]:
    return [x[1] for x in candidates if x[1]]


def guess_pipeline_extension(
        candidates: List[Tuple[str, Optional[str], Optional[str]]],
        settings_dict: Dict,
        one: bool = False,
) -> Union[List[str], Optional[str]]:
    extensions = []
    for extension, setting, package in candidates:
        if package and not is_package_present(package):
            continue
        if setting and not shutil.which(settings_dict[setting]):
            continue
        if one:
            return extension
        extensions.append(extension)
    if one:
        return None
    return extensions


def pipeline_css_compressor(settings_dict: Dict) -> str:
    return guess_pipeline_extension(available_css_compressor, settings_dict, one=True)


pipeline_css_compressor.required_settings = required_settings(available_css_compressor)


def pipeline_js_compressor(settings_dict: Dict) -> str:
    return guess_pipeline_extension(available_js_compressors, settings_dict, one=True)


pipeline_js_compressor.required_settings = required_settings(available_js_compressors)


def pipeline_compilers(settings_dict: Dict) -> List[str]:
    return guess_pipeline_extension(available_compilers, settings_dict)


pipeline_compilers.required_settings = required_settings(available_compilers)
