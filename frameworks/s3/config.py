# -*- coding: utf-8 -*-
import os
from os.path import join

from pydantic import BaseModel, Field, model_validator
import json
from pathlib import Path

class Config(BaseModel):
    """
    Configuration class for storing cloud storage access parameters.

    :param bucket_name: Name of the S3 bucket.
    :param region: AWS region where the S3 bucket is hosted.
    :param download_dir: Directory for downloaded files; defaults to the current project directory if empty.
    """
    bucket_name: str = Field(..., description="S3-basket name")
    region: str = Field(..., description="Region of resource location")
    download_dir: str = Field("", description="Directory to store downloaded files")

    @model_validator(mode="before")
    @classmethod
    def set_default_download_dir(cls, values):
        """
        If 'download_dir' is an empty string or not provided, set it to the current project directory.
        """
        if not values.get("download_dir"):
            values["download_dir"] = str(Path.cwd() / 'downloads')
        return values

    @classmethod
    def load_from_file(cls, path: str | Path = None) -> "Config":
        """
        Load configuration from a JSON file.

        :param path: Path to the JSON config file.
        :return: An instance of the Config class.

        :raises FileNotFoundError: If the file does not exist.
        :raises json.JSONDecodeError: If the file is not valid JSON.
        :raises pydantic.ValidationError: If the data is invalid.
        """
        with open(path or join(os.getcwd(), 's3_config.json'), "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
