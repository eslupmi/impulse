"""
Unit tests for app.im.chain.filter_steps module.
"""
from unittest.mock import patch

from app.config.validation import SimpleChainStep
from app.im.chain.filter_steps import filter_undeclared_steps


class TestFilterUndeclaredSteps:
    def test_keeps_wait_and_declared(self):
        steps = [
            SimpleChainStep(user='alice'),
            SimpleChainStep(wait='1m'),
            SimpleChainStep(webhook='hook'),
        ]
        result = filter_undeclared_steps(
            'c1', steps,
            users={'alice': {}},
            webhooks={'hook': {}},
        )
        assert result == steps

    def test_drops_undeclared_user_with_warning(self):
        steps = [
            SimpleChainStep(user='alice'),
            SimpleChainStep(wait='1m'),
            SimpleChainStep(user='bob'),
        ]
        with patch('app.im.chain.filter_steps.logger') as mock_logger:
            result = filter_undeclared_steps('c1', steps, users={'alice': {}})
        assert len(result) == 2
        assert result[0].user == 'alice'
        assert result[1].wait == '1m'
        mock_logger.warning.assert_called_once_with(
            'Chain step entity not declared',
            extra={'chain': 'c1', 'user': 'bob'},
        )

    def test_drops_undeclared_user_group_group_webhook_chain(self):
        steps = [
            SimpleChainStep(user_group='missing_ug'),
            SimpleChainStep(group='missing_g'),
            SimpleChainStep(webhook='missing_wh'),
            SimpleChainStep(chain='missing_ch'),
            SimpleChainStep(wait='5s'),
        ]
        with patch('app.im.chain.filter_steps.logger') as mock_logger:
            result = filter_undeclared_steps('c1', steps)
        assert result == [steps[-1]]
        assert mock_logger.warning.call_count == 4

    def test_keeps_declared_nested_chain(self):
        steps = [SimpleChainStep(chain='nested')]
        result = filter_undeclared_steps('c1', steps, chains={'nested': []})
        assert result == steps

    def test_accepts_dict_steps(self):
        steps = [{'user': 'alice'}, {'wait': '1m'}, {'user': 'ghost'}]
        result = filter_undeclared_steps('c1', steps, users={'alice': {}})
        assert result == [{'user': 'alice'}, {'wait': '1m'}]

    def test_empty_steps(self):
        assert filter_undeclared_steps('c1', []) == []
        assert filter_undeclared_steps('c1', None) == []
