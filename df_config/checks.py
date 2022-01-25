# ##############################################################################
#  This file is part of Interdiode                                             #
#                                                                              #
#  Copyright (C) 2020 Matthieu Gallet <matthieu.gallet@19pouces.net>           #
#  All Rights Reserved                                                         #
#                                                                              #
# ##############################################################################
import os
import sys

from django.core.checks import Warning

settings_check_results = []


def missing_package(package_name, desc=""):
    if hasattr(sys, "real_prefix"):  # inside a virtualenv
        cmd = "Try 'python -m pip install %s' to install it." % package_name
    elif __file__.startswith(os.environ.get("HOME", "/home")):
        cmd = "Try 'python3 -m pip install --user %s' to install it." % package_name
    else:
        cmd = "Try 'sudo python3 -m pip install %s' to install it." % package_name
    return Warning(
        "Python package '%s' is required%s. %s" % (package_name, desc, cmd),
        obj="configuration",
    )



