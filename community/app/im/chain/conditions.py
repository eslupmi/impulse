"""Community chains support unconditional steps only."""


def validate_step(step):
    # The schema maps YAML `if` to `condition`. Reject it so the step cannot run unconditionally.
    expression = step.get('if') if isinstance(step, dict) else getattr(step, 'condition', None)
    if expression is not None:
        raise ValueError("Conditional chain steps require the Enterprise edition")


def matches_step(step, _labels):
    validate_step(step)
    return True
