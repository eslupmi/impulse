"""Queue-related constants"""


class QueueItemType:
    """Constants for queue item types"""
    UPDATE_STATUS = 'update_status'
    STATUS_CHECK = 'status_check'
    UPDATE_MESSAGE = 'update_message'
    CHAIN_STEP = 'chain_step'
    ALERT = 'alert'
    UNFREEZE = 'unfreeze'
    UPDATE_USER = 'update_user'
    MAINTENANCE_START = 'maintenance_start'


USER_UPDATE_GAP_SECONDS = {
    'slack': 1.0,
    'mattermost': 2.0,
    'telegram': 60.0,
}
