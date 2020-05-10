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
import os
import tempfile
from unittest import TestCase

from df_config.utils import ensure_dir, is_package_present


class TestIsPackagePresent(TestCase):
    def test_is_package_present(self):
        self.assertTrue(is_package_present("df_config"))
        self.assertFalse(is_package_present("flask"))


class TestEnsureDir(TestCase):
    def test_ensure_dir(self):
        with tempfile.TemporaryDirectory() as dirname:
            ensure_dir("%s/parent1/dirname" % dirname, parent=False)
            self.assertTrue(os.path.isdir("%s/parent1/dirname" % dirname))
            ensure_dir("%s/parent1/dirname" % dirname)
            self.assertTrue(os.path.isdir("%s/parent1/dirname" % dirname))
            ensure_dir("%s/parent2/filename" % dirname, parent=True)
            self.assertTrue(os.path.isdir("%s/parent2" % dirname))
            self.assertFalse(os.path.isdir("%s/parent2/filename" % dirname))
