import s3fs
fs = s3fs.S3FileSystem(anon=True)
try:
    print(fs.ls("s3://noaa-nexrad-level2/2020/"))
except Exception as e:
    print("Expected:", type(e).__name__)
