# config.py
class Config:
    def __init__(self):
        self.host = "localhost"
        self.port = 8080
        self.debug = True
        self.timeout = 30

    def url(self):
        return f"http://{self.host}:{self.port}/"