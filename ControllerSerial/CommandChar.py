from enum import Enum

class CommandChar(str, Enum):
    APRIL_TAG_SEARCH    = "A",
    MOVE_TO_POINTS      = "M",
    ROTATE              = "R",
    STOP                = "S",
    STOP_ACK            ="s",
    SEPARATOR = ":"