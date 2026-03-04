from typing import Dict, Optional, List, Union

from app.config.validation import SlackChannel, MattermostChannel, TelegramChannel
from app.logging import logger


class ChannelManager:
    """Singleton to manage channel data mapping."""
    
    _instance = None
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._channels: Dict[str, Dict] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChannelManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def get_channel_name_by_id(self, channel_id: str) -> Optional[str]:
        channel_data = self._channels.get(channel_id)
        return channel_data['name'] if channel_data else None
    
    def initialize(self, channels_list: List[str], channels_config: Dict[str, Union[SlackChannel, MattermostChannel, TelegramChannel, Dict]], default_channel: str) -> Dict[str, Dict]:
        logger.debug('Checking all channels defined')
        
        channels_dict = {}
        
        for channel in channels_list:
            if channel not in channels_config:
                logger.warning('Channel not defined', extra={'channel': channel})
                default_channel_obj = channels_config.get(default_channel)
                if default_channel_obj:
                    default_id = self._get_channel_id(default_channel_obj)
                    channels_dict[channel] = {'id': default_id}
                else:
                    logger.error('Default channel not found in configuration', extra={'channel': default_channel})
                    channels_dict[channel] = {'id': default_channel}
            else:
                channel_obj = channels_config[channel]
                channel_id = self._get_channel_id(channel_obj)
                
                if channel_id is None:
                    logger.warning('Channel has no `id`. Using default channel instead', extra={'channel': channel})
                    default_channel_obj = channels_config.get(default_channel)
                    if default_channel_obj:
                        default_id = self._get_channel_id(default_channel_obj)
                        channels_dict[channel] = {'id': default_id}
                    else:
                        logger.error('Default channel not found in configuration', extra={'channel': default_channel})
                        channels_dict[channel] = {'id': channel}
                else:
                    channel_dict = {'id': channel_id}
                    if hasattr(channel_obj, 'name') and getattr(channel_obj, 'name', None):
                        channel_dict['name'] = channel_obj.name
                    channels_dict[channel] = channel_dict
        
        self._channels.clear()
        for channel_name, channel_data in channels_dict.items():
            channel_id = channel_data['id']
            self._channels[channel_id] = {
                'id': channel_id,
                'name': channel_name,
                **{k: v for k, v in channel_data.items() if k != 'id'}
            }
        
        return channels_dict

    ### PRIVATE METHODS ###

    @staticmethod
    def _get_channel_id(channel_obj):
        """Extract channel ID from either a typed channel object or a dictionary"""
        if hasattr(channel_obj, 'id'):
            return channel_obj.id
        elif isinstance(channel_obj, dict):
            return channel_obj.get('id')
        else:
            return None
