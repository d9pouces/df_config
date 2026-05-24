"""Additional tests for df_config/apps/pipeline.py."""

import importlib
from unittest.mock import MagicMock, mock_open, patch

from django.test import TestCase, override_settings

from df_config.apps.pipeline import (
    CssNanoCompressor,
    CssoCompressor,
    ESBuildCompressor,
    LightningcssCompressor,
    NicerPipelineCachedStorage,
    PyScssCompiler,
    RcssCompressor,
    TerserCompressor,
    TypescriptCompiler,
)


class TestFilterNotImplemented(TestCase):
    """Test all filter_css/filter_js methods that raise NotImplementedError."""

    compressor_classes = [
        RcssCompressor,
        CssNanoCompressor,
        CssoCompressor,
        LightningcssCompressor,
        TerserCompressor,
        ESBuildCompressor,
    ]

    def test_filter_css_not_implemented(self):
        for cls in self.compressor_classes:
            obj = cls(verbose=False)
            with self.assertRaises(
                NotImplementedError, msg=f"{cls.__name__}.filter_css"
            ):
                obj.filter_css("body { color: red; }")

    def test_filter_js_not_implemented(self):
        for cls in self.compressor_classes:
            obj = cls(verbose=False)
            with self.assertRaises(
                NotImplementedError, msg=f"{cls.__name__}.filter_js"
            ):
                obj.filter_js("var x = 1;")


class TestRcssCompressor(TestCase):
    """Test RcssCompressor.compress_css using a mocked rcssmin module."""

    def test_compress_css(self):
        mock_rcssmin = MagicMock()
        mock_rcssmin.cssmin.return_value = "minified_css"
        with patch.dict("sys.modules", {"rcssmin": mock_rcssmin}):
            result = RcssCompressor(verbose=False).compress_css("body { color: red; }")
        self.assertEqual(result, "minified_css")
        mock_rcssmin.cssmin.assert_called_once_with("body { color: red; }")


class TestPyScssCompiler(TestCase):
    """Test PyScssCompiler match_file and compile_file."""

    def test_match_file_scss(self):
        compiler = PyScssCompiler(verbose=False)
        self.assertTrue(compiler.match_file("styles.scss"))

    def test_match_file_sass(self):
        compiler = PyScssCompiler(verbose=False)
        self.assertTrue(compiler.match_file("theme.sass"))

    def test_match_file_other(self):
        compiler = PyScssCompiler(verbose=False)
        self.assertFalse(compiler.match_file("styles.css"))
        self.assertFalse(compiler.match_file("script.js"))

    def test_compile_file_not_verbose(self):
        mock_scss = MagicMock()
        mock_compiler_inst = MagicMock()
        mock_compiler_inst.compile.return_value = "compiled_css"
        mock_scss.Compiler.return_value = mock_compiler_inst

        with patch.dict("sys.modules", {"scss": mock_scss}):
            with patch("builtins.open", mock_open()) as m_open:
                with override_settings(STATIC_ROOT="/tmp/static"):
                    compiler = PyScssCompiler(verbose=False)
                    compiler.compile_file("input.scss", "output.css")

        mock_compiler_inst.compile.assert_called_once_with("input.scss")
        m_open.assert_called_once_with("output.css", "w")

    def test_compile_file_verbose(self):
        mock_scss = MagicMock()
        mock_compiler_inst = MagicMock()
        mock_compiler_inst.compile.return_value = "compiled_css_verbose"
        mock_scss.Compiler.return_value = mock_compiler_inst

        with patch.dict("sys.modules", {"scss": mock_scss}):
            with patch("builtins.open", mock_open()):
                with patch("builtins.print") as mock_print:
                    with override_settings(STATIC_ROOT="/tmp/static"):
                        compiler = PyScssCompiler(verbose=True)
                        compiler.compile_file("input.scss", "output.css")
        mock_print.assert_called_once_with("compiled_css_verbose")


class TestTypescriptCompiler(TestCase):
    """Test TypescriptCompiler match_file and compile_file."""

    def _make_compiler(self):
        """Create a TypescriptCompiler instance without calling __init__."""
        compiler = TypescriptCompiler.__new__(TypescriptCompiler)
        compiler.verbose = False
        return compiler

    def test_match_file_ts(self):
        compiler = self._make_compiler()
        self.assertTrue(compiler.match_file("app.ts"))

    def test_match_file_other(self):
        compiler = self._make_compiler()
        self.assertFalse(compiler.match_file("app.js"))
        self.assertFalse(compiler.match_file("app.tsx"))

    def test_compile_file(self):
        compiler = self._make_compiler()
        with patch.object(compiler, "execute_command") as mock_exec:
            with override_settings(
                TYPESCRIPT_BINARY="tsc",
                TYPESCRIPT_ARGUMENTS=["--target", "es6"],
            ):
                compiler.compile_file("input.ts", "output.js")
        mock_exec.assert_called_once_with(
            ["tsc", "--target", "es6", "--outFile", "output.js", "input.ts"]
        )


