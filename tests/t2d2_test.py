# pylint: disable=missing-docstring,line-too-long
import os
import unittest

from t2d2_sdk import T2D2, random_string

creds_api_key = {
    "api_key": os.getenv("T2D2_API_KEY", ""),
}
PROJECT_ID = 1


class T2D2APITests(unittest.TestCase):
    def setUp(self):
        # Initialize T2D2 object with dummy credentials
        self.t2d2 = T2D2(
            credentials=creds_api_key, base_url="http://localhost:4000/api/"
        )

    def test_random_string(self):
        # Test random_string function
        result = random_string(length=6)
        self.assertEqual(len(result), 6)

    def test_project(self):
        # Test project function
        project = self.t2d2.get_project(PROJECT_ID)
        self.assertEqual(project["id"], PROJECT_ID)

        self.t2d2.set_project(PROJECT_ID)
        self.assertEqual(self.t2d2.project["id"], PROJECT_ID)

    # Add more test cases for other functions...


if __name__ == "__main__":
    print("Running tests...")
    unittest.main()
