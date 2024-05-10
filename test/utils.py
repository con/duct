from io import BytesIO


class MockStdout:
    def __init__(self):
        self.buffer = BytesIO()

    def write(self, text):
        self.buffer.write(text.encode())

    def getvalue(self):
        return self.buffer.getvalue()
