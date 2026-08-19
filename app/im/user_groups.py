from app.logging import logger


def generate_user_groups(user_groups_dict=None, users=None):
    user_groups = {}
    if user_groups_dict:
        logger.info('Creating user_groups')
        for name in user_groups_dict:
            user_names = []
            for user_name in user_groups_dict[name].users:
                if users.get(user_name) is None:
                    logger.warning('User not found', extra={'user': user_name, 'user_group': name})
                    continue
                user_names.append(user_name)
            user_groups[name] = UserGroup(name, user_names)
    return user_groups


class UserGroup:
    def __init__(self, name, users):
        self.name = name
        self.users = users

    def serialize(self):
        return {
            'users': self.users,
        }
