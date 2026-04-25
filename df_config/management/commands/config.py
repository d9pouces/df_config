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
"""Display all the loaded settings and their origin. Can also produce a setting file."""
import io
import os
from argparse import ArgumentParser
from collections.abc import Iterable
from importlib.metadata import version as get_version
from typing import Any, Set

from django.core.management import BaseCommand
from django.core.management.base import OutputWrapper
from django.core.management.color import no_style
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from df_config.config.base import merger
from df_config.config.merger import SettingMerger
from df_config.config.values_providers import (
    EnvironmentConfigProvider,
    IniConfigProvider,
)
from df_config.utils import guess_version, remove_arguments_from_help

__author__ = "Matthieu Gallet"


class Command(BaseCommand):
    """Display all the loaded settings and their origin.

    This management command allows to inspect the current Django configuration
    and export it in different formats: Python module, .ini file or environment variables.
    Use the verbosity flag (-v 2) to display additional information such as
    configuration providers and their status.
    """

    help = (
        "show the current configuration."
        'Can display as python file ("config python") or as .ini file ("config ini"). Use -v 2 to display more info.'
    )
    requires_system_checks = []
    options = {
        "python": "display the current config as Python module",
        "ini": "display the current config as .ini file",
        "env": "display the current config as environment variables",
    }

    def add_arguments(self, parser: ArgumentParser):
        """Add the arguments to the ArgumentParser.

        Registers the following arguments:
        - ``action``: the output format, one of ``python``, ``ini`` or ``env``.
        - ``--filename``: optional path to write the output to a file instead of stdout.
        """
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
        """Entry point of the command.

        Delegates to :meth:`handle_head` and silently swallows
        :exc:`BrokenPipeError` so that the command works correctly when its
        output is piped to tools such as ``head``.
        """
        try:
            self.handle_head(**options)
        except BrokenPipeError:
            # this exception is raised when `manage.py config python | head` is used
            pass

    def handle_head(self, **options):
        """Handle the action, raising a BrokenPipeError when interrupted.

        Dispatches to the appropriate display method depending on the value of
        the ``action`` option (``python``, ``ini`` or ``env``).  When a
        ``--filename`` is provided the output is written to that file instead of
        stdout.  For the ``python`` action the output is optionally formatted
        with *black* when that package is available.
        """
        action = options["action"]
        verbosity = options["verbosity"]
        filename = options["filename"]
        fd = io.StringIO()
        if filename:
            self.stdout = OutputWrapper(fd)
            self.style = no_style()
        if action == "python":
            self.show_python_config(verbosity)
        elif action == "ini":
            self.show_ini_config(verbosity)
        elif action == "env":
            self.show_env_config(verbosity)

        if filename and action in {"python", "env"}:
            filename: str = os.path.abspath(filename)
            content = fd.getvalue()
            if action == "python":
                # noinspection PyBroadException
                try:
                    # noinspection PyPackageRequirements,PyUnresolvedReferences
                    import black

                    mode = black.FileMode()
                    # noinspection PyArgumentList
                    content = black.format_file_contents(content, fast=False, mode=mode)
                except Exception:  # nosec  # nosec
                    pass
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w") as dst_fd:
                dst_fd.write(content)

    def show_external_config(self, config):
        """Render settings using a Django template file.

        :param config: path or name of the Django template to render.  The
            template receives the current merged settings dictionary as its
            context.
        """
        content = render_to_string(config, merger.settings)
        self.stdout.write(content)

    def show_ini_config(self, verbosity):
        """Display the current configuration as a ``.ini`` file.

        Lists the active :class:`~df_config.config.values_providers.IniConfigProvider`
        instances and serialises the current settings into the ini format.
        When *verbosity* is 2 or higher, the fields provider and all
        configuration file paths (including missing ones) are shown.

        :param verbosity: integer verbosity level coming from the ``-v`` flag.
        """
        if verbosity >= 2:
            p = merger.fields_provider
            self.stdout.write(
                self.style.SUCCESS(f"# configuration fields read from {p}")
            )
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
        """Display the current configuration as shell environment variables.

        Looks for an :class:`~df_config.config.values_providers.EnvironmentConfigProvider`
        in the active providers to retrieve the variable prefix, then serialises
        every setting as ``PREFIX_SETTING_NAME=value`` lines.
        When *verbosity* is 2 or higher the fields provider and the variable
        names are printed as comments.

        :param verbosity: integer verbosity level coming from the ``-v`` flag.
        """
        prefix = None
        for provider in merger.providers:
            if not isinstance(provider, EnvironmentConfigProvider):
                continue
            prefix = provider.prefix
        if not prefix:
            self.stderr.write("Environment variables are not used•")
            return
        if verbosity >= 2:
            p = merger.fields_provider
            self.stdout.write(
                self.style.SUCCESS(f"# configuration fields read from {p}")
            )
            self.stdout.write(self.style.SUCCESS("# read environment variables:"))
        provider = EnvironmentConfigProvider(prefix)
        merger.write_provider(provider, include_doc=verbosity >= 2)
        self.stdout.write(provider.to_str())

    def show_python_config(self, verbosity):
        """Display the current configuration as a Python settings module.

        Outputs a ready-to-use Python file that reproduces the fully-merged
        configuration.  The file starts with a header containing the
        df_config version, the project version and the list of active
        configuration providers.  All required ``from … import …`` statements
        are automatically computed and emitted before the setting assignments.
        When *verbosity* is greater than 1, the per-provider raw values are
        shown as inline comments next to each setting.

        :param verbosity: integer verbosity level coming from the ``-v`` flag.
        """
        version = get_version("df_config")
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
                    "project": merger.settings.get("DF_PROJECT_NAME", "project"),
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
        imports = self.get_raw_imports(setting_names)

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
            value = SettingMerger.unwrap_object(merger.settings[setting_name])
            self.stdout.write(self.style.SUCCESS("%s = %r" % (setting_name, value)))
            if verbosity <= 1:
                continue
            for p_name, r_value in merger.raw_settings[setting_name].items():
                self.stdout.write(
                    self.style.WARNING(
                        "    #   %s -> %r"
                        % (p_name or "built-in", SettingMerger.unwrap_object(r_value))
                    )
                )

    def get_raw_imports(self, setting_names: list[Any]) -> dict[Any, Any]:
        """Compute the ``import`` statements required by the current settings.

        Iterates over *setting_names*, inspects the type of each setting value
        (including nested structures such as dicts and iterables) and collects
        the module/class pairs that must be imported so that the generated
        Python file is self-contained.

        :param setting_names: ordered list of setting names to inspect.
        :returns: a mapping ``{module_name: {class_name, …}}`` that can be
            used to generate ``from module_name import class_name`` lines.
        """
        imports = {}
        for setting_name in setting_names:
            if setting_name not in merger.settings:
                continue
            value = merger.settings[setting_name]
            self._recursive_add_import(setting_name, value, imports)
        return imports

    # noinspection PyUnusedLocal
    @staticmethod
    def _add_import(name, val, imports):
        """Register a single value's type in the *imports* mapping.

        If *val* is not already a type, its class is used.  Built-in types
        (whose ``__module__`` is ``"builtins"``) are silently ignored.

        :param name: setting name – kept for signature consistency but not used
            directly.
        :param val: the value whose type must be imported.
        :param imports: mutable mapping ``{module: {class_name, …}}`` that is
            updated in-place.
        """
        if not isinstance(val, type):
            val = val.__class__
        if val.__module__ != "builtins":
            imports.setdefault(val.__module__, set()).add(val.__name__)

    def _recursive_add_import(self, name: str, value, imports: dict[str, Set[str]]):
        """Recursively collect import requirements for a setting value.

        Unwraps *value* and delegates to :meth:`_add_import` for the top-level
        object.  For dicts, both keys and values are traversed recursively.
        For other iterables (excluding strings and bytes), each element is
        traversed recursively.

        :param name: setting name used for context.
        :param value: setting value to inspect (may be wrapped).
        :param imports: mutable mapping ``{module: {class_name, …}}`` updated
            in-place.
        """
        unwrapped = SettingMerger.unwrap_object(value)
        self._add_import(name, unwrapped, imports)
        if isinstance(unwrapped, dict):
            for key, elem in unwrapped.items():
                self._add_import(name, SettingMerger.unwrap_object(key), imports)
                self._recursive_add_import(name, elem, imports)
        elif isinstance(unwrapped, Iterable) and not isinstance(
            unwrapped, (str, bytes)
        ):
            for elem in unwrapped:
                self._recursive_add_import(name, elem, imports)
