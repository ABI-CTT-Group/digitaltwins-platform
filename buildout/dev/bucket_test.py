import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import os

def test_s3_connection():
    # Configuration
    s3_client = boto3.client(
        's3',
        endpoint_url='https://swift.rc.nectar.org.au',
        aws_access_key_id='***',      # Replace with your access key
        aws_secret_access_key='***',  # Replace with your secret key
        region_name='us-east-1',
        config=Config(
            s3={
                'addressing_style': 'path'  # Force path-style addressing
            },
            signature_version='s3v4'
        )
    )
    
    try:
        # Test 1: List all buckets
        print("Listing all buckets...")
        response = s3_client.list_buckets()
        print(f"Found {len(response['Buckets'])} buckets:")
        for bucket in response['Buckets']:
            print(f"  - {bucket['Name']} (created: {bucket['CreationDate']})")
        
        # Test 2: List objects in specific bucket
        bucket_name = 'terraform-states'  # Replace with your bucket name
        print(f"\nListing objects in bucket '{bucket_name}'...")
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        
        if 'Contents' in response:
            print(f"Found {len(response['Contents'])} objects:")
            for obj in response['Contents']:
                print(f"  - {obj['Key']} (size: {obj['Size']} bytes, modified: {obj['LastModified']})")
        else:
            print("Bucket is empty or doesn't exist")
            
        # Test 3: Try to get bucket location (basic connectivity test)
        location = s3_client.get_bucket_location(Bucket=bucket_name)
        print(f"\nBucket location: {location}")
        
        print("\n✅ Connection successful!")
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"\n❌ Error: {error_code} - {error_message}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        return False

# Run the test
if __name__ == "__main__":
    test_s3_connection()
