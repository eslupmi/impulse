from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.config.validation import MessengerType
from app.im.application import Application
from app.im.mattermost.threads import _build_mattermost_actions
from app.im.slack.threads import _build_slack_actions
from app.jinja_template import JinjaTemplate


TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"


def _config(task_management=False):
    return SimpleNamespace(
        app=SimpleNamespace(task_management=task_management),
        messenger=SimpleNamespace(impulse_address="https://impulse.test"),
    )


def _env(task_management_enabled=False):
    return SimpleNamespace(task_management_enabled=task_management_enabled)


def _maintenance_incident():
    return SimpleNamespace(
        status="firing",
        chain_enabled=False,
        frozen_by_inhibition=False,
        frozen_by_maintenance=True,
        frozen_until=datetime.now(timezone.utc) + timedelta(hours=1),
        task_link="",
        can_manual_unfreeze=lambda: False,
        is_frozen=lambda: True,
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


@pytest.mark.parametrize(
    ("builder", "config_patch", "env_patch", "label_key"),
    [
        (_build_slack_actions, "app.im.slack.threads.get_config", "app.im.slack.threads.get_environment_config", "text"),
        (
            _build_mattermost_actions,
            "app.im.mattermost.threads.get_config",
            "app.im.mattermost.threads.get_environment_config",
            "name",
        ),
    ],
)
def test_maintenance_freeze_button_label_is_maintenance(builder, config_patch, env_patch, label_key):
    with patch(config_patch, return_value=_config()), patch(env_patch, return_value=_env()):
        actions = builder(_maintenance_incident(), "UTC")

    freeze_action = next(action for action in actions if action.get("name") == "freeze" or action.get("id") == "freeze")
    assert freeze_action[label_key] == "Maintenance"


@pytest.mark.parametrize("template_name", ["slack_body.j2", "mattermost_body.j2", "telegram_body.j2"])
def test_parent_section_hidden_for_maintenance_sentinel_only(template_name):
    template = JinjaTemplate(
        (TEMPLATES_DIR / template_name).read_text(),
        autoescape=template_name.startswith("telegram_"),
    )
    incident = SimpleNamespace(serialize=lambda: _incident_data(["maintenance"]))
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
    template = JinjaTemplate(
        (TEMPLATES_DIR / template_name).read_text(),
        autoescape=template_name.startswith("telegram_"),
    )
    incident = SimpleNamespace(serialize=lambda: _incident_data(["maintenance", "parent-1"]))
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


def test_application_jinja_template_autoescape_only_for_telegram():
    snippet = '<a href="{{ url }}">link</a>'
    url = 'https://example.com?q="x"&y=1'
    telegram = Application.jinja_template(SimpleNamespace(type=MessengerType.TELEGRAM), snippet)
    slack = Application.jinja_template(SimpleNamespace(type=MessengerType.SLACK), snippet)

    assert telegram.render(url=url) == '<a href="https://example.com?q=&#34;x&#34;&amp;y=1">link</a>'
    assert slack.render(url=url) == '<a href="https://example.com?q="x"&y=1">link</a>'


def test_telegram_body_escapes_quotes_in_source_and_runbook_urls():
    grafana_url = (
        'https://grafana.iuqweiu.com/explore?orgld=1&left="now-1h","now","VictoriaMetrics",'
        '{"expr":"rate(kube_pod_container_status_restarts_total{job=\\"kube-state-metrics\\"}[15m])"}'
    )
    payload = {
        "commonAnnotations": {
            "summary": "Summary",
            "description": "Test description 'with quotes'",
            "runbook": grafana_url.replace("grafana.iuqweiu.com", "grafana.tst-st.com"),
        },
        "groupLabels": {"alertname": "alert1"},
        "commonLabels": {
            "alertname": "alert1",
            "instance": "localhost:9100",
            "job": "elasricsearch",
            "severity": "critical",
            "service": "elast",
        },
        "alerts": [{"generatorURL": grafana_url, "labels": {"instance": "localhost:9100"}, "annotations": {}}],
    }
    template = Application.jinja_template(
        SimpleNamespace(type=MessengerType.TELEGRAM),
        (TEMPLATES_DIR / "telegram_body.j2").read_text(),
    )
    incident = SimpleNamespace(serialize=lambda: _incident_data([]))
    JinjaTemplate.set_incidents(SimpleNamespace(uniq_ids={}))
    try:
        rendered = template.form_message(payload, incident)
    finally:
        JinjaTemplate.set_incidents(None)

    assert 'href="https://grafana.iuqweiu.com/explore?orgld=1&amp;left=&#34;now-1h&#34;' in rendered
    assert 'href="https://grafana.tst-st.com/explore?orgld=1&amp;left=&#34;now-1h&#34;' in rendered
    assert 'left="now-1h"' not in rendered
    assert "<i>Test description &#39;with quotes&#39;</i>" in rendered
