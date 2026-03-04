from typing import Union

from app.config.validation import ChainType, CloudChain, ScheduleChain as ScheduleChainType
from app.im.chain.chain import Chain
from app.im.chain.google_calendar_chain import GoogleCalendarChain
from app.im.chain.schedule_chain import ScheduleChain
from app.logging import logger


class ChainFactory:
    ### PRIVATE METHODS ###

    @staticmethod
    def _create_chain(name: str, config: Union[ScheduleChainType, CloudChain, list]):
        """
        Create and return a Chain, ScheduleChain or GoogleCalendarChain instance 
        based on the configuration.
        """
        if hasattr(config, 'type'):
            if config.type == ChainType.CLOUD and config.provider == 'google':
                try:
                    chain = GoogleCalendarChain(name, config)
                    if isinstance(chain, GoogleCalendarChain):
                        chain.start_sync()
                    return chain
                except Exception as e:
                    logger.error(f"Failed to create GoogleCalendarChain '{name}': {e}")
                    return None
            elif config.type == ChainType.SCHEDULE:
                try:
                    return ScheduleChain(
                        name=name,
                        timezone_=config.timezone,
                        schedule=config.schedule,
                    )
                except Exception as e:
                    logger.error(f"Failed to create ScheduleChain '{name}': {e}")
                    return None
            else:
                logger.error(f"Unknown chain type '{config.type.value }' for chain '{name}'. Check impulse.yml")
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
