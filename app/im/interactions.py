"""Impulse-owned business actions for verified provider interactions."""
import asyncio
from app.im.plugin_api import InteractionAction
from app.logging import logger

async def apply_interaction(application, interaction, incidents, queue):
    incident = incidents.get_by_ts(ts=interaction.message.thread_id)
    if incident is None:
        return interaction.original_response
    if interaction.message.channel_id and str(incident.channel_id) != str(interaction.message.channel_id):
        return interaction.original_response
    has_freeze = any(command.action in (InteractionAction.FREEZE, InteractionAction.UNFREEZE)
                     for command in interaction.commands)
    if incident.is_frozen and (incident.frozen_by_inhibition or not has_freeze):
        return interaction.original_response
    user_id = interaction.actor_id
    timezone = application._get_user_timezone_str(user_id)
    for command in interaction.commands:
        if command.action == InteractionAction.FREEZE:
            if incident.can_manual_unfreeze():
                await application._handle_unfreeze_action(incident, user_id, queue)
            elif command.freeze_option:
                await application._handle_freeze_action(incident, command.freeze_option, user_id,
                                                       incidents, queue, user_timezone=timezone)
        elif command.action == InteractionAction.UNFREEZE:
            await application._handle_unfreeze_action(incident, user_id, queue)
        elif command.action == InteractionAction.TOGGLE_ASSIGNMENT:
            await toggle_assignment(application, incident, user_id, queue)
        elif command.action == InteractionAction.CREATE_TASK:
            application._handle_task_action(incident, user_id, queue)
    incident.dump()
    body, header, icons = application.form_body_header_status_icons(incident)
    return application.provider.respond_to_interaction(application._presentation(incident, body, header, icons, timezone))

async def toggle_assignment(self, incident_, user_id, queue_):
    """Handle chain-related button actions"""
    await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
    if incident_.chain_enabled or incident_.status != 'resolved':
        if incident_.assigned_user_id == user_id:
            logger.info('Button pressed: user already assigned', extra={'incident': incident_.uniq_id, 'button': 'take_it', 'user_id': user_id})
        else:
            logger.info('Button pressed: assigning to user', extra={'incident': incident_.uniq_id, 'button': 'take_it', 'user_id': user_id})
            self.fetch_and_assign_user_name(incident_, user_id, dump=False)
            self.track_async_task(asyncio.create_task(self.post_assignment_notification(incident_)))
        incident_.chain_enabled = False
    else:
        logger.info('Button pressed', extra={'incident': incident_.uniq_id, 'button': 'release', 'user_id': user_id})
        self.track_async_task(asyncio.create_task(self.post_unassignment_notification(incident_)))
        incident_.release()

