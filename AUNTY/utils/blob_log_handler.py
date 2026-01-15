import logging
from io import StringIO


class InMemoryLogHandler(logging.Handler):
    """
    Captures logs in memory so they can be uploaded to Blob Storage.
    """

    def __init__(self):
        super().__init__()
        self.buffer = StringIO()

    def emit(self, record):
        msg = self.format(record)
        self.buffer.write(msg + "\n")

    def get_value(self) -> str:
        return self.buffer.getvalue()

    def clear(self):
        self.buffer = StringIO()
