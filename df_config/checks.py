# ##############################################################################
#  This file is part of Interdiode                                             #
#                                                                              #
#  Copyright (C) 2020 Matthieu Gallet <matthieu.gallet@19pouces.net>           #
#  All Rights Reserved                                                         #
#                                                                              #
# ##############################################################################
"""Check installed modules and settings to provide lists of middlewares/installed apps."""
import os
import sys

from django.core.checks import Warning

settings_check_results = []


def missing_package(package_name, desc=""):
    """Return a warning if a Python package is missing."""
    if hasattr(sys, "real_prefix"):  # inside a virtualenv
        cmd = f"Try 'python -m pip install {package_name}' to install it."
    elif __file__.startswith(os.environ.get("HOME", "/home")):
        cmd = f"Try 'python3 -m pip install --user {package_name}' to install it."
    else:
        cmd = f"Try 'sudo python3 -m pip install {package_name}' to install it."
    return Warning(
        f"Python package '{package_name}' is required{desc}.",
        obj="configuration",
        hint=cmd,
        id="df_config.W001",
    )
