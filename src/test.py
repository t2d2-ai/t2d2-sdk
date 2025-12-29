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
PROJECT_ID = 705

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
    print("\n[1/4] Initializing T2D2 client...")
    credentials = {"api_key": api_key}
    t2d2 = T2D2(credentials=credentials, base_url=BASE_URL)
    print("✓ Client initialized")
    
    # Set project
    print(f"\n[2/4] Setting project {PROJECT_ID}...")
    try:
        t2d2.set_project(PROJECT_ID)
        project_info = t2d2.get_project_info()
        print(f"✓ Project set: {project_info.get('name', 'N/A')}")
        print(f"  Project ID: {project_info.get('id', 'N/A')}")
        print(f"  Address: {project_info.get('address', 'N/A')}")
    except Exception as e:
        print(f"✗ Failed to set project: {e}")
        return
    
    # Generate condition report
    print(f"\n[3/4] Generating condition report document...")
    output_path = "condition_report_project_705.docx"
    try:
        doc_path = t2d2.generate_condition_report_document(
            image_ids=None,  # Include all images
            output_path=output_path,
            padding_percent=0.2
        )
        print(f"✓ Condition report generated successfully!")
        print(f"  Output file: {doc_path}")
    except Exception as e:
        print(f"✗ Failed to generate condition report: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Summary
    print(f"\n[4/4] Test Summary")
    print("=" * 60)
    print(f"✓ Project: {project_info.get('name', 'N/A')} (ID: {PROJECT_ID})")
    print(f"✓ Condition report saved to: {doc_path}")
    print("=" * 60)
    print("\nTest completed successfully!")

if __name__ == "__main__":
    main()

