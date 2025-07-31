import asyncio
import aiobotocore.session

async def main():
    session = aiobotocore.session.get_session()
    async with session.create_client("s3", region_name="us-east-1") as client:
        try:
            await client.list_buckets()
        except Exception as e:
            print("Expected:", type(e).__name__)

asyncio.run(main())
