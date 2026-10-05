"""Impulse-owned business actions for verified provider interactions."""
import asyncio
from dataclasses import replace

from impulse_messenger_api import InteractionAction
from app.logging import logger

async def apply_interaction(application, interaction, incidents, queue):
    async def finish_early():
        acknowledge = getattr(application.provider, 'acknowledge_interaction', None)
        if acknowledge is not None:
            await acknowledge(interaction)
        return interaction.original_response

    incident = incidents.get_by_ts(ts=interaction.message.thread_id, channel_id=interaction.message.channel_id)
    if incident is None:
        return await finish_early()
    if interaction.message.channel_id and str(incident.channel_id) != str(interaction.message.channel_id):
        return await finish_early()
    has_freeze = any(command.action in (InteractionAction.FREEZE, InteractionAction.UNFREEZE, InteractionAction.SHOW_FREEZE_OPTIONS)
                     for command in interaction.commands)
    if incident.is_frozen and (not has_freeze or (
            incident.frozen_by_inhibition and not application.provider.descriptor.allow_inhibited_freeze_actions)):
        return await finish_early()
    user_id = interaction.actor_id
    timezone = application._get_user_timezone_str(user_id)
    menu_unfroze = False
    for command in interaction.commands:
        if command.action == InteractionAction.FREEZE:
            if incident.can_manual_unfreeze():
                await application._handle_unfreeze_action(incident, user_id, queue)
            elif command.freeze_option:
                await application._handle_freeze_action(incident, command.freeze_option, user_id,
                                                       queue, user_timezone=timezone)
        elif command.action == InteractionAction.SHOW_FREEZE_OPTIONS:
            if incident.can_manual_unfreeze():
                await application._handle_unfreeze_action(incident, user_id, queue)
                # The presentation is built after unfreeze, so this command must not open the menu.
                menu_unfroze = True
        elif command.action == InteractionAction.UNFREEZE:
            await application._handle_unfreeze_action(incident, user_id, queue)
        elif command.action in (InteractionAction.TOGGLE_ASSIGNMENT, InteractionAction.ASSIGN, InteractionAction.RELEASE):
            await toggle_assignment(application, incident, user_id, queue, action=command.action)
        elif command.action == InteractionAction.CREATE_TASK:
            application._handle_task_action(incident, user_id, queue)
    if menu_unfroze:
        interaction = replace(interaction, commands=tuple(
            command for command in interaction.commands
            if command.action != InteractionAction.SHOW_FREEZE_OPTIONS
        ))
    if not any(command.action == InteractionAction.SHOW_FREEZE_OPTIONS for command in interaction.commands):
        incident.dump()
    body, header, icons = application.form_body_header_status_icons(incident)
    presentation = application._presentation(incident, body, header, icons, timezone)
    after_interaction = getattr(application.provider, 'after_interaction', None)
    if after_interaction is not None:
        await after_interaction(presentation, interaction)
    return application.provider.respond_to_interaction(presentation)

async def toggle_assignment(self, incident_, user_id, queue_, action=InteractionAction.TOGGLE_ASSIGNMENT):
    """Apply explicit claim/release commands or the platform's state-dependent toggle."""
    assign = action == InteractionAction.ASSIGN or (
        action == InteractionAction.TOGGLE_ASSIGNMENT and (incident_.chain_enabled or incident_.status != 'resolved')
    )
    needs_assignment = assign and str(incident_.assigned_user_id) != str(user_id)
    if needs_assignment and not await self.fetch_and_assign_user_name(incident_, user_id, dump=False):
        return
    await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
    if assign:
        if not needs_assignment:
            logger.info('Button pressed: user already assigned', extra={'incident': incident_.uniq_id, 'button': 'take_it', 'user_id': user_id})
        else:
            logger.info('Button pressed: assigning to user', extra={'incident': incident_.uniq_id, 'button': 'take_it', 'user_id': user_id})
            self.track_async_task(asyncio.create_task(self.post_assignment_notification(incident_)))
        incident_.chain_enabled = False
    else:
        logger.info('Button pressed', extra={'incident': incident_.uniq_id, 'button': 'release', 'user_id': user_id})
        self.track_async_task(asyncio.create_task(self.post_unassignment_notification(incident_)))
        incident_.release()
