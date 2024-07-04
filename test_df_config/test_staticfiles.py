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
import unittest

from df_config.guesses.staticfiles import (
    media_storage_setting,
    minio_storage_access_key,
    minio_storage_endpoint,
    minio_storage_secret_key,
    minio_storage_static_bucket_name,
    minio_storage_use_https,
    static_storage_setting,
)


class TestStaticFiles(unittest.TestCase):
    def test_static_storage_setting_wn(self):
        self.assertEqual(
            {
                "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
                "OPTIONS": {"base_url": "/static", "location": "/data/static"},
            },
            static_storage_setting(
                {
                    "DEBUG": False,
                    "PIPELINE_ENABLED": False,
                    "USE_WHITENOISE": True,
                    "STATIC_ROOT": "/data/static",
                    "STATIC_URL": "/static",
                    "USE_PIPELINE": True,
                }
            ),
        )

    def test_static_storage_setting_pp(self):
        self.assertEqual(
            {
                "BACKEND": "df_config.apps.pipeline.NicerPipelineCachedStorage",
                "OPTIONS": {"base_url": "/static", "location": "/data/static"},
            },
            static_storage_setting(
                {
                    "DEBUG": False,
                    "PIPELINE_ENABLED": True,
                    "USE_WHITENOISE": False,
                    "STATIC_ROOT": "/data/static",
                    "STATIC_URL": "/static",
                    "USE_PIPELINE": True,
                }
            ),
        )

    def test_static_storage_setting_s3(self):
        self.assertEqual(
            {
                "BACKEND": "minio_storage.storage.MinioStaticStorage",
                "OPTIONS": {},
            },
            static_storage_setting(
                {
                    "DEBUG": False,
                    "PIPELINE_ENABLED": True,
                    "USE_WHITENOISE": False,
                    "STATIC_ROOT": "s3:https://access_key:secret_key@s3.rbx.io.cloud.ovh.net/bucket_name",
                    "STATIC_URL": "/static",
                    "USE_PIPELINE": True,
                }
            ),
        )

    def test_media_storage_setting_s3(self):
        self.assertEqual(
            {
                "BACKEND": "minio_storage.storage.MinioMediaStorage",
                "OPTIONS": {},
            },
            media_storage_setting(
                {
                    "MEDIA_ROOT": "s3:https://access_key:secret_key@s3.rbx.io.cloud.ovh.net/bucket_name",
                    "MEDIA_URL": "/media",
                }
            ),
        )

    def test_static_storage_settings_s3(self):
        self.assertEqual(
            "bucket_name",
            minio_storage_static_bucket_name(
                {
                    "STATIC_ROOT": "s3:https://access_key:secret_key@s3.rbx.io.cloud.ovh.net/bucket_name",
                }
            ),
        )

        self.assertEqual(
            "secret_key",
            minio_storage_secret_key(
                {
                    "MEDIA_ROOT": "s3:https://access_key:secret_key@s3.rbx.io.cloud.ovh.net/media",
                    "STATIC_ROOT": "s3:https://access_key:secret_key@s3.rbx.io.cloud.ovh.net/static",
                }
            ),
        )
        self.assertEqual(
            "access_key",
            minio_storage_access_key(
                {
                    "MEDIA_ROOT": "s3:https://access_key:secret_key@s3.rbx.io.cloud.ovh.net/media",
                    "STATIC_ROOT": "s3:https://access_key:secret_key@s3.rbx.io.cloud.ovh.net/static",
                }
            ),
        )
        self.assertEqual(
            "s3.rbx.io.cloud.ovh.net:443",
            minio_storage_endpoint(
                {
                    "MEDIA_ROOT": "s3:https://access_key:secret_key@s3.rbx.io.cloud.ovh.net/media",
                    "STATIC_ROOT": "s3:https://access_key:secret_key@s3.rbx.io.cloud.ovh.net/static",
                }
            ),
        )
        self.assertTrue(
            minio_storage_use_https(
                {
                    "MEDIA_ROOT": "s3:https://access_key:secret_key@s3.rbx.io.cloud.ovh.net/media",
                    "STATIC_ROOT": "s3:https://access_key:secret_key@s3.rbx.io.cloud.ovh.net/static",
                }
            ),
        )
