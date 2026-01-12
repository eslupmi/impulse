class Group:
    """Common Group class for Slack and Mattermost"""
    def __init__(self, config_name, name=None, id_=None, exists=False):
        self.config_name = config_name  # Name from impulse.yml config
        self.name = name  # Real name from messenger API (if exists)
        self.id = id_
        self.exists = exists
        self.defined = True

    def __repr__(self):
        return self.name if self.name else self.config_name
