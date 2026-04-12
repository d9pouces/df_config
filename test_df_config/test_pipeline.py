import importlib.resources
import shutil

from django.test import TestCase

from df_config.apps.pipeline import (
    CssNanoCompressor,
    CssoCompressor,
    ESBuildCompressor,
    LightningcssCompressor,
    MinifyCompressor,
    TerserCompressor,
)


class TestCompressor(TestCase):
    checked_js = [
        (
            "first.js",
            "(function(){window.concat=function(){console.log(arguments)}})();\n",
        ),
        (
            "second.js",
            '(function(){window.cat=function(){console.log("hello world")}})();\n',
        ),
    ]

    def check_js_compressor(self, compressor, checked_js):

        for name, expected_content in checked_js:
            ref = importlib.resources.files("test_df_config").joinpath(f"data/{name}")
            with ref.open("r") as fd:
                content = fd.read()
                actual_content = compressor(verbose=False).compress_js(content)
                self.assertEqual(actual_content, expected_content)

    def check_css_compressor(self, compressor):

        for name in [
            "urls.css",
            "first.css",
            "second.css",
            "sourcemap.css",
            "urls.css",
        ]:
            ref = importlib.resources.files("test_df_config").joinpath(f"data/{name}")
            with ref.open("r") as fd:
                content = fd.read()
                compressor(verbose=False).compress_css(content)

    def test_lightningcss(self):
        if not shutil.which("lightningcss"):
            self.skipTest("lightningcss is not installed")
        self.check_css_compressor(LightningcssCompressor)

    def test_cssnano(self):
        if not shutil.which("postcss"):
            self.skipTest("cssnano is not installed")
        self.check_css_compressor(CssNanoCompressor)

    def test_minify(self):
        if not shutil.which("minify"):
            self.skipTest("minify is not installed")
        checked_js = [
            (
                "first.js",
                "(function(){window.concat=function(){console.log(arguments)}})()",
            ),
            (
                "second.js",
                '(function(){window.cat=function(){console.log("hello world")}})()',
            ),
        ]

        self.check_css_compressor(MinifyCompressor)
        self.check_js_compressor(MinifyCompressor, checked_js)

    def test_csso(self):
        if not shutil.which("csso"):
            self.skipTest("csso is not installed")
        self.check_css_compressor(CssoCompressor)

    def test_esbuild(self):
        if not shutil.which("esbuild"):
            self.skipTest("esbuild is not installed")
        self.check_js_compressor(ESBuildCompressor, self.checked_js)

    def test_terser(self):
        if not shutil.which("terser"):
            self.skipTest("terser is not installed")
        self.check_js_compressor(TerserCompressor, self.checked_js)
