from typing import Dict, Optional, List

from app.logging import logger


class ChannelManager:
    """Singleton to manage channel data mapping."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChannelManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._channels: Dict[str, Dict] = {}
    
    def initialize(self, channels_list: List[str], channels_config: Dict[str, Dict], default_channel: str) -> Dict[str, Dict]:
        logger.info('Checking all channels defined')
        
        for channel in channels_list:
            if channel not in channels_config:
                logger.warning(f'.. channel {channel} not defined. Using default channel instead')
                channels_config[channel] = {'id': channels_config.get(default_channel)['id']}
            else:
                if 'id' not in channels_config[channel]:
                    logger.warning(f'.. channel \'{channel}\' has no \'id\'. Using default channel instead')
                    channels_config[channel] = {'id': channels_config.get(default_channel)['id']}
                elif channels_config[channel].get('id') is None:
                    logger.warning(f'.. channel {channel} \'id\' is empty. Using default channel instead')
                    channels_config[channel] = {'id': channels_config.get(default_channel)['id']}
        
        self._channels.clear()
        for channel_name, channel_data in channels_config.items():
            channel_id = channel_data['id']
            self._channels[channel_id] = {
                'id': channel_id,
                'name': channel_name,
                **{k: v for k, v in channel_data.items() if k != 'id'}
            }
        
        return channels_config
    
    def get_channel_name_by_id(self, channel_id: str) -> Optional[str]:
        channel_data = self._channels.get(channel_id)
        return channel_data['name'] if channel_data else None