class TestTerserCompressorVerbose(TestCase):
    """Test TerserCompressor verbose branches."""

    def test_compress_js_verbose(self):
        compressor = TerserCompressor(verbose=True)
        with patch.object(
            compressor, "execute_command", return_value="min_js"
        ) as mock_exec:
            with override_settings(TERSER_BINARY="terser", TERSER_ARGUMENTS=[]):
                result = compressor.compress_js("var x = 1;")
        self.assertEqual(result, "min_js")
        command = mock_exec.call_args[0][0]
        self.assertIn("--verbose", command)

    def test_compress_js_not_verbose(self):
        compressor = TerserCompressor(verbose=False)
        with patch.object(
            compressor, "execute_command", return_value="min_js"
        ) as mock_exec:
            with override_settings(TERSER_BINARY="terser", TERSER_ARGUMENTS=[]):
                result = compressor.compress_js("var x = 1;")
        self.assertEqual(result, "min_js")
        command = mock_exec.call_args[0][0]
        self.assertNotIn("--verbose", command)


class TestESBuildCompressorVerbose(TestCase):
    """Test ESBuildCompressor verbose branches."""

    def test_compress_js_verbose(self):
        compressor = ESBuildCompressor(verbose=True)
        with patch.object(
            compressor, "execute_command", return_value="min_js"
        ) as mock_exec:
            with override_settings(
                ESBUILD_BINARY="esbuild", ESBUILD_ARGUMENTS=["--minify"]
            ):
                result = compressor.compress_js("var x = 1;")
        self.assertEqual(result, "min_js")
        command = mock_exec.call_args[0][0]
        self.assertIn("--verbose", command)

    def test_compress_js_not_verbose(self):
        compressor = ESBuildCompressor(verbose=False)
        with patch.object(
            compressor, "execute_command", return_value="min_js"
        ) as mock_exec:
            with override_settings(
                ESBUILD_BINARY="esbuild", ESBUILD_ARGUMENTS=["--minify"]
            ):
                result = compressor.compress_js("var x = 1;")
        self.assertEqual(result, "min_js")
        command = mock_exec.call_args[0][0]
        self.assertNotIn("--verbose", command)


class TestNicerPipelineCachedStorage(TestCase):
    """Test NicerPipelineCachedStorage.hashed_name."""

    def test_hashed_name_success(self):
        from pipeline.storage import PipelineManifestStorage

        with patch.object(
            PipelineManifestStorage, "hashed_name", return_value="file.abc123.css"
        ):
            storage = NicerPipelineCachedStorage.__new__(NicerPipelineCachedStorage)
            result = storage.hashed_name("file.css")
        self.assertEqual(result, "file.abc123.css")

    def test_hashed_name_value_error(self):
        from pipeline.storage import PipelineManifestStorage

        with patch.object(
            PipelineManifestStorage,
            "hashed_name",
            side_effect=ValueError("file.css not found"),
        ):
            storage = NicerPipelineCachedStorage.__new__(NicerPipelineCachedStorage)
            with self.assertRaises(ValueError) as ctx:
                storage.hashed_name("file.css")
        self.assertIn("collectstatic", str(ctx.exception))


class TestModuleLoadBranches(TestCase):
    """Test module-level conditional branches via importlib.reload."""

    def test_module_reload_no_pipeline(self):
        """Cover the USE_PIPELINE=False branch (fake base classes)."""
        import df_config.apps.pipeline as pipeline_mod

        try:
            with override_settings(USE_PIPELINE=False, USE_WHITENOISE=False):
                importlib.reload(pipeline_mod)
            self.assertIsNone(pipeline_mod.PipelineManifestStorage)
            self.assertIsNone(pipeline_mod.PipelineMixin)
            self.assertIsNone(pipeline_mod.NicerPipelineCachedStorage)
            self.assertIsNone(pipeline_mod.PipelineCompressedManifestStaticFilesStorage)
            self.assertIsNone(pipeline_mod.CompressedManifestStaticFilesStorage)
            # Verify fake SubProcessCompressor is a class
            self.assertTrue(callable(pipeline_mod.SubProcessCompressor))
            fake = pipeline_mod.SubProcessCompressor(verbose=True)
            self.assertTrue(fake.verbose)
        finally:
            with override_settings(USE_PIPELINE=True, USE_WHITENOISE=False):
                importlib.reload(pipeline_mod)

    def test_module_reload_with_whitenoise(self):
        """Cover the USE_WHITENOISE=True branch (real import + combined storage class)."""
        import df_config.apps.pipeline as pipeline_mod

        try:
            with override_settings(USE_PIPELINE=True, USE_WHITENOISE=True):
                importlib.reload(pipeline_mod)
            self.assertIsNotNone(pipeline_mod.CompressedManifestStaticFilesStorage)
            self.assertIsNotNone(
                pipeline_mod.PipelineCompressedManifestStaticFilesStorage
            )
        finally:
            with override_settings(USE_PIPELINE=True, USE_WHITENOISE=False):
                importlib.reload(pipeline_mod)
