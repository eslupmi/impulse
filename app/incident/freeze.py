from enum import Enum


class FreezeSource(str, Enum):
    TIME = "time"
    PARENT = "parent"
    MAINTENANCE = "maintenance"
    ALL = "all"


MAINTENANCE_PARENT_SENTINEL = FreezeSource.MAINTENANCE.value
