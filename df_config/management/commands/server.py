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
"""Universal server command.

use gunicorn, uvicorn or daphne, depending on the selected options
"""
import sys

from django.conf import settings
from django.core.management import BaseCommand

from df_config.utils import is_package_present


class Command(BaseCommand):
    """Launch the server command."""

    help = "Launch the server process"

    @property
    def listen_port(self):
        """Return the listen port."""
        add, sep, port = settings.LISTEN_ADDRESS.partition(":")
        return int(port)

    @property
    def listen_address(self):
        """Return the listen address."""
        add, sep, port = settings.LISTEN_ADDRESS.partition(":")
        return add

    def run_from_argv(self, argv):
        """Set up any environment changes requested (e.g., Python path and Django settings), then run this command.

        If the command raises a ``CommandError``, intercept it and print it sensibly
        to stderr. If the ``--traceback`` option is present or the raised
        ``Exception`` is not ``CommandError``, raise it.
        """
        if settings.DF_SERVER == "gunicorn":
            self.run_gunicorn()
        elif settings.DF_SERVER == "daphne":
            self.run_daphne()
        elif settings.DF_SERVER == "uvicorn":
            self.run_daphne()
        else:
            self.stderr.write(
                f"unknown value '{settings.DF_SERVER}' for setting DF_SERVER. "
                f"Valid choices are 'daphne', 'gunicorn' and 'uvicorn'."
            )
            return

    @staticmethod
    def get_wsgi_application():
        """Return the WSGI app."""
        mod_name, sep, attr_name = settings.WSGI_APPLICATION.rpartition(".")
        return "%s:%s" % (mod_name, attr_name)

    @staticmethod
    def get_asgi_application():
        """Return the ASGI app (required when using websockets)."""
        mod_name, sep, attr_name = settings.ASGI_APPLICATION.rpartition(".")
        return "%s:%s" % (mod_name, attr_name)

    def run_daphne(self):
        """Run the server using Daphne."""
        try:
            from daphne.cli import CommandLineInterface
        except ImportError:
            self.stderr.write("Unable to start: please install daphne first.")
            return

        host, port = self.listen_address, self.listen_port
        app = self.get_asgi_application()

        class CLI(CommandLineInterface):
            def __init__(self):
                super().__init__()
                # noinspection PyProtectedMember
                for action in self.parser._actions:
                    if action.dest == "port":
                        action.default = port
                    elif action.dest == "host":
                        action.default = host
                    elif action.dest == "application":
                        action.default = app
                        action.required = False

        return CLI().run(sys.argv[2:])

    def run_uvicorn(self):
        """Run the server using uvicorn."""
        import uvicorn

        app = self.get_asgi_application()
        return uvicorn.run(
            app, host=self.listen_address, port=self.listen_port, log_level="info"
        )

    def run_gunicorn(self):
        """Run the server using gunicorn."""
        sys.argv.pop(0)
        try:
            # noinspection PyPackageRequirements
            from gunicorn.config import KNOWN_SETTINGS, Setting
        except ImportError:
            self.stderr.write("Unable to start: please install gunicorn first.")
            return
        from gunicorn.app.wsgiapp import WSGIApplication

        if settings.USE_WEBSOCKETS:
            application = self.get_asgi_application()
            worker_cls = "uvicorn_worker.UvicornWorker"
            if not is_package_present("uvicorn_worker"):
                self.stderr.write(
                    "you must install uvicorn-worker to use websockets with Gunicorn."
                )
                worker_cls = "uvicorn.workers.UvicornWorker"
                if not is_package_present("uvicorn.workers"):
                    self.stderr.write(
                        "you must install uvicorn-worker to use websockets with Gunicorn."
                    )
                    return
        else:
            application = self.get_wsgi_application()
            worker_cls = "gunicorn.workers.gthread.ThreadWorker"

        class Application(WSGIApplication):
            def init(self, parser, opts, args):
                if not args:
                    args.append(application)
                super().init(parser, opts, args)

        for setting in KNOWN_SETTINGS:  # type: Setting
            if setting.name == "bind":
                setting.default = settings.LISTEN_ADDRESS
            elif setting.name == "worker_class":
                setting.default = worker_cls

        return Application("%(prog)s [OPTIONS] [APP_MODULE]").run()

    def handle(self, *args, **options):
        """Override the default function."""
        pass
