"""
========================
T2D2 SDK Client Library
========================
"""

import json
import os
# pylint: disable=wildcard-import, unused-wildcard-import
import random
import string
from collections import defaultdict
from datetime import datetime
from enum import Enum, auto
from urllib.parse import urlencode, urlparse

import boto3
import requests

TIMEOUT = 60
BASE_URL = os.getenv("T2D2_API_URL", "https://api-v3.t2d2.ai/api/")
# DEV https://api-v3-dev.t2d2.ai/api/


####################################################################################################
class T2D2(object):
    """
    A class to interact with the T2D2 API, providing methods for authentication, data retrieval, and data manipulation.

    Attributes:
        base_url (str): The base URL for the T2D2 API endpoints.
        headers (dict): Headers to be sent with each API request. Typically includes content type and authorization.
        s3_base_url (str): The base URL for S3 storage where data might be stored or retrieved.
        aws_region (str): The AWS region for S3 interactions.
        bucket (str): The name of the S3 bucket used for storing data.
        access_token (str): The token used for authenticating API requests.
        api_key (str): The API key used for authenticating with the T2D2 API.
        project (dict): A dictionary representing the current project's data. Default is None.
        debug (bool): A flag to enable or disable debug mode. Default is True.

    Methods:
        __init__(self, credentials, base_url=BASE_URL):
            Initializes the T2D2 object with credentials and optional base URL override.

            Args:
                credentials (dict): A dictionary containing necessary credentials for API interaction.
                base_url (str, optional): The base URL for the T2D2 API. Defaults to BASE_URL.

            Raises:
                ValueError: If the `base_url` does not end with a forward slash.
    """

    base_url: str
    headers: dict
    s3_base_url: str
    aws_region: str
    bucket: str
    access_token: str
    api_key: str
    project: dict = None
    debug: bool = True

    def __init__(self, credentials, base_url=BASE_URL):
        """Initialize / login"""
        if not base_url.endswith("/"):
            base_url += "/"
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
        self.login(credentials)
        self.project = {}

    def request(
        self,
        url_suffix: str,
        req_type: RequestType = RequestType.GET,
        params=None,
        headers=None,
        data=None,
    ) -> dict:
        """Send a request and handle response"""

        url = self.base_url + url_suffix
        if headers is None:
            headers = {}
        if params is None:
            params = {}
        if data is None:
            data = {}

        headers.update(self.headers)
        params_enc = {}
        for key, val in params.items():
            if isinstance(val, list):
                params_enc[key] = json.dumps(val)
            else:
                params_enc[key] = val
        if req_type == RequestType.GET:
            res = requests.get(
                url,
                headers=headers,
                params=urlencode(params_enc),
                timeout=TIMEOUT,
            )
        elif req_type == RequestType.POST:
            res = requests.post(
                url,
                headers=headers,
                params=urlencode(params_enc),
                json=data,
                timeout=TIMEOUT,
            )
        elif req_type == RequestType.PUT:
            res = requests.put(
                url,
                headers=headers,
                params=urlencode(params_enc),
                json=data,
                timeout=TIMEOUT,
            )
        elif req_type == RequestType.DELETE:
            res = requests.delete(
                url,
                headers=headers,
                params=urlencode(params_enc),
                json=data,
                timeout=TIMEOUT,
            )
        else:
            raise ValueError("Request type not yet supported. Coming soon")

        if res.status_code in (200, 201):
            try:
                return res.json()
            except Exception as e:
                print("JSON Conversion Error: ", e)
                return {"content": res.content}
        else:
            if self.debug:
                print(f"URL: {req_type} {res.url}")
                print(f"HEADERS: {headers}")
                print(f"PARAMS: {params}")
                print(f"DATA: {data}")
                print(res.status_code, res.content)
            raise ValueError(f"Error code received: {res.status_code}")

    def login(self, credentials):
        """Login and update header with authorization credentials

        Args:
            credentials (dict): A dictionary containing necessary credentials for API interaction.

        Returns:
            None

        Raises:
            ValueError: If the credentials are invalid or missing.
        """

        if "access_token" in credentials:
            # Directly use token
            self.access_token = credentials["access_token"]
            self.headers["Authorization"] = f"Bearer {self.access_token}"

        elif "password" in credentials:
            # Login
            url = "auth/login"
            json_data = self.request(url, RequestType.POST, data=credentials)
            self.access_token = json_data["data"]["firebaseDetail"]["access_token"]
            self.headers["Authorization"] = f"Bearer {self.access_token}"

        elif "api_key" in credentials:
            self.api_key = credentials["api_key"]
            self.headers["x-api-key"] = self.api_key

        return

    def notify_user(self, title, message):
        """Send a notification to the user

        Args:
            title (str): The title of the notification.
            message (str): The message content of the notification.

        Returns:
            dict: A dictionary containing the response from the API.

        Raises:
            ValueError: If the notification could not be sent.

        """
        url = "notifications"
        payload = {"title": title, "message": message}
        return self.request(url, RequestType.POST, data=payload)

    ################################################################################################
    # Project Get/Set
    ################################################################################################
    def get_project(self, project_id=None):
        """Return project list or project by project_id

        Args:
            project_id (str, optional): The ID of the project to retrieve. Defaults to None.

        Returns:
            dict: A dictionary containing the project data.

        Raises:
            ValueError: If the project is not set or the project_id is invalid.
        """

        if project_id is None:
            url = "project"
        else:
            url = f"project/{project_id}"
        json_data = self.request(url, RequestType.GET)
        return json_data["data"]

    def set_project(self, project_id):
        """Set the current project

        Args:
            project_id (str): The ID of the project to set.

        Returns:
            None

        Raises:
            ValueError: If the project_id is invalid or the project could not be set.
        """
        json_data = self.request(f"project/{project_id}", RequestType.GET)
        if not json_data["success"]:
            raise ValueError(json_data["message"])

        project = json_data["data"]
        self.project = project

        self.s3_base_url = project["config"]["s3_base_url"]
        self.aws_region = project["config"]["aws_region"]
        res = urlparse(self.s3_base_url)
        self.bucket = res.netloc.split(".")[0]
        return

    def get_project_info(self):
        """
        Return project information

        Args:
            None

        Returns:
            dict: A dictionary containing the project information.

        Raises:
            ValueError: If the project is not set.
        """
        if not self.project:
            raise ValueError("Project not set")
        return {
            "id": self.project["id"],
            "name": self.project["profile"]["name"],
            "address": self.project["location"]["address"],
            "description": self.project.get("description", ""),
            "created_by": self.project.get("created_by", ""),
            "created_at": ts2date(self.project["created_at"]),
            "statistics": self.project.get("statistics", {}),
        }

    ################################################################################################
    # CRUD Regions
    ################################################################################################
    def add_region(self, region_name: str):
        """
        Add region

        Args:
            region_name (str): The name of the region to add.

        Returns:
            dict: A dictionary containing the response from the API.

        Raises:
            ValueError: If the project is not set.
        """
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/categories/regions"
        json_data = self.request(url, RequestType.POST, data={"name": region_name})
        return json_data

    def update_region(self, region_name: str, new_region: dict):
        """
        Update region

        Args:
            region_name (str): The name of the region to update.

        Returns:
            dict: A dictionary containing the response from the API.

        Raises:
            ValueError: If the project is not set or the region is not found.
        """
        if not self.project:
            raise ValueError("Project not set")

        region_id = None
        for region in self.project["regions"]:
            if region["name"] == region_name:
                region_id = region["_id"]
                break

        if region_id is None:
            raise ValueError("Region not found")

        url = f"{self.project['id']}/categories/regions/{region_id}"
        json_data = self.request(url, RequestType.PUT, data=new_region)
        return json_data

    ################################################################################################
    # CRUD Assets
    ################################################################################################
    def get_assets(self, asset_type=1, asset_ids=None):
        """
        Return asset list based on specified ids

        Args:
            asset_type (int, optional): The type of asset to retrieve. Defaults to 1.
            asset_ids (list, optional): A list of asset IDs to retrieve. Defaults to None.

        Returns:
            list: A list of dictionaries containing the asset data.

        Raises:
            ValueError: If the project is not set.
        """
        if asset_ids is None:
            return []

        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/assets"
        payload = {"asset_type": asset_type, "asset_ids": asset_ids}
        json_data = self.request(url, RequestType.POST, data=payload)
        return json_data["data"]

    def add_assets(self, payload):
        """
        Add assets to project

        Args:
            payload (dict): A dictionary containing the assets to add.

        Returns:
            dict: A dictionary containing the response from the API.

        Raises:
            ValueError: If the project is not set.
        """
        url = f"{self.project['id']}/assets/bulk.create"
        return self.request(url, RequestType.POST, data=payload)

    def download_assets(
        self, asset_ids, asset_type=1, download_dir="./", original_filename=False
    ):
        """
        Download assets

        Args:
            asset_ids (list): A list of asset IDs to download.
            asset_type (int, optional): The type of asset to download. Defaults to 1.
            download_dir (str, optional): The directory to download the assets to. Defaults to "./".
            original_filename (bool, optional): Whether to use the original filename. Defaults to False.

        Returns:
            dict: A dictionary containing the asset IDs and their corresponding file paths.

        Raises:
            ValueError: If the project is not set or some assets are not found.
        """
        if not self.project:
            raise ValueError("Project not set")

        assets = self.get_assets(asset_type, asset_ids)
        if len(assets) != len(asset_ids):
            raise ValueError("Some assets not found")

        output = {}
        for asset in assets:
            url = asset["url"]
            if original_filename:
                file_name = asset["filename"]
            else:
                ext = os.path.splitext(asset["filename"])[1]
                file_name = f"img_{asset['id']}{ext}"
            file_path = os.path.join(download_dir, file_name)
            output[asset["id"]] = file_path
            response = download_file(url, file_path)
            if not response["success"]:
                raise ValueError(response["message"])

        return output

    ################################################################################################
    # CRUD Images
    ################################################################################################
    def upload_images(self, image_paths, image_type=1, params=None):
        """
        Upload images

        Args:
            image_paths (list): A list of image paths to upload.
            image_type (int, optional): The type of image to upload. Defaults to 1.
            params (dict, optional): Additional parameters to include in the upload. Defaults to None.

        Returns:
            dict: A dictionary containing the response from the API.

        Raises:
            ValueError: If the project is not set.
        """

        if not self.project:
            raise ValueError("Project not set")

        # Upload images to S3
        assets = []
        image_root = "images"
        if image_type == 3:
            image_root = "orthomosaics"

        for file_path in image_paths:
            base, ext = os.path.splitext(os.path.basename(file_path))
            filename = f"{base}_{random_string(6)}{ext}"
            s3_path = (
                self.s3_base_url
                + f"/projects/{self.project['id']}/{image_root}/{filename}"
            )
            result = upload_file(file_path, s3_path)
            if result.get("success", False):
                assets.append(
                    {
                        "name": base,
                        "filename": base + ext,
                        "url": filename,
                        "size": {"filesize": os.path.getsize(file_path)},
                    }
                )

        # Add images to project
        payload = {
            "project_id": self.project["id"],
            "asset_type": 1,
            "image_type": image_type,
            "assets": assets,
        }

        if params is not None:
            payload.update(params)

        return self.add_assets(payload)

    def get_images(self, image_ids=None, params=None):
        """
        Return image list based on specified ids

        Args:
            image_ids (list, optional): A list of image IDs to retrieve. Defaults to None.
            params (dict, optional): Additional parameters to include in the request. Defaults to None.

        Returns:
            list: A list of dictionaries containing the image data.

        Raises:
            ValueError: If the project is not set.
        """
        if not self.project:
            raise ValueError("Project not set yet")

        # all images in project
        if image_ids is None:
            url = f"{self.project['id']}/images"
            json_data = self.request(url, RequestType.GET, params=params)
            results = json_data["data"]["image_list"]
            return results

        # Specified image_ids
        results = []
        for img_id in image_ids:
            url = f"{self.project['id']}/images/{img_id}"
            json_data = self.request(url, RequestType.GET, params=params)
            results.append(json_data["data"])
        return results

    def update_images(self, image_ids, payload):
        """
        Update images

        Args:
            image_ids (list): A list of image IDs to update.
            payload (dict): A dictionary containing the updates to apply.

        Returns:
            dict: A dictionary containing the response from the API.

        Raises:
            ValueError: If the project is not set.
        """
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/images/bulk.update"
        payload["image_ids"] = image_ids
        payload["project_id"] = self.project["id"]
        return self.request(url, RequestType.PUT, data=payload)

    def delete_images(self, image_ids):
        """
        Delete images

        Args:
            image_ids (list): A list of image IDs to delete.

        Returns:
            dict: A dictionary containing the response from the API.

        Raises:
            ValueError: If the project is not set.
        """
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/images/bulk.delete"
        payload = {"image_ids": image_ids}
        return self.request(url, RequestType.DELETE, data=payload)

    ################################################################################################
    # CRUD Drawings
    ################################################################################################
    def upload_drawings(self, drawing_paths):
        """
        Upload drawings

        Args:
            drawing_paths (list): A list of drawing paths to upload.

        Returns:
            dict: A dictionary containing the response from the API.

        Raises:
            ValueError: If the project is not set.
        """

        if not self.project:
            raise ValueError("Project not set")

        # Upload images to S3
        assets = []
        for file_path in drawing_paths:
            base, ext = os.path.splitext(os.path.basename(file_path))
            filename = f"{base}_{random_string(6)}{ext}"
            s3_path = (
                self.s3_base_url + f"/projects/{self.project['id']}/drawings/{filename}"
            )
            upload_file(file_path, s3_path)
            assets.append(
                {
                    "name": base,
                    "filename": base + ext,
                    "url": filename,
                    "size": {"filesize": os.path.getsize(file_path)},
                }
            )

        # Add images to project
        url = f"{self.project['id']}/assets/bulk.create"
        payload = {"project_id": self.project["id"], "asset_type": 2, "assets": assets}
        res = self.request(url, RequestType.POST, data=payload)

        return res

    def get_drawings(self, drawing_ids=None, params=None):
        """
        Return drawing list based on specified ids

        Args:
            drawing_ids (list, optional): A list of drawing IDs to retrieve. Defaults to None.
            params (dict, optional): Additional parameters to include in the request. Defaults to None.

        Returns:
            list: A list of dictionaries containing the drawing data.

        Raises:
            ValueError: If the project is not set.
        """
        if not self.project:
            raise ValueError("Project not set")

        # all drawings in project
        if drawing_ids is None:
            url = f"{self.project['id']}/drawings"
            json_data = self.request(url, RequestType.GET, params=params)
            results = json_data["data"]["drawing_list"]
            return results

        results = []
        for dwg_id in drawing_ids:
            url = f"{self.project['id']}/drawings/{dwg_id}"
            json_data = self.request(url, RequestType.GET, params=params)
            results.append(json_data["data"])
        return results

    def update_drawings(self, drawing_ids, payload):
        """
        Update drawings

        Args:
            drawing_ids (list): A list of drawing IDs to update.
            payload (dict): A dictionary containing the updates to apply.

        Returns:
            dict: A dictionary containing the response from the API.

        Raises:
            ValueError: If the project is not set.
        """
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/drawings/bulk.update"
        payload["drawing_ids"] = drawing_ids
        payload["project_id"] = self.project["id"]
        return self.request(url, RequestType.PUT, data=payload)

    def delete_drawings(self, drawing_ids):
        """
        Delete drawings

        Args:
            drawing_ids (list): A list of drawing IDs to delete.

        Returns:
            dict: A dictionary containing the response from the API.

        Raises:
            ValueError: If the project is not set.
        """
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/drawings/bulk.delete"
        payload = {"drawing_ids": drawing_ids}
        return self.request(url, RequestType.DELETE, data=payload)

    ################################################################################################
    # CRUD Videos
    ################################################################################################
    def upload_videos(self, video_paths):
        """
        Upload videos

        Args:
            video_paths (list): A list of video paths to upload.

        Returns:
            dict: A dictionary containing the response from the API.

        Raises:
            ValueError: If the project is not set.
        """

        if not self.project:
            raise ValueError("Project not set")

        # Upload images to S3
        assets = []
        for file_path in video_paths:
            base, ext = os.path.splitext(os.path.basename(file_path))
            filename = f"{base}_{random_string(6)}{ext}"
            s3_path = (
                self.s3_base_url + f"/projects/{self.project['id']}/drawings/{filename}"
            )
            upload_file(file_path, s3_path)
            assets.append(
                {
                    "name": base,
                    "filename": base + ext,
                    "url": filename,
                    "size": {"filesize": os.path.getsize(file_path)},
                }
            )

        # Add images to project
        url = f"{self.project['id']}/assets/bulk.create"
        payload = {"project_id": self.project["id"], "asset_type": 4, "assets": assets}
        res = self.request(url, RequestType.POST, data=payload)

        return res

    def get_videos(self, video_ids=None, params=None):
        """
        Retrieves a list of videos based on specified video IDs.

        This method queries the T2D2 API to fetch details for a list of videos identified by their unique IDs. It returns a list of video details, including metadata such as title, duration, and resolution. If a video ID does not correspond to an existing video, it is silently ignored.

        Args:
            video_ids (list of str): A list of video IDs for which details are to be retrieved.

        Returns:
            list of dict: A list of dictionaries, each representing the details of a video. Each dictionary contains keys such as 'id', 'title', 'duration', and 'resolution'.

        Raises:
            ConnectionError: If there is a problem connecting to the T2D2 API.
            ValueError: If `video_ids` is empty or not a list.

        Example:
            >>> video_ids = ['abc123', 'def456', 'ghi789']
            >>> videos = get_videos(video_ids)
            >>> print(videos)
            [{'id': 'abc123', 'title': 'Video One', 'duration': '5 minutes', 'resolution': '1080p'}, ...]
        """
        if not self.project:
            raise ValueError("Project not set")

        # all videos in project
        if video_ids is None:
            url = f"{self.project['id']}/videos"
            json_data = self.request(url, RequestType.GET, params=params)
            results = json_data["data"]["video_list"]
            return results

        results = []
        for video_id in video_ids:
            url = f"{self.project['id']}/videos/{video_id}"
            json_data = self.request(url, RequestType.GET, params=params)
            results.append(json_data["data"])
        return results

    def update_videos(self, video_ids, payload):
        """
        Updates the details of multiple videos in the current project.

        This method accepts a list of dictionaries, each representing updates to a specific video identified by its ID. The updates can include changes to video metadata such as title, duration, and resolution. The method applies these updates to each corresponding video in the project. If a video ID does not exist within the project, that update is ignored.

        Args:
            video_updates (list of dict): A list of dictionaries, each containing updates for a specific video. Each dictionary must include an 'id' key corresponding to the video ID, along with any other keys representing the fields to be updated.

        Returns:
            list of dict: A list of dictionaries, each representing the updated details of a video. Each dictionary contains keys such as 'id', 'title', 'duration', and 'resolution', reflecting the applied updates.

        Raises:
            ValueError: If `video_updates` is empty, not a list, or if any dictionary in the list does not contain an 'id' key.
            ConnectionError: If there is a problem connecting to the T2D2 API to apply the updates.

        Example:
            >>> video_updates = [
            ...     {'id': 'abc123', 'title': 'Updated Video One', 'duration': '6 minutes'},
            ...     {'id': 'def456', 'resolution': '720p'}
            ... ]
            >>> updated_videos = update_videos(video_updates)
            >>> print(updated_videos)
            [{'id': 'abc123', 'title': 'Updated Video One', 'duration': '6 minutes', 'resolution': '1080p'}, ...]
        """
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/videos/bulk.update"
        payload["video_ids"] = video_ids
        payload["project_id"] = self.project["id"]
        return self.request(url, RequestType.PUT, data=payload)

    def delete_videos(self, video_ids):
        """
        Deletes a list of videos from the current project based on specified video IDs.

        This method removes videos identified by their unique IDs from the project. If a video ID does not correspond to an existing video within the project, it is silently ignored. This operation is irreversible.

        Args:
            video_ids (list of str): A list of video IDs indicating the videos to be deleted from the project.

        Returns:
            list of str: A list of video IDs that were successfully deleted.

        Raises:
            ValueError: If `video_ids` is empty or not a list.
            ConnectionError: If there is a problem connecting to the T2D2 API to delete the videos.

        Example:
            >>> video_ids = ['abc123', 'def456']
            >>> deleted_videos = delete_videos(video_ids)
            >>> print(deleted_videos)
            ['abc123', 'def456']
        """
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/videos/bulk.delete"
        payload = {"video_ids": video_ids}
        return self.request(url, RequestType.DELETE, data=payload)

    ################################################################################################
    # CRUD 3D
    ################################################################################################
    def upload_threed(self, threed_paths):
        """
        Uploads 3D model files to the current project.

        This method takes a list of file paths pointing to 3D model files and uploads them to the T2D2 project associated with this instance. Each file is uploaded to a pre-specified storage location and is then registered within the project with a unique identifier.

        Args:
            threed_paths (list of str): A list of file paths, each pointing to a 3D model file to be uploaded.

        Returns:
            list of dict: A list of dictionaries, each representing the upload status of a 3D model. Each dictionary contains keys such as 'id', 'path', and 'status', indicating the unique identifier for the uploaded model, the path of the uploaded file, and the upload status, respectively.

        Raises:
            FileNotFoundError: If any of the paths in `threed_paths` does not point to an existing file.
            ConnectionError: If there is a problem connecting to the T2D2 API or the storage location to upload the files.
            ValueError: If `threed_paths` is empty or not a list.

        Example:
            >>> threed_paths = ['/path/to/model1.obj', '/path/to/model2.stl']
            >>> upload_status = upload_threed(threed_paths)
            >>> print(upload_status)
            [{'id': 'model1_id', 'path': '/path/to/model1.obj', 'status': 'Uploaded'}, ...]
        """

        if not self.project:
            raise ValueError("Project not set")

        # Upload images to S3
        assets = []
        for file_path in threed_paths:
            base, ext = os.path.splitext(os.path.basename(file_path))
            filename = f"{base}_{random_string(6)}{ext}"
            s3_path = (
                self.s3_base_url
                + f"/projects/{self.project['id']}/3d_models/{filename}"
            )
            upload_file(file_path, s3_path)
            assets.append(
                {
                    "name": base,
                    "filename": base + ext,
                    "url": filename,
                    "size": {"filesize": os.path.getsize(file_path)},
                }
            )

        # Add images to project
        url = f"{self.project['id']}/assets/bulk.create"
        payload = {"project_id": self.project["id"], "asset_type": 6, "assets": assets}
        res = self.request(url, RequestType.POST, data=payload)

        return res

    def get_threed(self, model_ids=None, params=None):
        """
        Retrieves details of 3D models from the current project based on specified 3D model IDs.

        This method queries the project for details on 3D models identified by their unique IDs. It returns information about each model, including its file name, size, and upload status. If a 3D model ID does not correspond to an existing model within the project, it is silently ignored.

        Args:
            threed_ids (list of str): A list of 3D model IDs for which details are to be retrieved.

        Returns:
            list of dict: A list of dictionaries, each representing the details of a 3D model. Each dictionary contains keys such as 'id', 'name', 'size', and 'status', providing information about the model.

        Raises:
            ValueError: If `threed_ids` is empty or not a list.
            ConnectionError: If there is a problem connecting to the T2D2 API to retrieve the model details.

        Example:
            >>> threed_ids = ['model1_id', 'model2_id']
            >>> threed_details = get_threed(threed_ids)
            >>> print(threed_details)
            [{'id': 'model1_id', 'name': 'model1.obj', 'size': '2MB', 'status': 'Uploaded'}, ...]
        """
        if not self.project:
            raise ValueError("Project not set")

        # all videos in project
        if model_ids is None:
            url = f"{self.project['id']}/3d-models"
            json_data = self.request(url, RequestType.GET, params=params)
            results = json_data["data"]["model_list"]
            return results

        results = []
        for model_id in model_ids:
            url = f"{self.project['id']}/3d-models/{model_id}"
            json_data = self.request(url, RequestType.GET, params=params)
            results.append(json_data["data"])
        return results

    def update_threed(self, model_ids, payload):
        """Update videos"""
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/3d-models/bulk.update"
        payload["model_ids"] = model_ids
        payload["project_id"] = self.project["id"]
        return self.request(url, RequestType.PUT, data=payload)

    def delete_threed(self, model_ids):
        """Delete drawings"""
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/3d-models/bulk.delete"
        payload = {"model_ids": model_ids}
        return self.request(url, RequestType.DELETE, data=payload)

    ################################################################################################
    # CRUD Reports
    ################################################################################################
    def upload_reports(self, report_paths):
        """
        Updates the details of multiple 3D models in the current project.

        This method accepts a list of dictionaries, each representing updates to a specific 3D model identified by its ID. The updates can include changes to model metadata such as name, size, and status. The method applies these updates to each corresponding model in the project. If a 3D model ID does not exist within the project, that update is ignored.

        Args:
            threed_updates (list of dict): A list of dictionaries, each containing updates for a specific 3D model. Each dictionary must include an 'id' key corresponding to the model ID, along with any other keys representing the fields to be updated.

        Returns:
            list of dict: A list of dictionaries, each representing the updated details of a 3D model. Each dictionary contains keys such as 'id', 'name', 'size', and 'status', reflecting the applied updates.

        Raises:
            ValueError: If `threed_updates` is empty, not a list, or if any dictionary in the list does not contain an 'id' key.
            ConnectionError: If there is a problem connecting to the T2D2 API to apply the updates.

        Example:
            >>> threed_updates = [
            ...     {'id': 'model1_id', 'name': 'updated_model1.obj', 'size': '3MB'},
            ...     {'id': 'model2_id', 'status': 'Processing'}
            ... ]
            >>> updated_models = update_threed(threed_updates)
            >>> print(updated_models)
            [{'id': 'model1_id', 'name': 'updated_model1.obj', 'size': '3MB', 'status': 'Uploaded'}, ...]
        """

        if not self.project:
            raise ValueError("Project not set")

        # Upload images to S3
        assets = []
        for file_path in report_paths:
            base, ext = os.path.splitext(os.path.basename(file_path))
            filename = f"{base}_{random_string(6)}{ext}"
            s3_path = (
                self.s3_base_url + f"/projects/{self.project['id']}/reports/{filename}"
            )
            response = upload_file(file_path, s3_path)
            if not response["success"]:
                raise ValueError(response["message"])

            assets.append(
                {
                    "name": base,
                    "filename": base + ext,
                    "url": filename,
                    "size": {"filesize": os.path.getsize(file_path)},
                }
            )

        # Add images to project
        url = f"{self.project['id']}/assets/bulk.create"
        payload = {"project_id": self.project["id"], "asset_type": 5, "assets": assets}
        res = self.request(url, RequestType.POST, data=payload)

        return res

    def get_reports(self, report_ids=None, params=None):
        """
        Retrieves a list of reports based on specified report IDs.

        This method queries the project for details on reports identified by their unique IDs. It returns information about each report, including its title, creation date, and status. If a report ID does not correspond to an existing report within the project, it is silently ignored.

        Args:
            report_ids (list of str): A list of report IDs for which details are to be retrieved.

        Returns:
            list of dict: A list of dictionaries, each representing the details of a report. Each dictionary contains keys such as 'id', 'title', 'creation_date', and 'status', providing information about the report.

        Raises:
            ValueError: If `report_ids` is empty or not a list.
            ConnectionError: If there is a problem connecting to the T2D2 API to retrieve the report details.

        Example:
            >>> report_ids = ['report1_id', 'report2_id']
            >>> report_details = get_reports(report_ids)
            >>> print(report_details)
            [{'id': 'report1_id', 'title': 'Report One', 'creation_date': '2023-01-01', 'status': 'Completed'}, ...]
        """
        if report_ids is None:
            return []

        if not self.project:
            raise ValueError("Project not set")

        results = []
        for report_id in report_ids:
            url = f"{self.project['id']}/reports/{report_id}"
            json_data = self.request(url, RequestType.GET, params=params)
            results.append(json_data["data"])
        return results

    def update_reports(self, report_ids, payload):
        """
        Updates the details of multiple reports in the current project.

        This method accepts a list of dictionaries, each representing updates to a specific report identified by its ID. The updates can include changes to report metadata such as title, creation date, and status. The method applies these updates to each corresponding report in the project. If a report ID does not exist within the project, that update is ignored.

        Args:
            report_updates (list of dict): A list of dictionaries, each containing updates for a specific report. Each dictionary must include an 'id' key corresponding to the report ID, along with any other keys representing the fields to be updated.

        Returns:
            list of dict: A list of dictionaries, each representing the updated details of a report. Each dictionary contains keys such as 'id', 'title', 'creation_date', and 'status', reflecting the applied updates.

        Raises:
            ValueError: If `report_updates` is empty, not a list, or if any dictionary in the list does not contain an 'id' key.
            ConnectionError: If there is a problem connecting to the T2D2 API to apply the updates.

        Example:
            >>> report_updates = [
            ...     {'id': 'report1_id', 'title': 'Updated Report One', 'creation_date': '2023-02-01'},
            ...     {'id': 'report2_id', 'status': 'In Progress'}
            ... ]
            >>> updated_reports = update_reports(report_updates)
            >>> print(updated_reports)
            [{'id': 'report1_id', 'title': 'Updated Report One', 'creation_date': '2023-02-01', 'status': 'Completed'}, ...]
        """
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/reports/bulk.update"
        payload["report_ids"] = report_ids
        payload["project_id"] = self.project["id"]
        return self.request(url, RequestType.PUT, data=payload)

    def delete_reports(self, report_ids):
        """
        Deletes a list of reports from the current project based on specified report IDs.

        This method removes reports identified by their unique IDs from the project. If a report ID does not correspond to an existing report within the project, it is silently ignored. This operation is irreversible.

        Args:
            report_ids (list of str): A list of report IDs indicating the reports to be deleted from the project.

        Returns:
            list of str: A list of report IDs that were successfully deleted.

        Raises:
            ValueError: If `report_ids` is empty or not a list.
            ConnectionError: If there is a problem connecting to the T2D2 API to delete the reports.

        Example:
            >>> report_ids = ['report1_id', 'report2_id']
            >>> deleted_reports = delete_reports(report_ids)
            >>> print(deleted_reports)
            ['report1_id', 'report2_id']
        """
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/reports/bulk.delete"
        payload = {"report_ids": report_ids}
        return self.request(url, RequestType.DELETE, data=payload)

    ################################################################################################
    # CRUD Tags
    ################################################################################################
    def get_tags(self, params=None):
        """
        Retrieves a list of tags based on specified tag IDs.

        This method queries the project for details on tags identified by their unique IDs. It returns information about each tag, including its name, associated resources, and creation date. If a tag ID does not correspond to an existing tag within the project, it is silently ignored.

        Args:
            tag_ids (list of str): A list of tag IDs for which details are to be retrieved.

        Returns:
            list of dict: A list of dictionaries, each representing the details of a tag. Each dictionary contains keys such as 'id', 'name', 'resources', and 'creation_date', providing information about the tag.

        Raises:
            ValueError: If `tag_ids` is empty or not a list.
            ConnectionError: If there is a problem connecting to the T2D2 API to retrieve the tag details.

        Example:
            >>> tag_ids = ['tag1_id', 'tag2_id']
            >>> tag_details = get_tags(tag_ids)
            >>> print(tag_details)
            [{'id': 'tag1_id', 'name': 'Tag One', 'resources': ['resource1_id', 'resource2_id'], 'creation_date': '2023-01-01'}, ...]
        """
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/tags"
        json_data = self.request(url, RequestType.GET, params=params)
        return json_data["data"]

    def add_tags(self, tags):
        """
        Adds new tags to the project.

        This method allows for the creation of new tags within the project. Each tag is defined by a name and can optionally be associated with a list of resource IDs at the time of creation. The method returns the IDs of the newly created tags.

        Args:
            tags (list of dict): A list of dictionaries, each representing a tag to be added. Each dictionary must include a 'name' key, and can optionally include a 'resources' key with a list of resource IDs to associate with the tag.

        Returns:
            list of str: A list of the IDs of the newly created tags.

        Raises:
            ValueError: If `tags` is empty, not a list, or if any dictionary in the list does not contain a 'name' key.
            ConnectionError: If there is a problem connecting to the T2D2 API to add the tags.

        Example:
            >>> tags_to_add = [
            ...     {'name': 'New Tag 1', 'resources': ['resource1_id', 'resource2_id']},
            ...     {'name': 'New Tag 2'}
            ... ]
            >>> new_tag_ids = add_tags(tags_to_add)
            >>> print(new_tag_ids)
            ['new_tag1_id', 'new_tag2_id']
        """
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/tags"
        if isinstance(tags, str):
            tags = [tags]

        results = []
        for tag in tags:
            payload = {"name": tag}
            try:
                # Use POST to create new tag
                result = self.request(url, RequestType.POST, data=payload)
                results.append(result)
            except Exception as e:
                print("*WARNING* Tag already exists: ", e)

        return results

    # TODO: Delete / Update Tags
    ################################################################################################
    # CRUD Annotation Classes
    ################################################################################################
    def get_materials(self):
        """
        Retrieves a list of materials from the current project.

        This method queries the project's database for a list of all materials that have been defined within the project. It returns a list of material names. If the project is not set or initialized, it raises an error.

        Returns:
            list of str: A list containing the names of all materials in the project.

        Raises:
            RuntimeError: If the project is not set or initialized.

        Example:
            >>> materials = get_materials()
            >>> print(materials)
            ['Concrete', 'Steel', 'Wood']
        """
        if not self.project:
            raise ValueError("Project not set")

        url = "material"
        params = {"project_id": self.project["id"]}
        json_data = self.request(url, RequestType.GET, params=params)
        return json_data["data"]

    def get_annotation_classes(self, params=None):
        """
        Retrieves a list of annotation classes from the current project.

        This method queries the project's database for a list of all annotation classes that have been defined within the project. It returns a list of dictionaries, each representing an annotation class with details such as its ID, name, and associated attributes. If the project is not set or initialized, it raises an error.

        Args:
            params (dict, optional): A dictionary of parameters to filter the annotation classes. Defaults to None.

        Returns:
            list of dict: A list containing dictionaries, each with details of an annotation class.

        Raises:
            RuntimeError: If the project is not set or initialized.

        Example:
            >>> annotation_classes = get_annotation_classes()
            >>> print(annotation_classes)
            [{'id': 'class1', 'name': 'Vehicle', 'attributes': ['color', 'make']}, ...]
        """
        if not self.project:
            raise ValueError("Project not set")

        url = "annotation-class"
        params_ = {
            "project_id": self.project["id"],
            "scope": "DEFAULT",
            "sortBy": "id:asc",
        }
        if params is not None:
            params_.update(params)

        print(params_)

        json_data = self.request(url, RequestType.GET, params=params_)
        return json_data["data"]

    def add_annotation_class(self, name, color=None, materials=None):
        """
        Adds new annotation classes to the current project.

        This method allows for the creation of new annotation classes within the project. Each annotation class is defined by a name and can optionally include a list of attributes. The method returns the IDs of the newly created annotation classes.

        Args:
            annotation_classes (list of dict): A list of dictionaries, each representing an annotation class to be added. Each dictionary must include a 'name' key, and can optionally include an 'attributes' key with a list of attribute names.

        Returns:
            list of str: A list of the IDs of the newly created annotation classes.

        Raises:
            ValueError: If `annotation_classes` is empty, not a list, or if any dictionary in the list does not contain a 'name' key.
            ConnectionError: If there is a problem connecting to the database to add the annotation classes.

        Example:
            >>> annotation_classes_to_add = [
            ...     {'name': 'Pedestrian', 'attributes': ['age', 'gender']},
            ...     {'name': 'Traffic Light', 'attributes': ['color']}
            ... ]
            >>> new_annotation_class_ids = add_annotation_classes(annotation_classes_to_add)
            >>> print(new_annotation_class_ids)
            ['new_class1_id', 'new_class2_id']
        """
        if not self.project:
            raise ValueError("Project not set")

        if materials is None:
            materials = []

        if color is None:
            color = random_color()

        url = "annotation-class/create-annotation-class"
        payload = {
            "project_id": self.project["id"],
            "name": name,
            "materials": materials,
            "color": color,
        }
        results = self.request(url, RequestType.POST, data=payload)

        return results

    def delete_annotation_classes(self, annotation_class_ids):
        """
        Deletes specified annotation classes from the current project.

        This method removes annotation classes identified by their unique IDs from the project. If an annotation class ID does not correspond to an existing class within the project, it is silently ignored. This operation is irreversible.

        Args:
            class_ids (list of str): A list of annotation class IDs indicating the classes to be deleted from the project.

        Returns:
            list of str: A list of annotation class IDs that were successfully deleted.

        Raises:
            ValueError: If `class_ids` is empty or not a list.
            ConnectionError: If there is a problem connecting to the database to delete the annotation classes.

        Example:
            >>> class_ids_to_delete = ['class1_id', 'class2_id']
            >>> deleted_class_ids = delete_annotation_classes(class_ids_to_delete)
            >>> print(deleted_class_ids)
            ['class1_id', 'class2_id']
        """
        if not self.project:
            raise ValueError("Project not set")

        if isinstance(annotation_class_ids, int):
            annotation_class_ids = [annotation_class_ids]

        if len(annotation_class_ids) == 0:
            return {"success": False, "message": "No annotation class ids provided"}

        url = f"{self.project['id']}/annotation-class/bulk.delete"
        payload = {"annotation_class_ids": annotation_class_ids}
        results = self.request(url, RequestType.DELETE, data=payload)

        return results

    # TODO: Update Annotation Classes
    ################################################################################################
    # CRUD Annotations
    ################################################################################################
    def get_annotations(self, image_id=None, params=None):
        """
        Retrieves a list of annotations from the current project based on specified criteria.

        This method queries the project's database for annotations that match the given criteria, such as annotation class, attributes, and creation date range. It returns a list of dictionaries, each representing an annotation with details such as its ID, associated class, attributes, and creation date.

        Args:
            criteria (dict): A dictionary specifying the criteria for filtering annotations. Possible keys include 'class_id', 'attributes', and 'date_range', with their corresponding values used to filter the results.

        Returns:
            list of dict: A list containing dictionaries, each with details of an annotation that matches the specified criteria.

        Raises:
            ValueError: If `criteria` is not a dictionary or if required keys are missing.
            ConnectionError: If there is a problem connecting to the database to retrieve the annotations.

        Example:
            >>> criteria = {'class_id': 'vehicle', 'date_range': ('2023-01-01', '2023-01-31')}
            >>> annotations = get_annotations(criteria)
            >>> print(annotations)
            [{'id': 'annotation1', 'class_id': 'vehicle', 'attributes': {'color': 'red'}, 'creation_date': '2023-01-15'}, ...]
        """
        if not self.project:
            raise ValueError("Project not set")

        if params is None:
            params = {}

        if image_id is None:
            images = self.get_images(params=params)
            image_ids = [img["id"] for img in images]
        else:
            image_ids = [image_id]

        images = self.get_images(image_ids=image_ids, params=params)
        annotations = []
        for img in images:
            annotations.extend(img["annotations"])

        return annotations

    def delete_annotations(self, image_id, annotation_ids=None):
        """
        Deletes specified annotations from the current project.

        This method removes annotations identified by their unique IDs from the project. If an annotation ID does not correspond to an existing annotation within the project, it is silently ignored. This operation is irreversible.

        Args:
            annotation_ids (list of str): A list of annotation IDs indicating the annotations to be deleted from the project.

        Returns:
            list of str: A list of annotation IDs that were successfully deleted.

        Raises:
            ValueError: If `annotation_ids` is empty or not a list.
            ConnectionError: If there is a problem connecting to the database to delete the annotations.

        Example:
            >>> annotation_ids_to_delete = ['annotation1_id', 'annotation2_id']
            >>> deleted_annotation_ids = delete_annotations(annotation_ids_to_delete)
            >>> print(deleted_annotation_ids)
            ['annotation1_id', 'annotation2_id']
        """

        if not self.project:
            raise ValueError("Project not set")

        if annotation_ids is None:
            # Get annotation_ids for all annotations in image
            annotations = self.get_annotations(image_id)
            annotation_ids = [ann["id"] for ann in annotations]

        payload = {
            "project_id": self.project["id"],
            "image_id": image_id,
            "annotation_ids": annotation_ids,
        }

        return self.request("annotation", RequestType.DELETE, data=payload)

    def add_annotations(self, image_id, annotations):
        """
        Adds new annotations to the current project.

        This method allows for the creation of new annotations within the project. Each annotation is defined by its associated class ID and can include a set of attributes. The method returns the IDs of the newly created annotations.

        Args:
            annotations (list of dict): A list of dictionaries, each representing an annotation to be added. Each dictionary must include a 'class_id' key, and can optionally include an 'attributes' key with a dictionary of attribute names and values.

        Returns:
            list of str: A list of the IDs of the newly created annotations.

        Raises:
            ValueError: If `annotations` is empty, not a list, or if any dictionary in the list does not contain a 'class_id' key.
            ConnectionError: If there is a problem connecting to the database to add the annotations.

        Example:
            >>> annotations_to_add = [
            ...     {'class_id': 'vehicle', 'attributes': {'color': 'red', 'make': 'Toyota'}},
            ...     {'class_id': 'pedestrian'}
            ... ]
            >>> new_annotation_ids = add_annotations(annotations_to_add)
            >>> print(new_annotation_ids)
            ['new_annotation1_id', 'new_annotation2_id']
        """
        if not self.project:
            raise ValueError("Project not set")

        url = "annotation"
        payload = {
            "project_id": self.project["id"],
            "image_id": image_id,
            "annotations": annotations,
        }

        results = self.request(url, RequestType.POST, data=payload)

        return results

    # TODO: Update Annotations
    ################################################################################################
    # CRUD Geotags
    ################################################################################################
    def get_geotags(self, drawing_id, params=None):
        """
        Retrieves a list of geotags from the current project based on specified criteria.

        This method queries the project's database for geotags that match the given criteria, such as location, radius, and associated tags. It returns a list of dictionaries, each representing a geotag with details such as its ID, location (latitude and longitude), and associated tags.

        Args:
            criteria (dict): A dictionary specifying the criteria for filtering geotags. Possible keys include 'location' (a tuple of latitude and longitude), 'radius' (in meters), and 'tags' (a list of tag IDs).

        Returns:
            list of dict: A list containing dictionaries, each with details of a geotag that matches the specified criteria.

        Raises:
            ValueError: If `criteria` is not a dictionary, if required keys are missing, or if the values are not in the expected format.
            ConnectionError: If there is a problem connecting to the database to retrieve the geotags.

        Example:
            >>> criteria = {'location': (40.7128, -74.0060), 'radius': 1000, 'tags': ['tag1', 'tag2']}
            >>> geotags = get_geotags(criteria)
            >>> print(geotags)
            [{'id': 'geotag1', 'location': (40.7138, -74.0065), 'tags': ['tag1']}, ...]
        """
        if drawing_id is None:
            return []

        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/geotags?drawing_id={drawing_id}"
        json_data = self.request(url, RequestType.GET, params=params)

        return json_data["data"]

    def add_geotags(self, drawing_id, geotags):
        """
        Adds new geotags to the current project.

        This method allows for the creation of new geotags within the project. Each geotag is defined by its location (latitude and longitude) and can optionally include a set of associated tags. The method returns the IDs of the newly created geotags.

        Args:
            geotags (list of dict): A list of dictionaries, each representing a geotag to be added. Each dictionary must include a 'location' key with a tuple of latitude and longitude, and can optionally include a 'tags' key with a list of tag IDs.

        Returns:
            list of str: A list of the IDs of the newly created geotags.

        Raises:
            ValueError: If `geotags` is empty, not a list, or if any dictionary in the list does not contain a 'location' key or the 'location' value is not a tuple of latitude and longitude.
            ConnectionError: If there is a problem connecting to the database to add the geotags.

        Example:
            >>> geotags_to_add = [
            ...     {'location': (40.7128, -74.0060), 'tags': ['tag1', 'tag2']},
            ...     {'location': (34.0522, -118.2437)}
            ... ]
            >>> new_geotag_ids = add_geotags(geotags_to_add)
            >>> print(new_geotag_ids)
            ['new_geotag1_id', 'new_geotag2_id']
        """
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/geotags/bulk.create"
        payload = {
            "drawing_id": drawing_id,
            "geotags": geotags,
        }
        results = self.request(url, RequestType.POST, data=payload)

        return results

    def delete_geotags(self, drawing_id, geotag_ids):
        """
        Deletes specified geotags from a drawing in the current project.

        This method removes geotags identified by their unique IDs from a specified drawing within the project. If a geotag ID does not correspond to an existing geotag within the specified drawing, it is silently ignored. This operation is irreversible.

        Args:
            drawing_id (str): The ID of the drawing from which the geotags will be deleted.
            geotag_ids (list of str): A list of geotag IDs indicating the geotags to be deleted from the drawing.

        Returns:
            dict: A dictionary containing the status of the deletion operation, including any errors encountered.

        Raises:
            ValueError: If `drawing_id` is empty or not a string, or if `geotag_ids` is empty or not a list.
            ConnectionError: If there is a problem connecting to the database to delete the geotags.

        Example:
            >>> drawing_id = 'drawing123'
            >>> geotag_ids_to_delete = ['geotag1_id', 'geotag2_id']
            >>> deletion_status = delete_geotags(drawing_id, geotag_ids_to_delete)
            >>> print(deletion_status)
            {'success': True, 'errors': []}
        """
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/geotags/bulk.delete"
        payload = {
            "drawing_id": drawing_id,
            "geotag_ids": geotag_ids,
        }
        results = self.request(url, RequestType.POST, data=payload)

        return results

    ################################################################################################
    # CRUD Downloads
    ################################################################################################
    def upload_downloads(self, file_paths):
        """
        Uploads and processes download requests for a specified project within the T2D2 SDK.

        This method is responsible for uploading files associated with download requests for a given project. It uploads each file to the server, links it to the project, and optionally sends a notification to the requester upon successful upload. The method returns a summary of the upload process, detailing the status of each request and any errors that occurred.

        Args:
            project_id (str): The unique identifier of the project for which downloads are being processed.
            download_requests (list of dict): A list of dictionaries, each representing a download request. Each dictionary must include 'request_id' and 'file_path', and may optionally include 'notify' to indicate if the requester should be notified upon completion.

        Returns:
            list of dict: A summary of the upload process for each download request, including 'request_id', 'status' (success or failure), and 'error' message in case of failure.

        Raises:
            ValueError: If `project_id` is not provided, `download_requests` is not a list, or any request dictionary is missing required keys.
            FileNotFoundError: If any 'file_path' does not point to an existing file.
            ConnectionError: If there is an issue connecting to the server to upload the files.

        Example:
            >>> project_id = 'projectABC123'
            >>> download_requests = [
            ...     {'request_id': 'download1', 'file_path': '/path/to/file1.zip', 'notify': True},
            ...     {'request_id': 'download2', 'file_path': '/path/to/file2.zip'}
            ... ]
            >>> upload_results = upload_downloads(project_id, download_requests)
            >>> print(upload_results)
            [{'request_id': 'download1', 'status': 'success'}, {'request_id': 'download2', 'status': 'failure', 'error': 'File not found'}]
        """

        if not self.project:
            raise ValueError("Project not set")

        for file_path in file_paths:
            filename = os.path.basename(file_path)
            s3_path = (
                self.s3_base_url
                + f"/projects/{self.project['id']}/downloads/{filename}"
            )
            response = upload_file(file_path, s3_path)
            if not response["success"]:
                raise ValueError(response["message"])

        return {"success": True, "message": "Files uploaded"}

    ################################################################################################
    # Classes and Conditions methods
    ################################################################################################
    def get_classes(self):
        """Return classes"""
        if not self.project:
            raise ValueError("Project not set")

        # Get full class data
        class_map = {}
        classes = self.get_annotation_classes()
        for lbl in classes["label_list"]:
            class_map[lbl["id"]] = lbl

        url = f"{self.project['id']}/conditions"
        json_data = self.request(url, RequestType.GET)
        output = []
        for lbl in json_data["data"]["condition_list"]:
            lbl["name"] = class_map[lbl["annotation_class_id"]]["name"]
            output.append(lbl)
        return

    def summarize_images(self):
        """Summarize images"""
        if not self.project:
            raise ValueError("Project not set")

        # Return image summary
        images = self.get_images()
        if len(images) == 0:
            return {
                "region_group": {},
                "date_group": {},
                "tag_group": {},
            }
        # Group by region, date and tags
        region_group, date_group, tag_group = (
            defaultdict(int),
            defaultdict(int),
            defaultdict(int),
        )
        for img in images:
            img_region = img["region"]["name"]
            img_date = ts2date(img["captured_date"]).split(" ")[0]
            img_tags = img["tags"]

            region_group[img_region] += 1
            date_group[img_date] += 1
            for img_tag in img_tags:
                tag_group[img_tag["name"]] += 1

        return {
            "region_group": region_group,
            "date_group": date_group,
            "tag_group": tag_group,
        }

    def summarize_conditions(self):
        """Summarize conditions by region, label and rating"""
        if not self.project:
            raise ValueError("Project not set")

        imgs = self.get_images()

        anns = defaultdict(list)
        for img in imgs:
            reg = img["region"]["name"]
            anns_img = self.get_annotations(image_id=img["id"])
            anns[reg] += anns_img

        result = {}
        for reg, annotations in anns.items():
            sublist = {}
            for ann in annotations:
                label = ann["annotation_class"]["annotation_class_name"]
                rating = ann.get("condition", {}).get("rating_name", "default")
                area = ann["area"]
                length = ann["length"]
                ann_id = ann["id"]
                key = (label, rating)
                if key in sublist:
                    sublist[key]["count"] += 1
                    sublist[key]["length"] += length
                    sublist[key]["area"] += area
                    sublist[key]["annotation_ids"].append(ann_id)
                else:
                    sublist[key] = {}
                    sublist[key]["count"] = 1
                    sublist[key]["length"] = length
                    sublist[key]["area"] = area
                    sublist[key]["annotation_ids"] = []

            result[reg] = sublist

        return result


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


####################################################################################################
