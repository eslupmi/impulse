from app.logging import logger

_ENTITY_KEYS = ('user', 'user_group', 'group', 'webhook', 'chain', 'wait')


def _step_type_and_value(step) -> tuple[str, str]:
    if hasattr(step, 'get_type_and_value'):
        return step.get_type_and_value()
    for key in _ENTITY_KEYS:
        if isinstance(step, dict) and step.get(key) is not None:
            return key, step[key]
    raise ValueError("Chain step has no valid type or value set")


def filter_undeclared_steps(
    chain_name: str,
    steps: list | None,
    users: dict | None = None,
    user_groups: dict | None = None,
    groups: dict | None = None,
    webhooks: dict | None = None,
    chains: dict | None = None,
) -> list:
    if not steps:
        return steps or []
    registries = {
        'user': users or {},
        'user_group': user_groups or {},
        'group': groups or {},
        'webhook': webhooks or {},
        'chain': chains or {},
    }
    filtered = []
    for step in steps:
        type_, value = _step_type_and_value(step)
        if type_ == 'wait':
            filtered.append(step)
            continue
        if value not in registries[type_]:
            logger.warning(
                'Chain step entity not declared',
                extra={'chain': chain_name, type_: value},
            )
            continue
        filtered.append(step)
    return filtered
