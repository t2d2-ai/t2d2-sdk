# pylint: disable=missing-docstring,line-too-long
import os
import random
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

# pylint: disable=import-error, wrong-import-position
from t2d2_sdk import T2D2, random_string

creds_api_key = {"api_key": os.getenv("T2D2_API_KEY", "")}
BASE_URL = "https://api-v3.t2d2.ai/api"
PROJECT_ID = 44


def gen_random_polygons(n=5):
    """Return random polygon points"""
    points = []
    for _ in range(n):
        points.append([random.random(), random.random()])
    return points


def gen_random_box():
    """Return random box points"""
    points = [
        0.1 + 0.05 * random.random(),
        0.2 + 0.05 * random.random(),
        0.4 + 0.05 * random.random(),
        0.8 + 0.05 * random.random(),
    ]
    return points


def generate_random_annotations(n=10):
    """Generate random annotations"""
    annotations = []
    for _ in range(n):
        annotations.append(
            {
                # "points": gen_random_polygons(),
                # "shape": 4,
                "points": gen_random_box(),
                "shape": 3,
                "annotation_class_name": "efflorescence",
            }
        )

    return annotations


class T2D2APITests(unittest.TestCase):
    def setUp(self):
        # Initialize T2D2 object with dummy credentials
        self.t2d2 = T2D2(credentials=creds_api_key, base_url=BASE_URL)
        self.t2d2.set_project(PROJECT_ID)

    def test_random_string(self):
        # Test random_string function
        result = random_string(length=6)
        self.assertEqual(len(result), 6)

    def test_project(self):
        # Test project function
        res = self.t2d2.get_project()
        project_count = res["total_projects"]
        # print("Total Projects: ", project_count)
        self.assertEqual(project_count, 427)

        project = self.t2d2.get_project(PROJECT_ID)
        self.assertEqual(project["id"], PROJECT_ID)

    def test_unauthorized(self):
        # Test unauthorized function
        t2d2 = T2D2(credentials={"api_key": "test"}, base_url=BASE_URL)
        t2d2.debug = False
        self.assertRaises(ValueError, t2d2.get_project, PROJECT_ID)

    def test_images(self):
        # Get Images
        images = self.t2d2.get_images(params={"image_types": [1, 2, 4]})
        self.assertEqual(len(images), 266)

        # Get Images
        orthos = self.t2d2.get_images(params={"image_types": [3]})
        self.assertEqual(len(orthos), 12)

    def test_annotations(self):
        # Test annotations function
        image_id = 330243
        params = {}

        res = self.t2d2.delete_annotations(image_id=330243)
        self.assertEqual(res["success"], True)

        annotations = self.t2d2.get_annotations(image_id=image_id, params=params)
        self.assertEqual(len(annotations), 0)

        anns = generate_random_annotations(n=10)
        # print(anns)
        res = self.t2d2.add_annotations(image_id=image_id, annotations=anns)
        self.assertEqual(res["success"], True)
        # print(res)

        annotations = self.t2d2.get_annotations(image_id=330243, params=params)
        self.assertEqual(len(annotations), 10)


if __name__ == "__main__":
    print("Running tests...")
    unittest.main()
