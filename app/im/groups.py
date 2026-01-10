from app.im.users import UndefinedUser
from app.logging import logger


def generate_user_groups(user_groups_dict=None, users=None):
    user_groups = {}
    if user_groups_dict:
        logger.info('Creating user_groups')
        for name in user_groups_dict.keys():
            user_names = user_groups_dict[name].users
            user_objects = []
            for user_name in user_names:
                user_object = users.get(user_name, UndefinedUser(user_name))
                user_objects.append(user_object)
            user_groups[name] = UserGroup(name, user_objects)
    return user_groups


class UserGroup:
    def __init__(self, name, users):
        self.name = name
        self.users = users


class Group:
    """Common Group class for Slack and Mattermost"""
    def __init__(self, name, id_=None, exists=False):
        self.name = name
        self.id = id_
        self.exists = exists
        self.defined = True

    def __repr__(self):
        return self.name
