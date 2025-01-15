def get_attr_by_key_chain(obj, default=None, *keys):
    """
    Traverse a chain of keys or attributes to fetch a value from an object or dictionary.

    Args:
        obj: The object or dictionary to traverse.
        default: The default value to return if any key/attribute is not found.
        *keys: A sequence of keys or attribute names.

    Returns:
        The value found at the end of the key chain, or the default value.
    """
    for key in keys:
        try:
            if isinstance(obj, dict):
                obj = obj[key]
            else:
                obj = getattr(obj, key)
        except (KeyError, AttributeError, TypeError):
            return default
    return obj
