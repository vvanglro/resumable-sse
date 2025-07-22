from enum import Enum


class ChatState(str, Enum):
    START = "start"
    GENERATING = "generating"
    STREAMING = "streaming"
    END = "end"
    DONE = "done"

    def __str__(self) -> str:
        return self.value
