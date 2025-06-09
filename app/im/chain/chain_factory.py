from typing import Union

from app.im.chain.chain import Chain
from app.im.chain.schedule_chain import ScheduleChain
from app.im.chain.google_calendar_chain import GoogleCalendarChain
from app.logging import logger


class ChainFactory:
    @staticmethod
    def _create_chain(name: str, config: Union[dict, list]):
        """
        Create and return a Chain, ScheduleChain or GoogleCalendarChain instance 
        based on the configuration.
        """
        if 'type' in config:
            if config.get('type') == 'cloud' and config.get('provider') == 'google':
                try:
                    chain = GoogleCalendarChain(name, config)
                    if isinstance(chain, GoogleCalendarChain):
                        chain.start_sync()
                    return chain
                except Exception as e:
                    logger.error(f"Failed to create GoogleCalendarChain '{name}': {e}")
                    return None
            elif config.get('type') == 'schedule':
                try:
                    return ScheduleChain(
                        name=name,
                        timezone=config.get('timezone', ScheduleChain.DEFAULT_TIMEZONE),
                        schedule=config.get('schedule', []),
                    )
                except Exception as e:
                    logger.error(f"Failed to create ScheduleChain '{name}': {e}")
                    return None
            else:
                logger.error(f"Unknown chain type '{config.get('type')}' for chain '{name}'. Check impulse.yml")
                return None
        else:
            try:
                return Chain(name, config)
            except Exception as e:
                logger.error(f"Failed to create Chain '{name}': {e}")
                return None

    @classmethod
    def generate(cls, chains_dict):
        logger.info('Creating chains')
        chains = {}
        for name, config in chains_dict.items():
            chain = cls._create_chain(name, config)
            if chain is not None:
                chains[name] = chain
            else:
                logger.warning(f"Skipping chain '{name}' due to creation failure")
        return chains
