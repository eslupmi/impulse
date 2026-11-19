# Authentication

IMPulse supports authentication through all supported messengers.

## How to enable

See instruction in corresponding messenger article:

=== "Slack"

    [Instruction](../integrations/messengers/slack.md#authentication)

=== "Mattermost"

    [Instruction](../integrations/messengers/mattermost.md#authentication)

=== "Telegram"

    [Instruction](../integrations/messengers/telegram.md#authentication)

## Session lifetime

UI sessions expire 90 days after login. Activity does not extend this lifetime; signing out ends the current session immediately.

IMPulse automatically removes expired session records when an instance becomes primary, then waits eight hours between passes. This applies to filesystem and S3 storage, including sessions on devices that are no longer used. Expired sessions are rejected immediately, even before the next cleanup pass.
