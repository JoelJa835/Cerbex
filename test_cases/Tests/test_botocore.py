import botocore.session
session = botocore.session.get_session()
print(session.get_config_variable("region"))
