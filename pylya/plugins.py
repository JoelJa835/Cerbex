from lyapy import Analysis

class CallLogger(Analysis):
    def __init__(self):
        self.log = []

    def on_call(self, module, func, args, kwargs):
        self.log.append(f"CALL {module}.{func}{args}{kwargs}")

    def on_return(self, module, func, result):
        self.log.append(f"RET  {module}.{func} -> {result}")
