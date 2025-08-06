# test_module.py

async def read_items(token=None):
    """
    Dummy async function to validate your async wrapper/importer logic.
    """
    return {"token": token}

def get_data(x, y):
    """
    Dummy sync function to validate your sync wrapper/importer logic.
    """
    return x + y
