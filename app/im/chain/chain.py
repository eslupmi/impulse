class Chain:
    def __init__(self, name: str, steps: list):
        self.name = name
        self.steps = steps

    def __repr__(self):
        return self.name
