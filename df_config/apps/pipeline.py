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
"""Define extra compressors or compilers for django-pipeline."""

import os
from pathlib import Path

from django.conf import settings

if getattr(settings, "USE_PIPELINE", False):
    from pipeline.compilers import SubProcessCompiler
    from pipeline.compressors import SubProcessCompressor
    from pipeline.storage import PipelineManifestStorage, PipelineMixin
else:
    SubProcessCompressor = object
    SubProcessCompiler = object
    PipelineManifestStorage = None
    PipelineMixin = None


if getattr(settings, "USE_WHITENOISE", False):
    # noinspection PyPackageRequirements,PyUnresolvedReferences
    from whitenoise.storage import CompressedManifestStaticFilesStorage
else:
    CompressedManifestStaticFilesStorage = None


class RcssCompressor(SubProcessCompressor):
    """CSS compressor based on the Python library rcssmin.

    (https://github.com/ndparker/rcssmin).
    """

    def filter_css(self, css):
        """Not implemented."""
        raise NotImplementedError

    def filter_js(self, js):
        """Not implemented."""
        raise NotImplementedError

    # noinspection PyMethodMayBeStatic
    def compress_css(self, css):
        """Compress a block of CSS code using the "rcssmin" module."""
        # noinspection PyUnresolvedReferences,PyPackageRequirements
        from rcssmin import cssmin

        return cssmin(css)


class CssNanoCompressor(SubProcessCompressor):
    """CSS compressor based on the "cssnano" command."""

    def compress_css(self, css):
        """Compress a block of CSS code using the "cssnano" command."""
        command = [settings.CSSNANO_BINARY] + settings.CSSNANO_ARGUMENTS
        return self.execute_command(command, css)

    def filter_css(self, css):
        """Not implemented."""
        raise NotImplementedError

    def filter_js(self, js):
        """Not implemented."""
        raise NotImplementedError


class TerserCompressor(SubProcessCompressor):
    """JavaScript compressor based on the "terser" command."""

    def compress_js(self, js):
        """Compress a block of JavaScript code using the "terser" command."""
        command = [settings.TERSER_BINARY, settings.TERSER_ARGUMENTS, "--"]
        if self.verbose:
            command += ["--verbose"]
        return self.execute_command(command, js)

    def filter_css(self, css):
        """Not implemented."""
        raise NotImplementedError

    def filter_js(self, js):
        """Not implemented."""
        raise NotImplementedError


class PyScssCompiler(SubProcessCompiler):
    """SASS (.scss) compiler based on the Python library pyScss.

    (http://pyscss.readthedocs.io/en/latest/ ).
    However, this compiler is limited to SASS 3.2 and cannot compile modern projets like Bootstrap 4.
    Please use :class:`pipeline.compilers.sass.SASSCompiler` if you use modern SCSS files.

    """

    output_extension = "css"

    # noinspection PyMethodMayBeStatic
    def match_file(self, filename):
        """Return True if the file is a SASS file."""
        return filename.endswith(".scss") or filename.endswith(".sass")

    # noinspection PyUnusedLocal
    def compile_file(self, infile, outfile, outdated=False, force=False):
        """Compile a SASS file using the "scss" command."""
        # noinspection PyUnresolvedReferences,PyUnresolvedReferences,PyPackageRequirements
        from scss import Compiler

        root = Path(os.path.abspath(settings.STATIC_ROOT))
        compiler = Compiler(root=root, search_path=("./",))
        css_content = compiler.compile(infile)
        with open(outfile, "w") as fd:
            fd.write(css_content)
        # noinspection PyUnresolvedReferences
        if self.verbose:
            print(css_content)


class TypescriptCompiler(SubProcessCompiler):
    """TypeScript (.ts) compiler using "tsc" (https://www.typescriptlang.org)."""

    output_extension = "js"

    # noinspection PyMethodMayBeStatic
    def match_file(self, filename):
        """Return True if the file is a TypeScript file."""
        return filename.endswith(".ts")

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def compile_file(self, infile, outfile, outdated=False, force=False):
        """Compile a TypeScript file using the "tsc" command."""
        command = (
            [settings.TYPESCRIPT_BINARY]
            + settings.TYPESCRIPT_ARGUMENTS
            + ["--outFile", outfile, infile]
        )
        self.execute_command(command)


if PipelineManifestStorage:

    class NicerPipelineCachedStorage(PipelineManifestStorage):
        """Display a better exception."""

        def hashed_name(self, name, content=None, filename=None):
            """Display a better exception if the file is not found."""
            try:
                return super().hashed_name(name, content=content)
            except ValueError as e:
                raise ValueError(
                    "%s. Did you run the command 'collectstatic'?" % e.args[0]
                )

else:
    NicerPipelineCachedStorage = None

if PipelineMixin and CompressedManifestStaticFilesStorage:

    class PipelineCompressedManifestStaticFilesStorage(
        PipelineMixin, CompressedManifestStaticFilesStorage
    ):
        """Mix django-pipeline and whitenoise."""

        pass

else:
    PipelineCompressedManifestStaticFilesStorage = None
