"""T2D2 SDK API wrapper"""
import os
import random
import string
from enum import Enum, auto
from urllib.parse import urlencode, urlparse

import boto3
import requests

TIMEOUT = 60
BASE_URL = os.getenv("T2D2_API_URL", "https://api-v3.t2d2.ai/api/")
# DEV https://api-v3-dev.t2d2.ai/api/

####################################################################################################
def random_string(length: int = 6) -> str:
    """Generate a random string of fixed length"""
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))


####################################################################################################
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
        return {"success": False, "message": f"{str(e)} \n{bucket} \n{key} \n{file_path}"}


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
        return {"success": False, "message": f"{str(e)} \n{bucket} \n{key} \n{file_path}"}


####################################################################################################
class RequestType(Enum):
    """Request types"""

    GET = auto()
    PUT = auto()
    POST = auto()
    DELETE = auto()


####################################################################################################
class T2D2(object):
    """T2D2 API wrapper"""

    base_url: str
    headers: dict
    s3_base_url: str
    aws_region: str
    bucket: str
    access_token: str
    api_key: str
    project: dict = None

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
        if req_type == RequestType.GET:
            res = requests.get(
                url, headers=headers, params=urlencode(params), timeout=TIMEOUT
            )
        elif req_type == RequestType.POST:
            res = requests.post(
                url,
                headers=headers,
                params=urlencode(params),
                json=data,
                timeout=TIMEOUT,
            )
        elif req_type == RequestType.PUT:
            res = requests.put(
                url,
                headers=headers,
                params=urlencode(params),
                json=data,
                timeout=TIMEOUT,
            )
        elif req_type == RequestType.DELETE:
            res = requests.delete(
                url,
                headers=headers,
                params=urlencode(params),
                json=data,
                timeout=TIMEOUT,
            )
        else:
            raise ValueError("Request type not yet supported. Coming soon")

        if res.status_code == 200:
            try:
                return res.json()
            except Exception as e:
                print("JSON Conversion Error: ", e)
                return {"content": res.content}
        else:
            print(f"URL: {req_type} {url}")
            print(f"HEADERS: {headers}")
            print(f"PARAMS: {params}")
            print(f"DATA: {data}")
            print(res.status_code, res.content)
            raise ValueError(f"Error code received: {res.status_code}")

    def login(self, credentials):
        """Login and update header with authorization credentials"""

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

    ################################################################################################
    # Project Get/Set
    ################################################################################################
    def get_project(self, project_id):
        """Return project list"""
        url = f"project/{project_id}"
        json_data = self.request(url, RequestType.GET)
        return json_data["data"]

    def set_project(self, project_id):
        """Set project by project_id"""
        json_data = self.request(f"project/{project_id}", RequestType.GET)
        project = json_data["data"]
        self.project = project

        self.s3_base_url = project["config"]["s3_base_url"]
        self.aws_region = project["config"]["aws_region"]
        res = urlparse(self.s3_base_url)
        self.bucket = res.netloc.split(".")[0]
        return

    ################################################################################################
    # Get Assets
    ################################################################################################
    def get_assets(self, asset_type=1, asset_ids=None):
        """Return asset list based on specified ids"""
        if asset_ids is None:
            return []

        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/assets"
        payload = {"asset_type": asset_type, "asset_ids": asset_ids}
        json_data = self.request(url, RequestType.POST, data=payload)
        return json_data["data"]

    def get_images(self, image_ids=None, params=None):
        """Return image list based on specified ids"""
        if image_ids is None:
            return []

        if not self.project:
            raise ValueError("Project not set")

        results = []
        for img_id in image_ids:
            url = f"{self.project['id']}/images/{img_id}"
            json_data = self.request(url, RequestType.GET, params=params)
            results.append(json_data["data"])
        return results

    def get_drawings(self, drawing_ids=None, params=None):
        """Return drawing list based on specified ids"""
        if drawing_ids is None:
            return []

        if not self.project:
            raise ValueError("Project not set")

        results = []
        for dwg_id in drawing_ids:
            url = f"{self.project['id']}/drawings/{dwg_id}"
            json_data = self.request(url, RequestType.GET, params=params)
            results.append(json_data["data"])
        return results

    def get_videos(self, video_ids=None, params=None):
        """Return video list based on specified ids"""
        if video_ids is None:
            return []

        if not self.project:
            raise ValueError("Project not set")

        results = []
        for vid_id in video_ids:
            url = f"{self.project['id']}/videos/{vid_id}"
            json_data = self.request(url, RequestType.GET, params=params)
            results.append(json_data["data"])
        return results

    def get_reports(self, report_ids=None, params=None):
        """Return report list based on specified ids"""
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

    def get_geotags(self, drawing_id=None, params=None):
        """Return annotation list based on specified ids"""
        if drawing_id is None:
            return []

        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/geotags?drawing_id={drawing_id}"
        json_data = self.request(url, RequestType.GET, params=params)

        return json_data["data"]

    ################################################################################################
    # Add / Upload methods
    ################################################################################################
    def add_annotations(self, payloads):
        """Add annotations"""
        results = []
        for payload in payloads:
            url = "annotation"
            res = self.request(url, RequestType.POST, data=payload)
            results.append(res)

        return results

    def add_assets(self, payload):
        """Add assets"""
        url = f"{self.project['id']}/assets/bulk.create"
        return self.request(url, RequestType.POST, data=payload)

    def upload_images(self, image_paths, image_type=1):
        """Upload images"""

        if not self.project:
            raise ValueError("Project not set")

        # Upload images to S3
        assets = []
        for file_path in image_paths:
            base, ext = os.path.splitext(os.path.basename(file_path))
            filename = f"{base}_{random_string(6)}{ext}"
            s3_path = (
                self.s3_base_url + f"/projects/{self.project['id']}/images/{filename}"
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
        payload = {
            "project_id": self.project["id"],
            "asset_type": 1,
            "image_type": image_type,
            "assets": assets,
        }
        return self.add_assets(payload)

    def upload_drawings(self, drawing_paths):
        """Upload drawings"""

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

    def upload_videos(self, video_paths):
        """Upload videos"""

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

    def upload_reports(self, report_paths):
        """Upload reports"""

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
