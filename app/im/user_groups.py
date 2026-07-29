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


def serialize_user_groups(user_groups):
    return {name: user_group.serialize() for name, user_group in user_groups.items()}


class UserGroup:
    def __init__(self, name, users):
        self.name = name
        self.users = users

    def serialize(self):
        return {
            'name': self.name,
            'users': [u.name for u in self.users],
        }
