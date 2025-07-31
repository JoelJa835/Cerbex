from s3transfer.manager import TransferManager
from botocore.session import get_session
from botocore.client import Config

session = get_session()
client = session.create_client("s3", config=Config(signature_version="s3v4"))
mgr = TransferManager(client)
mgr.shutdown()
print("TransferManager created and shut down.")
