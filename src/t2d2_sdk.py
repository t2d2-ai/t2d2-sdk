"""T2D2 SDK API wrapper"""

import json
import os
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

    def notify_user(self, title, message):
        """Notify user"""
        url = "notifications"
        payload = {"title": title, "message": message}
        return self.request(url, RequestType.POST, data=payload)

    ################################################################################################
    # Project Get/Set
    ################################################################################################
    def get_project(self, project_id=None):
        """Return project list"""
        if project_id is None:
            url = "project"
        else:
            url = f"project/{project_id}"
        json_data = self.request(url, RequestType.GET)
        return json_data["data"]

    def set_project(self, project_id):
        """Set project by project_id"""
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
        """Return project info"""
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
    def add_region(self, region_name:str):
        """Add region to project"""
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/categories/regions"
        json_data = self.request(url, RequestType.POST, data={'name': region_name})
        return json_data    

    ################################################################################################
    # CRUD Assets
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

    def add_assets(self, payload):
        """Add assets"""
        url = f"{self.project['id']}/assets/bulk.create"
        return self.request(url, RequestType.POST, data=payload)

    def download_assets(
        self, asset_ids, asset_type=1, download_dir="./", original_filename=False
    ):
        """Download assets"""
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
        """Upload images"""

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
        """Return image list based on specified ids"""
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
        """Update images"""
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/images/bulk.update"
        payload["image_ids"] = image_ids
        payload["project_id"] = self.project["id"]
        return self.request(url, RequestType.PUT, data=payload)

    def delete_images(self, image_ids):
        """Delete images"""
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/images/bulk.delete"
        payload = {"image_ids" : image_ids}
        return self.request(url, RequestType.DELETE, data=payload)

    ################################################################################################
    # CRUD Drawings
    ################################################################################################
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

    def get_drawings(self, drawing_ids=None, params=None):
        """Return drawing list based on specified ids"""
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
        """Update images"""
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/drawings/bulk.update"
        payload["drawing_ids"] = drawing_ids
        payload["project_id"] = self.project["id"]
        return self.request(url, RequestType.PUT, data=payload)

    def delete_drawings(self, drawing_ids):
        """Delete drawings"""
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/drawings/bulk.delete"
        payload = {"drawing_ids" : drawing_ids}
        return self.request(url, RequestType.DELETE, data=payload)

    ################################################################################################
    # CRUD Videos
    ################################################################################################
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

    def get_videos(self, video_ids=None, params=None):
        """Return video list based on specified ids"""
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
        """Update videos"""
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/videos/bulk.update"
        payload["video_ids"] = video_ids
        payload["project_id"] = self.project["id"]
        return self.request(url, RequestType.PUT, data=payload)

    def delete_videos(self, video_ids):
        """Delete drawings"""
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/videos/bulk.delete"
        payload = {"video_ids" : video_ids}
        return self.request(url, RequestType.DELETE, data=payload)

    ################################################################################################
    # CRUD 3D
    ################################################################################################
    def upload_threed(self, threed_paths):
        """Upload 3d"""

        if not self.project:
            raise ValueError("Project not set")

        # Upload images to S3
        assets = []
        for file_path in threed_paths:
            base, ext = os.path.splitext(os.path.basename(file_path))
            filename = f"{base}_{random_string(6)}{ext}"
            s3_path = (
                self.s3_base_url + f"/projects/{self.project['id']}/3d_models/{filename}"
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
        """Return video list based on specified ids"""
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
        payload = {"model_ids" : model_ids}
        return self.request(url, RequestType.DELETE, data=payload)

    ################################################################################################
    # CRUD Reports
    ################################################################################################
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

    # TODO: Delete / Update Reports
    ################################################################################################
    # CRUD Tags
    ################################################################################################
    def get_tags(self, params=None):
        """Return tag list"""
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/tags"
        json_data = self.request(url, RequestType.GET, params=params)
        return json_data["data"]

    def add_tags(self, tags):
        """Add tags"""
        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/tags"
        if isinstance(tags, str):
            tags = [tags]

        results = []
        for tag in tags:
            payload = {"name": tag}
            try:
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
        """Return material list"""
        if not self.project:
            raise ValueError("Project not set")

        url = "material"
        params = {"project_id": self.project["id"]}
        json_data = self.request(url, RequestType.GET, params=params)
        return json_data["data"]

    def get_annotation_classes(self, params=None):
        """Return annotation class list"""
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
        """Add annotation class"""
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
        """Delete annotation class"""
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
        """TODO: Return annotation list based on specified ids"""
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
        """Delete annotations"""

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
        """TODO: Add annotations"""
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
        """Return annotation list based on specified ids"""
        if drawing_id is None:
            return []

        if not self.project:
            raise ValueError("Project not set")

        url = f"{self.project['id']}/geotags?drawing_id={drawing_id}"
        json_data = self.request(url, RequestType.GET, params=params)

        return json_data["data"]

    def add_geotags(self, drawing_id, geotags):
        """Add geotags"""
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
        """Delete geotags"""
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
        """Upload downloads to project folder"""

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
            img_region = img["region"]['name']
            img_date = ts2date(img["captured_date"]).split(' ')[0]
            img_tags = img["tags"]

            region_group[img_region] += 1
            date_group[img_date] += 1
            for img_tag in img_tags:
                tag_group[img_tag['name']] += 1

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
            reg = img['region']['name']
            anns_img = self.get_annotations(image_id=img['id'])
            anns[reg] += anns_img

        result = {}
        for reg, annotations in anns.items():
            sublist = {}
            for ann in annotations:
                label = ann['annotation_class']['annotation_class_name']
                rating = ann.get('condition', {}).get('rating_name', 'default')
                area = ann['area']
                length = ann['length']
                ann_id = ann['id']
                key = (label, rating)
                if key in sublist:
                    sublist[key]['count'] += 1
                    sublist[key]['length'] += length
                    sublist[key]['area'] += area
                    sublist[key]['annotation_ids'].append(ann_id)
                else:
                    sublist[key] = {}
                    sublist[key]['count'] = 1
                    sublist[key]['length'] = length
                    sublist[key]['area'] = area
                    sublist[key]['annotation_ids'] = []
                    
            result[reg] = sublist

        return result