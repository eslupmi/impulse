from app.logging import logger


def check_channels(channels_list, channels_config, default_channel):
    logger.info(f'Checking all channels defined')
    for channel in channels_list:
        if channel not in channels_config.keys():
            logger.warning(f'.. channel {channel} not defined. Using default channel instead')
            channels_config[channel] = {'id': channels_config.get(default_channel)['id']}
        else:
            if 'id' not in channels_config[channel]:
                logger.warning(f'.. channel \'{channel}\' has no \'id\'. Using default channel instead')
                channels_config[channel] = {'id': channels_config.get(default_channel)['id']}
            elif channels_config[channel].get('id') is None:
                logger.warning(f'.. channel {channel} \'id\' is empty. Using default channel instead')
                channels_config[channel] = {'id': channels_config.get(default_channel)['id']}
    return channels_config
