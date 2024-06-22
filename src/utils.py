"""Common helper functions for the project."""
import random
import string
from datetime import datetime
from urllib.parse import urlparse
from enum import Enum, auto

import boto3


####################################################################################################
# COMMON HELPER FUNCTIONS
####################################################################################################
def random_string(length: int = 6) -> str:
    """Generate a random string of fixed length"""
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))


def random_color() -> str:
    """Generate a random color"""
    r = lambda: random.randint(0, 255)
    return "#%02X%02X%02X" % (r(), r(), r())


def ts2date(ts):
    """Convert timestamp to date"""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def download_file(url: str, file_path: str):
    """Download a file from a url to a local path"""
    try:
        s3 = boto3.client("s3")
        parsed_url = urlparse(url)
        bucket = parsed_url.netloc.split(".")[0]
        key = parsed_url.path[1:]
        s3.download_file(bucket, key, file_path)
        return {"success": True, "message": "File downloaded"}
    except Exception as e:
        return {
            "success": False,
            "message": f"{str(e)} \n{bucket} \n{key} \n{file_path}",
        }


def upload_file(file_path: str, url: str):
    """Upload a file from a local path to a url"""
    try:
        s3 = boto3.client("s3")
        parsed_url = urlparse(url)
        bucket = parsed_url.netloc.split(".")[0]
        key = parsed_url.path[1:]
        s3.upload_file(file_path, bucket, key, ExtraArgs={"ACL": "public-read"})
        return {"success": True, "message": "File uploaded"}
    except Exception as e:
        return {
            "success": False,
            "message": f"{str(e)} \n{bucket} \n{key} \n{file_path}",
        }

####################################################################################################
class RequestType(Enum):
    """Request types"""

    GET = auto()
    PUT = auto()
    POST = auto()
    DELETE = auto()

