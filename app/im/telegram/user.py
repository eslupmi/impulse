from app.im.telegram.config import telegram_env, telegram_admins_template_string


class User:
    def __init__(self, id_, name, username):
        self.id = id_
        self.name = name
        self.username = username

    def __repr__(self):
        return self.username

    def mention_text(self, admins_usernames):
        if self.name is not None:
            text = f'➤ user [{self.username}](tg://user?id={self.id}): '
            text += f'{self.name}'
        else:
            text = f'➤ user [{self.username}](tg://user?id={self.id}): '
            admins_text = telegram_env.from_string(telegram_admins_template_string).render(users=admins_usernames)
            text += (f'not found in Telegram\n'
                     f'➤ admins: {admins_text}')
        return text
