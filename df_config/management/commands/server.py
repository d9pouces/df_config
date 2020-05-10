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
"""
universal server command

use gunicorn, uvicorn or daphne, depending on the selected options
"""
import sys

from django.conf import settings
from django.core.management import BaseCommand

from df_config.utils import is_package_present


class Command(BaseCommand):
    help = "Launch the server process"

    @property
    def listen_port(self):
        add, sep, port = settings.LISTEN_ADDRESS.partition(":")
        return int(port)

    @property
    def listen_address(self):
        add, sep, port = settings.LISTEN_ADDRESS.partition(":")
        return add

    def run_from_argv(self, argv):
        """
        Set up any environment changes requested (e.g., Python path
        and Django settings), then run this command. If the
        command raises a ``CommandError``, intercept it and print it sensibly
        to stderr. If the ``--traceback`` option is present or the raised
        ``Exception`` is not ``CommandError``, raise it.
        """
        if settings.DF_SERVER == "gunicorn":
            self.run_gunicorn()
        elif settings.DF_SERVER == "daphne":
            self.run_daphne()
        else:
            self.stderr.write(
                "unknown value '%s' for setting DF_SERVER. Please choose between 'daphne' and 'gunicorn'."
                % settings.DF_SERVER
            )
            return

    @staticmethod
    def get_application():
        if settings.USE_WEBSOCKETS:
            application = "df_websockets.routing:application"
        else:
            application = "df_config.application.asgi_application"
        return application

    def run_daphne(self):
        # noinspection PyPackageRequirements,PyUnresolvedReferences
        from daphne.cli import CommandLineInterface

        host, port = self.listen_address, self.listen_port
        app = self.get_application()

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

    def run_gunicorn(self):
        sys.argv.pop(0)
        # noinspection PyPackageRequirements,PyUnresolvedReferences
        from gunicorn.config import KNOWN_SETTINGS, Setting

        # noinspection PyPackageRequirements,PyUnresolvedReferences
        from gunicorn.app.wsgiapp import WSGIApplication

        application = self.get_application()
        if settings.USE_WEBSOCKETS:
            worker_cls = "uvicorn.workers.UvicornWorker"
            if not is_package_present("uvicorn.workers"):
                self.stderr.write(
                    "you must install uvicorn to use websockets with Gunicorn."
                )
                return
        else:
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
        pass
