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
"""Provide utility functions for static and media files."""
import urllib.parse
from importlib.util import find_spec
from typing import Dict, Optional, Union

from django.core.exceptions import ImproperlyConfigured


def static_storage(settings_dict):
    """Guess the best static files storage engine."""
    use_pipeline = settings_dict["PIPELINE_ENABLED"] and settings_dict["USE_PIPELINE"]
    if settings_dict["USE_WHITENOISE"] and use_pipeline:
        return "df_config.apps.pipeline.PipelineCompressedManifestStaticFilesStorage"
    elif settings_dict["USE_WHITENOISE"]:
        return "whitenoise.storage.CompressedManifestStaticFilesStorage"
    elif use_pipeline:
        return "df_config.apps.pipeline.NicerPipelineCachedStorage"
    return "django.contrib.staticfiles.storage.StaticFilesStorage"


static_storage.required_settings = [
    "PIPELINE_ENABLED",
    "USE_WHITENOISE",
    "USE_PIPELINE",
]


def static_storage_setting(settings_dict):
    """Guess the right static file storage engine."""
    static_root = settings_dict["STATIC_ROOT"]
    options = {"base_url": settings_dict["STATIC_URL"]}
    use_pipeline = settings_dict["PIPELINE_ENABLED"] and settings_dict["USE_PIPELINE"]
    if static_root.startswith("s3:"):
        if find_spec("minio_storage") is None:
            raise ImproperlyConfigured("please install django-minio-storage.")
        backend = "minio_storage.storage.MinioStaticStorage"
        options = {}
    elif settings_dict["USE_WHITENOISE"] and use_pipeline:
        options["location"] = static_root
        backend = "df_config.apps.pipeline.PipelineCompressedManifestStaticFilesStorage"
    elif settings_dict["USE_WHITENOISE"]:
        options["location"] = static_root
        backend = "whitenoise.storage.CompressedManifestStaticFilesStorage"
    elif use_pipeline:
        options["location"] = static_root
        backend = "df_config.apps.pipeline.NicerPipelineCachedStorage"
    else:
        options["location"] = static_root
        backend = "django.contrib.staticfiles.storage.StaticFilesStorage"
    return {"BACKEND": backend, "OPTIONS": options}


static_storage_setting.required_settings = [
    "DEBUG",
    "PIPELINE_ENABLED",
    "USE_WHITENOISE",
    "STATIC_ROOT",
    "STATIC_URL",
    "USE_PIPELINE",
]


def parse_s3_url(
    url: str, url_2: Optional[str] = None
) -> Dict[str, Union[Optional[str], bool]]:
    """Extract all S3 data from the given URL."""
    if url.startswith("s3:"):
        parsed_url = urllib.parse.urlparse(url[3:])
    elif url_2 is not None and url_2.startswith("s3:"):
        parsed_url = urllib.parse.urlparse(url_2[3:])
    else:
        return {
            "endpoint": None,
            "access_key": None,
            "secret_key": None,
            "use_https": False,
            "bucket_name": None,
        }
    if parsed_url.scheme not in ("http", "https"):
        raise ImproperlyConfigured(
            f"Invalid scheme provided {parsed_url.scheme} in s3 URL {url}."
        )
    port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
    return {
        "endpoint": f"{parsed_url.hostname}:{port}",
        "access_key": parsed_url.username,
        "secret_key": parsed_url.password,
        "use_https": parsed_url.scheme == "https",
        "bucket_name": parsed_url.path[1:],
    }


def media_storage_setting(settings_dict):
    """Guess the best media storage engine."""
    media_root = settings_dict["MEDIA_ROOT"]
    options = {"base_url": settings_dict["MEDIA_URL"]}
    if media_root.startswith("s3:"):
        if find_spec("minio_storage") is None:
            raise ImproperlyConfigured("please install django-minio-storage.")
        backend = "minio_storage.storage.MinioMediaStorage"
        options = {}
    else:
        options["location"] = media_root
        backend = "django.core.files.storage.FileSystemStorage"
    return {"BACKEND": backend, "OPTIONS": options}


media_storage_setting.required_settings = ["MEDIA_ROOT", "MEDIA_URL"]


def pipeline_enabled(settings_dict):
    """Guess if django-pipeline is enabled."""
    return settings_dict["USE_PIPELINE"] and not settings_dict["DEBUG"]


pipeline_enabled.required_settings = ["DEBUG", "USE_PIPELINE"]


def static_finder(settings_dict):
    """Provide static files finders, using pipeline when available."""
    r = [
        "django.contrib.staticfiles.finders.FileSystemFinder",
        "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    ]
    if settings_dict["USE_PIPELINE"]:
        r.append("pipeline.finders.PipelineFinder")
    return r


static_finder.required_settings = ["DEBUG", "USE_PIPELINE"]


def minio_storage_endpoint(settings_dict) -> Optional[str]:
    """Provide the end point from the MEDIA_ROOT or STATIC_ROOT setting."""
    media_root = settings_dict["MEDIA_ROOT"]
    static_root = settings_dict["STATIC_ROOT"]
    data = parse_s3_url(media_root, static_root)
    return data["endpoint"]


minio_storage_endpoint.required_settings = ["MEDIA_ROOT", "STATIC_ROOT"]


def minio_storage_use_https(settings_dict) -> bool:
    """Guess if the S3 endpoint use HTTPS."""
    media_root = settings_dict["MEDIA_ROOT"]
    static_root = settings_dict["STATIC_ROOT"]
    data = parse_s3_url(media_root, static_root)
    return data["use_https"]


minio_storage_use_https.required_settings = ["MEDIA_ROOT", "STATIC_ROOT"]


def minio_storage_access_key(settings_dict) -> Optional[str]:
    """Provide the access key from the MEDIA_ROOT or STATIC_ROOT setting."""
    media_root = settings_dict["MEDIA_ROOT"]
    static_root = settings_dict["STATIC_ROOT"]
    data = parse_s3_url(media_root, static_root)
    return data["access_key"]


minio_storage_access_key.required_settings = ["MEDIA_ROOT", "STATIC_ROOT"]


def minio_storage_secret_key(settings_dict) -> Optional[str]:
    """Provide the secret key from the MEDIA_ROOT or STATIC_ROOT setting."""
    media_root = settings_dict["MEDIA_ROOT"]
    static_root = settings_dict["STATIC_ROOT"]
    data = parse_s3_url(media_root, static_root)
    return data["secret_key"]


minio_storage_secret_key.required_settings = ["MEDIA_ROOT", "STATIC_ROOT"]


def minio_storage_media_bucket_name(settings_dict) -> Optional[str]:
    """Provide the static bucket name from the MEDIA_ROOT setting."""
    data = parse_s3_url(settings_dict["MEDIA_ROOT"])
    return data["bucket_name"]


minio_storage_media_bucket_name.required_settings = ["MEDIA_ROOT"]


def minio_storage_static_bucket_name(settings_dict) -> Optional[str]:
    """Provide the static bucket name from the STATIC_ROOT setting."""
    data = parse_s3_url(settings_dict["STATIC_ROOT"])
    return data["bucket_name"]


minio_storage_static_bucket_name.required_settings = ["STATIC_ROOT"]
