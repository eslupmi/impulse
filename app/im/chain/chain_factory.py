from app.config.validation import CloudChain
from app.config.validation import ScheduleChain as ScheduleChainType
from app.im.chain.chain import Chain
from app.im.chain.filter_steps import filter_undeclared_steps
from app.im.chain.google_calendar_chain import GoogleCalendarChain
from app.im.chain.schedule_chain import ScheduleChain
from app.logging import logger


class ChainFactory:
    ### PRIVATE METHODS ###

    @staticmethod
    def _filter_schedule(name: str, schedule, registries: dict):
        return [
            entry.model_copy(update={
                'steps': filter_undeclared_steps(name, entry.steps, **registries),
            })
            for entry in schedule
        ]

    @classmethod
    def _create_chain(cls, name: str, config: ScheduleChainType | CloudChain | list, registries: dict):
        if isinstance(config, dict) and config.get('type') == 'ui':
            return None
        if isinstance(config, CloudChain) and config.provider == 'google':
            filtered = config.model_copy(update={
                'default_steps': filter_undeclared_steps(name, config.default_steps, **registries),
            })
            chain = GoogleCalendarChain(name, filtered, registries=registries)
            chain.start_sync()
            return chain
        if isinstance(config, ScheduleChainType):
            return ScheduleChain(
                name=name,
                timezone_=config.timezone,
                schedule=cls._filter_schedule(name, config.schedule, registries),
            )
        if isinstance(config, list):
            return Chain(name, filter_undeclared_steps(name, config, **registries))
        raise ValueError(f"Unknown chain type '{config.type.value}' for chain '{name}'. Check impulse.yml")

    @classmethod
    def generate(cls, chains_dict, users=None, user_groups=None, groups=None, webhooks=None):
        logger.info('Creating chains')
        registries = {
            'users': users or {},
            'user_groups': user_groups or {},
            'groups': groups or {},
            'webhooks': webhooks or {},
            'chains': chains_dict or {},
        }
        chains = {}
        for name, config in chains_dict.items():
            try:
                chain = cls._create_chain(name, config, registries)
                if chain is not None:
                    chains[name] = chain
                else:
                    logger.warning(f"Skipping chain '{name}' because it is handled outside runtime chain creation")
            except Exception as e:  # noqa: BLE001
                logger.exception(f"Failed to create chain '{name}'")
                logger.warning(f"Skipping chain '{name}' due to creation failure: {e}")
        return chains
