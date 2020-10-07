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
import io
from argparse import ArgumentParser

from django.core.management import BaseCommand
from django.core.management.base import OutputWrapper
from django.core.management.color import no_style
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from df_config import __version__ as version
from df_config.config.base import merger
from df_config.utils import guess_version, remove_arguments_from_help

__author__ = "Matthieu Gallet"

from df_config.config.values_providers import (
    EnvironmentConfigProvider,
    IniConfigProvider,
)


class Command(BaseCommand):
    help = (
        "show the current configuration."
        'Can display as python file ("config python") or as .ini file ("config ini"). Use -v 2 to display more info.'
    )
    requires_system_checks = False
    options = {
        "python": "display the current config as Python module",
        "ini": "display the current config as .ini file",
        "env": "display the current config as environment variables",
    }

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument(
            "action",
            default="show",
            choices=self.options,
            help=",\n".join(['"%s": %s' % x for x in self.options.items()]),
        )
        parser.add_argument(
            "--filename", default=None, help="write output to this file"
        )
        remove_arguments_from_help(
            parser, {"--settings", "--traceback", "--pythonpath"}
        )

    def handle(self, *args, **options):
        try:
            self.handle_head(**options)
        except BrokenPipeError:
            pass

    def handle_head(self, **options):
        action = options["action"]
        verbosity = options["verbosity"]
        filename = options["filename"]
        fd = None
        if filename:
            fd = io.StringIO()
            self.stdout = OutputWrapper(fd)
            self.style = no_style()

        if action == "python":
            self.show_python_config(verbosity)
        elif action == "ini":
            self.show_ini_config(verbosity)
        elif action == "env":
            self.show_env_config(verbosity)

        if filename and action in {"python", "env"}:
            content = fd.getvalue()
            # noinspection PyBroadException
            if action == "python":
                try:
                    # noinspection PyPackageRequirements,PyUnresolvedReferences
                    import black

                    mode = black.FileMode()
                    # noinspection PyArgumentList
                    content = black.format_file_contents(content, fast=False, mode=mode)
                except Exception:
                    pass
            with open(filename, "w") as dst_fd:
                dst_fd.write(content)

    def show_external_config(self, config):
        content = render_to_string(config, merger.settings)
        self.stdout.write(content)

    def show_ini_config(self, verbosity):
        if verbosity >= 2:
            self.stdout.write(self.style.SUCCESS("# read configuration files:"))
        for provider in merger.providers:
            if not isinstance(provider, IniConfigProvider):
                continue
            elif provider.is_valid():
                self.stdout.write(
                    self.style.SUCCESS('    #  - %s "%s"' % (provider.name, provider))
                )
            elif verbosity >= 2:
                self.stdout.write(
                    self.style.ERROR(
                        '    #  - %s "%s" (not found)' % (provider.name, provider)
                    )
                )
        provider = IniConfigProvider()
        merger.write_provider(provider, include_doc=verbosity >= 2)
        self.stdout.write(provider.to_str())

    def show_env_config(self, verbosity):
        prefix = None
        for provider in merger.providers:
            if not isinstance(provider, EnvironmentConfigProvider):
                continue
            prefix = provider.prefix
        if not prefix:
            self.stderr.write("Environment variables are not used•")
            return
        if verbosity >= 2:
            self.stdout.write(self.style.SUCCESS("# read environment variables:"))
        provider = EnvironmentConfigProvider(prefix)
        merger.write_provider(provider, include_doc=verbosity >= 2)
        self.stdout.write(provider.to_str())

    def show_python_config(self, verbosity):
        self.stdout.write(self.style.SUCCESS("# " + "-" * 80))
        self.stdout.write(
            self.style.SUCCESS(
                _("# df_config version %(version)s") % {"version": version}
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                _("# %(project)s version %(version)s")
                % {
                    "version": guess_version(merger.settings),
                    "project": merger.settings["DF_PROJECT_NAME"],
                }
            )
        )
        self.stdout.write(self.style.SUCCESS("# Configuration providers:"))
        for provider in merger.providers:
            if provider.is_valid():
                self.stdout.write(
                    self.style.SUCCESS('#  - %s "%s"' % (provider.name, provider))
                )
            elif verbosity > 1:
                self.stdout.write(
                    self.style.ERROR(
                        '#  - %s "%s" (not found)' % (provider.name, provider)
                    )
                )
        self.stdout.write(self.style.SUCCESS("# " + "-" * 80))
        setting_names = list(merger.raw_settings)
        setting_names.sort()

        # first, compute all imports to do
        imports = {}

        def add_import(val):
            if not isinstance(val, type):
                val = val.__class__
            if val.__module__ != "builtins":
                imports.setdefault(val.__module__, set()).add(val.__name__)

        for setting_name in setting_names:
            if setting_name not in merger.settings:
                continue
            value = merger.settings[setting_name]
            add_import(value)
        if imports:
            self.stdout.write("\n")
            for module_name in sorted(imports):
                objects = ", ".join(sorted(imports[module_name]))
                self.stdout.write(
                    self.style.WARNING("from %s import %s" % (module_name, objects))
                )
            self.stdout.write("\n")

        for setting_name in setting_names:
            if setting_name not in merger.settings:
                continue
            value = merger.settings[setting_name]
            self.stdout.write(self.style.SUCCESS("%s = %r" % (setting_name, value)))
            if verbosity <= 1:
                continue
            for provider_name, raw_value in merger.raw_settings[setting_name].items():
                self.stdout.write(
                    self.style.WARNING(
                        "    #   %s -> %r" % (provider_name or "built-in", raw_value)
                    )
                )
