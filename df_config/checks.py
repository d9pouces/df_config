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
        cmd = f"Try 'python -m pip install {package_name}' to install it."
    elif __file__.startswith(os.environ.get("HOME", "/home")):
        cmd = f"Try 'python3 -m pip install --user {package_name}' to install it."
    else:
        cmd = f"Try 'sudo python3 -m pip install {package_name}' to install it."
    return Warning(
        f"Python package '{package_name}' is required{desc}. {cmd}",
        obj="configuration",
    )
