class User:
    def __init__(self, id_, name, exists=False):
        self.name = name
        self.id = id_
        self.exists = exists

    def __repr__(self):
        return self.name
