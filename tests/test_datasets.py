# pylint: disable=missing-docstring,line-too-long
import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

# pylint: disable=import-error, wrong-import-position
from t2d2_sdk import T2D2

# Configuration
creds_api_key = {"api_key": os.getenv("T2D2_API_KEY", "")}
BASE_URL = "https://api-v3.t2d2.ai/api"
PROJECT_ID = 705  # Update this with your actual project ID


class T2D2DatasetTests(unittest.TestCase):
    """Test cases for T2D2 Dataset API methods"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        # Initialize T2D2 object with API key credentials
        self.t2d2 = T2D2(credentials=creds_api_key, base_url=BASE_URL)
        self.t2d2.set_project(PROJECT_ID)
        
        # Store created dataset IDs for cleanup
        self.created_datasets = []
        
    def tearDown(self):
        """Clean up after each test method"""
        # Clean up any datasets created during tests
        if self.created_datasets:
            try:
                self.t2d2.delete_datasets(self.created_datasets)
                print(f"Cleaned up {len(self.created_datasets)} test datasets")
            except Exception as e:
                print(f"Warning: Failed to clean up datasets: {e}")
            finally:
                self.created_datasets = []

    def test_get_datasets(self):
        """Test retrieving all datasets"""
        print("\n=== Testing get_datasets ===")
        
        # Test getting all datasets
        datasets = self.t2d2.get_datasets()
        
        # Verify response structure
        self.assertIn("dataset_list", datasets)
        self.assertIn("total_datasets", datasets)
        self.assertIsInstance(datasets["dataset_list"], list)
        self.assertIsInstance(datasets["total_datasets"], int)
        
        print(f"Found {datasets['total_datasets']} total datasets")
        
        # Test with filtering parameters
        filtered_datasets = self.t2d2.get_datasets(params={
            "search": "",
            "sortBy": "id:desc",
            "page": 1,
            "limit": 10,
            "public": False
        })
        
        self.assertIn("dataset_list", filtered_datasets)
        self.assertIn("total_datasets", filtered_datasets)
        print(f"Filtered datasets: {len(filtered_datasets['dataset_list'])}")

    def test_create_dataset(self):
        """Test creating a new dataset"""
        print("\n=== Testing create_dataset ===")
        
        # Create a test dataset
        dataset_name = f"test_dataset_{os.getpid()}"
        created_dataset = self.t2d2.create_dataset(dataset_name)
        
        # Verify response structure
        self.assertIn("id", created_dataset)
        self.assertIn("name", created_dataset)
        self.assertIn("created_by", created_dataset)
        self.assertIn("created_at", created_dataset)
        self.assertIn("image_ids", created_dataset)
        
        # Verify dataset properties
        self.assertEqual(created_dataset["name"], dataset_name)
        self.assertEqual(created_dataset["image_ids"], [])
        self.assertFalse(created_dataset.get("public", True))  # Should be private by default
        
        # Store for cleanup
        self.created_datasets.append(created_dataset["id"])
        
        print(f"Created dataset: {created_dataset['name']} with ID: {created_dataset['id']}")
        
        return created_dataset

    def test_delete_datasets(self):
        """Test deleting datasets"""
        print("\n=== Testing delete_datasets ===")
        
        # First create a dataset to delete
        dataset_name = f"delete_test_{os.getpid()}"
        created_dataset = self.t2d2.create_dataset(dataset_name)
        dataset_id = created_dataset["id"]
        
        print(f"Created dataset {dataset_id} for deletion test")
        
        # Delete the dataset
        delete_response = self.t2d2.delete_datasets([dataset_id])
        
        # Verify deletion response
        self.assertTrue(delete_response["success"])
        self.assertIn("message", delete_response)
        self.assertIn("deleted", delete_response["message"].lower())
        
        print(f"Delete response: {delete_response['message']}")
        
        # Verify dataset is actually deleted by trying to get datasets
        datasets = self.t2d2.get_datasets()
        dataset_ids = [d["id"] for d in datasets["dataset_list"]]
        self.assertNotIn(dataset_id, dataset_ids)
        
        print(f"Verified dataset {dataset_id} was deleted")

    def test_update_dataset_images_add(self):
        """Test adding images to a dataset"""
        print("\n=== Testing update_dataset_images (add) ===")
        
        # Create a test dataset
        dataset_name = f"add_images_test_{os.getpid()}"
        created_dataset = self.t2d2.create_dataset(dataset_name)
        dataset_id = created_dataset["id"]
        self.created_datasets.append(dataset_id)
        
        print(f"Created dataset {dataset_id} for image addition test")
        
        # Get some images from the project to add to dataset
        images = self.t2d2.get_images(params={"limit": 2})
        
        if len(images) == 0:
            self.skipTest("No images available in project for testing")
        
        # Use first image for testing
        test_image_id = images[0]["id"]
        print(f"Using image {test_image_id} for testing")
        
        # Add image to dataset
        updated_dataset = self.t2d2.update_dataset_images(
            dataset_id, "add", [test_image_id]
        )
        
        # Verify the image was added
        self.assertIn(test_image_id, updated_dataset["image_ids"])
        self.assertGreater(updated_dataset["image_size"], 0)
        
        print(f"Successfully added image {test_image_id} to dataset")
        print(f"Dataset now has {len(updated_dataset['image_ids'])} images")
        
        return dataset_id, test_image_id

    def test_update_dataset_images_remove(self):
        """Test removing images from a dataset"""
        print("\n=== Testing update_dataset_images (remove) ===")
        
        # First add an image to a dataset
        dataset_id, test_image_id = self.test_update_dataset_images_add()
        
        print(f"Testing removal of image {test_image_id} from dataset {dataset_id}")
        
        # Remove the image from dataset
        updated_dataset = self.t2d2.update_dataset_images(
            dataset_id, "remove", [test_image_id]
        )
        
        # Verify the image was removed
        self.assertNotIn(test_image_id, updated_dataset["image_ids"])
        self.assertEqual(updated_dataset["image_size"], 0)
        
        print(f"Successfully removed image {test_image_id} from dataset")
        print(f"Dataset now has {len(updated_dataset['image_ids'])} images")

    def test_update_dataset_images_invalid_action(self):
        """Test update_dataset_images with invalid action"""
        print("\n=== Testing update_dataset_images (invalid action) ===")
        
        # Create a test dataset
        dataset_name = f"invalid_action_test_{os.getpid()}"
        created_dataset = self.t2d2.create_dataset(dataset_name)
        dataset_id = created_dataset["id"]
        self.created_datasets.append(dataset_id)
        
        # Test with invalid action
        with self.assertRaises(ValueError) as context:
            self.t2d2.update_dataset_images(dataset_id, "invalid_action", [123])
        
        self.assertIn("Action must be either 'add' or 'remove'", str(context.exception))
        print("Correctly raised ValueError for invalid action")

    def test_dataset_workflow(self):
        """Test complete dataset workflow: create -> add images -> remove images -> delete"""
        print("\n=== Testing Complete Dataset Workflow ===")
        
        # Step 1: Create dataset
        dataset_name = f"workflow_test_{os.getpid()}"
        created_dataset = self.t2d2.create_dataset(dataset_name)
        dataset_id = created_dataset["id"]
        
        print(f"Step 1: Created dataset {dataset_id}")
        
        # Step 2: Get images to add
        images = self.t2d2.get_images(params={"limit": 3})
        
        if len(images) < 2:
            self.skipTest("Not enough images available for workflow test")
        
        image_ids = [img["id"] for img in images[:2]]
        print(f"Step 2: Selected images {image_ids} for testing")
        
        # Step 3: Add images to dataset
        updated_dataset = self.t2d2.update_dataset_images(dataset_id, "add", image_ids)
        self.assertEqual(len(updated_dataset["image_ids"]), 2)
        print(f"Step 3: Added {len(image_ids)} images to dataset")
        
        # Step 4: Remove one image
        updated_dataset = self.t2d2.update_dataset_images(
            dataset_id, "remove", [image_ids[0]]
        )
        self.assertEqual(len(updated_dataset["image_ids"]), 1)
        self.assertEqual(updated_dataset["image_ids"][0], image_ids[1])
        print(f"Step 4: Removed one image, dataset now has {len(updated_dataset['image_ids'])} images")
        
        # Step 5: Delete dataset
        delete_response = self.t2d2.delete_datasets([dataset_id])
        self.assertTrue(delete_response["success"])
        print(f"Step 5: Deleted dataset {dataset_id}")
        
        print("✅ Complete workflow test passed!")


def run_dataset_tests():
    """Run all dataset tests"""
    print("=" * 60)
    print("T2D2 Dataset API Tests")
    print("=" * 60)
    
    # Check if API key is available
    
   
    print(f"✅ Using base URL: {BASE_URL}")
    print()
    
    # Run tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    return True


if __name__ == "__main__":
    run_dataset_tests()
