from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.im.providers.mattermost import MattermostProvider
from app.im.providers.mattermost.payloads import _build_mattermost_actions
from app.im.providers.slack.payloads import _build_slack_actions
from app.im.providers.slack import SlackProvider
from app.im.providers.telegram import TelegramProvider
from app.jinja_template import JinjaTemplate


TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"


def _maintenance_incident():
    return SimpleNamespace(
        status="firing",
        chain_enabled=False,
        frozen_by_inhibition=False,
        frozen_by_maintenance=True,
        frozen_until=datetime.now(timezone.utc) + timedelta(hours=1),
        task_link="",
        can_manual_unfreeze=lambda: False,
        can_unfreeze=False,
        can_create_task=False,
        is_frozen=True,
    )


def _payload():
    return {
        "commonAnnotations": {},
        "groupLabels": {},
        "commonLabels": {},
        "alerts": [
            {
                "generatorURL": "",
                "labels": {"instance": "host-1"},
                "annotations": {},
            }
        ],
    }


def _incident_data(parents):
    return {
        "task_link": "",
        "assigned_user_id": "",
        "assigned_user": "",
        "parents": parents,
        "childs": [],
    }


def _incident(parents, childs=None):
    data = _incident_data(parents)
    if childs is not None:
        data["childs"] = childs
    return SimpleNamespace(serialize=lambda: data, parents=parents, childs=data["childs"])


@pytest.mark.parametrize(
    ("builder", "label_key"),
    [(_build_slack_actions, "text"), (_build_mattermost_actions, "name")],
)
def test_maintenance_freeze_button_label_is_maintenance(builder, label_key):
    actions = builder(_maintenance_incident(), "")

    freeze_action = next(action for action in actions if action.get("name") == "freeze" or action.get("id") == "freeze")
    assert freeze_action[label_key] == "Maintenance"


@pytest.mark.parametrize("template_name", ["slack_body.j2", "mattermost_body.j2", "telegram_body.j2"])
def test_parent_section_hidden_for_maintenance_sentinel_only(template_name):
    if template_name == 'slack_body.j2':
        source = SlackProvider.template_source('body')
    elif template_name == 'mattermost_body.j2':
        source = MattermostProvider.template_source('body')
    else:
        source = TelegramProvider.template_source('body')
    template = JinjaTemplate(source)
    incident = _incident(["maintenance"])
    JinjaTemplate.set_incidents(SimpleNamespace(uniq_ids={}))
    try:
        rendered = template.form_message(_payload(), incident)
    finally:
        JinjaTemplate.set_incidents(None)

    assert "Parent incidents" not in rendered
    assert "Parent sources" not in rendered
    assert "Maintenance" not in rendered


@pytest.mark.parametrize("template_name", ["slack_body.j2", "mattermost_body.j2", "telegram_body.j2"])
def test_parent_section_shows_only_real_parent_incidents(template_name):
    if template_name == 'slack_body.j2':
        source = SlackProvider.template_source('body')
    elif template_name == 'mattermost_body.j2':
        source = MattermostProvider.template_source('body')
    else:
        source = TelegramProvider.template_source('body')
    template = JinjaTemplate(source)
    incident = _incident(["maintenance", "parent-1"])
    parent = SimpleNamespace(
        link="https://example.test/parent",
        payload={"commonLabels": {"alertname": "ParentAlert"}},
    )
    JinjaTemplate.set_incidents(SimpleNamespace(uniq_ids={"parent-1": parent}))
    try:
        rendered = template.form_message(_payload(), incident)
    finally:
        JinjaTemplate.set_incidents(None)

    assert "Parent incidents" in rendered
    assert "Parent sources" not in rendered
    assert "ParentAlert" in rendered
    assert "Maintenance" not in rendered
