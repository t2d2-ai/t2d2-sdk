#!/usr/bin/env python3
"""
Test script for condition report service with project 705
"""
import os
import sys

from dotenv import load_dotenv
load_dotenv() 

# Add parent directory to path to import t2d2_sdk
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from t2d2_sdk import T2D2

# Configuration
BASE_URL = "https://api-v3.t2d2.ai/api"
PROJECT_ID = 790

def main():
    """Test condition report generation for project 705"""
    print("=" * 60)
    print("Testing Condition Report Service with Project 705")
    print("=" * 60)
    
    # Get API key from environment
    api_key = os.getenv("T2D2_API_KEY", "")
    if not api_key:
        print("ERROR: T2D2_API_KEY environment variable not set!")
        print("Please set it with: export T2D2_API_KEY='your_api_key'")
        return
    
    # Initialize T2D2 client
    print("\n[1/3] Initializing T2D2 client...")
    credentials = {"api_key": api_key}
    t2d2 = T2D2(credentials=credentials, base_url=BASE_URL)
    print("✓ Client initialized")
    
    # Set project
    print(f"\n[2/3] Setting project {PROJECT_ID}...")
    try:
        t2d2.set_project(PROJECT_ID)
        project_info = t2d2.get_project_info()
        print(f"✓ Project set: {project_info.get('name', 'N/A')}")
        print(f"  Project ID: {project_info.get('id', 'N/A')}")
        print(f"  Address: {project_info.get('address', 'N/A')}")
    except Exception as e:
        print(f"✗ Failed to set project: {e}")
        return

    t2d2_id = t2d2.get_images(image_ids=["694791"])
        
    t2d2_ann = t2d2.get_annotations(image_id=694791)
    print(t2d2_ann)
    
    # Summary
    print(f"\n[3/3] Test Summary")
    print("=" * 60)
    print(f"✓ Project: {project_info.get('name', 'N/A')} (ID: {PROJECT_ID})")
    print("=" * 60)
    print("\nTest completed successfully!")

if __name__ == "__main__":
    main()

