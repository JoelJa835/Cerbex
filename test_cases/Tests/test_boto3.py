import boto3
s3 = boto3.client("s3")
# List buckets (will fail without credentials, but still exercises API)
try:
    print(s3.list_buckets())
except Exception as e:
    print("Expected error:", type(e).__name__)
