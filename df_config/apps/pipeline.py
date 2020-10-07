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


# noinspection PyClassHasNoInit,PyAbstractClass
import os
import subprocess
from pathlib import Path

from django.conf import settings

if settings.USE_PIPELINE:

    # noinspection PyPackageRequirements,PyUnresolvedReferences
    from pipeline.compressors import CompressorBase, SubProcessCompressor

    # noinspection PyPackageRequirements,PyUnresolvedReferences
    from pipeline.compilers import CompilerBase

    # noinspection PyPackageRequirements,PyUnresolvedReferences
    from pipeline.storage import PipelineManifestStorage, PipelineMixin
else:
    CompressorBase = object
    CompilerBase = object
    SubProcessCompressor = object
    PipelineManifestStorage = None
    PipelineMixin = None


if settings.USE_WHITENOISE:
    # noinspection PyPackageRequirements,PyUnresolvedReferences
    from whitenoise.storage import CompressedManifestStaticFilesStorage
else:
    CompressedManifestStaticFilesStorage = None


class RcssCompressor(CompressorBase):
    """
    CSS compressor based on the Python library slimit
    (https://github.com/ndparker/rcssmin).
    """

    def filter_css(self, css):
        raise NotImplementedError

    def filter_js(self, js):
        raise NotImplementedError

    # noinspection PyMethodMayBeStatic
    def compress_css(self, css):
        # noinspection PyUnresolvedReferences,PyPackageRequirements
        from rcssmin import cssmin

        return cssmin(css)


class CssNanoCompressor(SubProcessCompressor):
    def compress_css(self, css):
        command = [settings.CSSNANO_BINARY] + settings.CSSNANO_ARGUMENTS
        return self.execute_command(command, css)

    def filter_css(self, css):
        raise NotImplementedError

    def filter_js(self, js):
        raise NotImplementedError


class TerserCompressor(SubProcessCompressor):
    def compress_js(self, js):
        command = [settings.TERSER_BINARY, settings.TERSER_ARGUMENTS, "--"]
        if self.verbose:
            command += ["--verbose"]
        return self.execute_command(command, js)

    def filter_css(self, css):
        raise NotImplementedError

    def filter_js(self, js):
        raise NotImplementedError


# noinspection PyClassHasNoInit
class PyScssCompiler(CompilerBase):
    """ SASS (.scss) compiler based on the Python library pyScss.
    (http://pyscss.readthedocs.io/en/latest/ ).
    However, this compiler is limited to SASS 3.2 and cannot compile modern projets like Bootstrap 4.
    Please use :class:`pipeline.compilers.sass.SASSCompiler` if you use modern SCSS files.

    """

    output_extension = "css"

    # noinspection PyMethodMayBeStatic
    def match_file(self, filename):
        return filename.endswith(".scss") or filename.endswith(".sass")

    # noinspection PyUnusedLocal
    def compile_file(self, infile, outfile, outdated=False, force=False):
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


# noinspection PyClassHasNoInit
class TypescriptCompiler(CompilerBase):
    """ TypeScript (.ts) compiler using "tsc".
    (https://www.typescriptlang.org ).

    """

    output_extension = "js"

    # noinspection PyMethodMayBeStatic
    def match_file(self, filename):
        return filename.endswith(".ts")

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def compile_file(self, infile, outfile, outdated=False, force=False):
        # noinspection PyPackageRequirements,PyUnresolvedReferences
        from pipeline.exceptions import CompilerError

        command = (
            [settings.TYPESCRIPT_BINARY]
            + settings.TYPESCRIPT_ARGUMENTS
            + ["-out", outfile, infile]
        )
        try:
            p = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, __ = p.communicate(b"")
            if p.returncode != 0:
                raise CompilerError(
                    "Unable to execute TypeScript",
                    command=command,
                    error_output=stdout.decode(),
                )
        except Exception as e:
            raise CompilerError(e, command=command, error_output=str(e))


if PipelineManifestStorage:

    class NicerPipelineCachedStorage(PipelineManifestStorage):
        """ display a better exception"""

        def hashed_name(self, name, content=None, filename=None):
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
        """mix django-pipeline and whitenoise"""

        pass


else:
    PipelineCompressedManifestStaticFilesStorage = None
