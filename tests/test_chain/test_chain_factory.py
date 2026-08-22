"""
Unit tests for app.im.chain.chain_factory module.
"""
from unittest.mock import Mock, patch

import pytest

from app.config.validation import ChainType, SimpleChainStep
from app.im.chain.chain_factory import ChainFactory

_EMPTY_REGS = {
    'users': {},
    'user_groups': {},
    'groups': {},
    'webhooks': {},
    'chains': {},
}


class TestChainFactory:
    """Test cases for ChainFactory class."""

    def test_create_chain_with_google_calendar_chain_type(self):
        """Test _create_chain with Google Calendar chain type."""
        from app.config.validation import CloudChain
        config = Mock()
        config.type = ChainType.CLOUD
        config.provider = "google"
        config.default_steps = []
        config.model_copy = Mock(return_value=config)

        with patch('app.im.chain.chain_factory.GoogleCalendarChain') as mock_google_chain:
            mock_instance = Mock()
            mock_google_chain.return_value = mock_instance
            with patch('app.im.chain.chain_factory.isinstance', side_effect=lambda o, t: t is CloudChain):
                result = ChainFactory._create_chain("test_chain", config, _EMPTY_REGS)

            mock_google_chain.assert_called_once_with("test_chain", config, registries=_EMPTY_REGS)
            mock_instance.start_sync.assert_called_once()
            assert result == mock_instance

    def test_create_chain_with_google_calendar_chain_type_not_google_provider(self):
        """Test _create_chain with cloud type but not google provider."""
        config = Mock()
        config.type = ChainType.CLOUD
        config.provider = "microsoft"

        with pytest.raises(ValueError, match="Unknown chain type 'cloud' for chain 'test_chain'"):
            ChainFactory._create_chain("test_chain", config, _EMPTY_REGS)

    def test_create_chain_with_unknown_chain_type(self):
        """Test _create_chain with unknown chain type."""
        config = Mock()
        config.type = Mock()
        config.type.value = "UNKNOWN_TYPE"

        with pytest.raises(ValueError, match="Unknown chain type 'UNKNOWN_TYPE' for chain 'test_chain'"):
            ChainFactory._create_chain("test_chain", config, _EMPTY_REGS)

    def test_create_chain_with_schedule_chain_exception(self):
        """Test _create_chain with schedule chain creation exception."""
        from app.config.validation import ScheduleChain as ScheduleChainType
        config = Mock(spec=ScheduleChainType)
        config.type = ChainType.SCHEDULE
        config.timezone = "UTC"
        config.schedule = []

        with patch('app.im.chain.chain_factory.ScheduleChain') as mock_schedule_chain:
            mock_schedule_chain.side_effect = Exception("Schedule chain error")
            with patch('app.im.chain.chain_factory.isinstance', side_effect=lambda o, t: t is ScheduleChainType):
                with pytest.raises(Exception, match="Schedule chain error"):
                    ChainFactory._create_chain("test_chain", config, _EMPTY_REGS)

    def test_create_chain_with_google_calendar_chain_exception(self):
        """Test _create_chain with Google Calendar chain creation exception."""
        from app.config.validation import CloudChain
        config = Mock()
        config.type = ChainType.CLOUD
        config.provider = "google"
        config.default_steps = []
        config.model_copy = Mock(return_value=config)

        with patch('app.im.chain.chain_factory.GoogleCalendarChain') as mock_google_chain:
            mock_google_chain.side_effect = Exception("Google Calendar chain error")
            with patch('app.im.chain.chain_factory.isinstance', side_effect=lambda o, t: t is CloudChain):
                with pytest.raises(Exception, match="Google Calendar chain error"):
                    ChainFactory._create_chain("test_chain", config, _EMPTY_REGS)

    def test_create_chain_with_google_calendar_chain_starts_sync(self):
        """Google calendar chains always start sync after construction."""
        from app.config.validation import CloudChain
        config = Mock()
        config.type = ChainType.CLOUD
        config.provider = "google"
        config.default_steps = []
        config.model_copy = Mock(return_value=config)

        with patch('app.im.chain.chain_factory.GoogleCalendarChain') as mock_google_chain:
            mock_instance = Mock()
            mock_google_chain.return_value = mock_instance
            with patch('app.im.chain.chain_factory.isinstance', side_effect=lambda o, t: t is CloudChain):
                result = ChainFactory._create_chain("test_chain", config, _EMPTY_REGS)

        mock_instance.start_sync.assert_called_once()
        assert result == mock_instance

    def test_create_chain_with_basic_chain_type(self):
        """Test _create_chain with basic chain type (no type attribute)."""
        config = [SimpleChainStep(user="user1"), SimpleChainStep(user="user2")]
        regs = {**_EMPTY_REGS, 'users': {'user1': {}, 'user2': {}}}

        with patch('app.im.chain.chain_factory.Chain') as mock_chain:
            mock_instance = Mock()
            mock_chain.return_value = mock_instance

            result = ChainFactory._create_chain("test_chain", config, regs)

            mock_chain.assert_called_once_with("test_chain", config)
            assert result == mock_instance

    def test_create_chain_filters_undeclared_steps(self):
        config = [
            SimpleChainStep(user="user1"),
            SimpleChainStep(wait="1m"),
            SimpleChainStep(user="ghost"),
        ]
        regs = {**_EMPTY_REGS, 'users': {'user1': {}}}

        result = ChainFactory._create_chain("test_chain", config, regs)

        assert [s.get_type_and_value() for s in result.steps] == [
            ('user', 'user1'),
            ('wait', '1m'),
        ]

    def test_create_chain_with_basic_chain_exception(self):
        """Test _create_chain with basic chain creation exception."""
        config = [SimpleChainStep(user="user1")]
        regs = {**_EMPTY_REGS, 'users': {'user1': {}}}

        with patch('app.im.chain.chain_factory.Chain') as mock_chain:
            mock_chain.side_effect = Exception("Basic chain error")

            with pytest.raises(Exception, match="Basic chain error"):
                ChainFactory._create_chain("test_chain", config, regs)

    def test_generate_with_empty_chains_dict(self):
        """Test generate with empty chains dictionary."""
        with patch('app.im.chain.chain_factory.logger') as mock_logger:
            result = ChainFactory.generate({})

            mock_logger.info.assert_called_once_with('Creating chains')
            assert result == {}

    def test_generate_with_single_chain(self):
        """Test generate with single chain."""
        chains_dict = {
            "test_chain": Mock()
        }

        with patch.object(ChainFactory, '_create_chain') as mock_create_chain:
            mock_chain = Mock()
            mock_create_chain.return_value = mock_chain

            with patch('app.im.chain.chain_factory.logger') as mock_logger:
                result = ChainFactory.generate(chains_dict)

                mock_logger.info.assert_called_once_with('Creating chains')
                expected_regs = {
                    'users': {},
                    'user_groups': {},
                    'groups': {},
                    'webhooks': {},
                    'chains': chains_dict,
                }
                mock_create_chain.assert_called_once_with(
                    "test_chain", chains_dict["test_chain"], expected_regs
                )
                assert result == {"test_chain": mock_chain}

    def test_generate_with_multiple_chains(self):
        """Test generate with multiple chains."""
        chains_dict = {
            "chain1": Mock(),
            "chain2": Mock(),
            "chain3": Mock()
        }

        with patch.object(ChainFactory, '_create_chain') as mock_create_chain:
            mock_chain1 = Mock()
            mock_chain2 = Mock()
            mock_chain3 = Mock()
            mock_create_chain.side_effect = [mock_chain1, mock_chain2, mock_chain3]

            with patch('app.im.chain.chain_factory.logger') as mock_logger:
                result = ChainFactory.generate(chains_dict)

                mock_logger.info.assert_called_once_with('Creating chains')
                assert mock_create_chain.call_count == 3
                assert result == {
                    "chain1": mock_chain1,
                    "chain2": mock_chain2,
                    "chain3": mock_chain3
                }

    def test_generate_with_chain_creation_failure(self):
        """Test generate with chain creation failure."""
        chains_dict = {
            "test_chain": Mock()
        }

        with patch.object(ChainFactory, '_create_chain') as mock_create_chain:
            mock_create_chain.return_value = None

            with patch('app.im.chain.chain_factory.logger') as mock_logger:
                result = ChainFactory.generate(chains_dict)

                mock_logger.info.assert_called_once_with('Creating chains')
                mock_logger.warning.assert_called_once_with(
                    "Skipping chain 'test_chain' because it is handled outside runtime chain creation"
                )
                assert result == {}

    def test_generate_with_mixed_success_and_failure(self):
        """Test generate with mixed success and failure."""
        chains_dict = {
            "chain1": Mock(),
            "chain2": Mock(),
            "chain3": Mock()
        }

        with patch.object(ChainFactory, '_create_chain') as mock_create_chain:
            mock_chain1 = Mock()
            mock_chain3 = Mock()
            mock_create_chain.side_effect = [mock_chain1, None, mock_chain3]

            with patch('app.im.chain.chain_factory.logger') as mock_logger:
                result = ChainFactory.generate(chains_dict)

                mock_logger.info.assert_called_once_with('Creating chains')
                mock_logger.warning.assert_called_once_with(
                    "Skipping chain 'chain2' because it is handled outside runtime chain creation"
                )
                assert result == {
                    "chain1": mock_chain1,
                    "chain3": mock_chain3
                }

    def test_generate_with_special_characters_chain_names(self):
        """Test generate with special characters in chain names."""
        chains_dict = {
            "test-chain_with.special@chars": Mock(),
            "chain#123": Mock()
        }

        with patch.object(ChainFactory, '_create_chain') as mock_create_chain:
            mock_chain1 = Mock()
            mock_chain2 = Mock()
            mock_create_chain.side_effect = [mock_chain1, mock_chain2]

            with patch('app.im.chain.chain_factory.logger') as mock_logger:
                result = ChainFactory.generate(chains_dict)

                mock_logger.info.assert_called_once_with('Creating chains')
                assert result == {
                    "test-chain_with.special@chars": mock_chain1,
                    "chain#123": mock_chain2
                }

    def test_generate_with_very_long_chain_names(self):
        """Test generate with very long chain names."""
        long_name = "a" * 1000
        chains_dict = {
            long_name: Mock()
        }

        with patch.object(ChainFactory, '_create_chain') as mock_create_chain:
            mock_chain = Mock()
            mock_create_chain.return_value = mock_chain

            with patch('app.im.chain.chain_factory.logger') as mock_logger:
                result = ChainFactory.generate(chains_dict)

                mock_logger.info.assert_called_once_with('Creating chains')
                assert result == {long_name: mock_chain}

    def test_generate_with_none_chain_config(self):
        """Test generate with None chain config."""
        chains_dict = {
            "test_chain": None
        }

        with patch.object(ChainFactory, '_create_chain') as mock_create_chain:
            mock_create_chain.return_value = None

            with patch('app.im.chain.chain_factory.logger') as mock_logger:
                result = ChainFactory.generate(chains_dict)

                mock_logger.info.assert_called_once_with('Creating chains')
                mock_logger.warning.assert_called_once_with(
                    "Skipping chain 'test_chain' because it is handled outside runtime chain creation"
                )
                assert result == {}

    def test_generate_with_empty_chain_config(self):
        """Test generate with empty chain config."""
        chains_dict = {
            "test_chain": []
        }

        with patch.object(ChainFactory, '_create_chain') as mock_create_chain:
            mock_chain = Mock()
            mock_create_chain.return_value = mock_chain

            with patch('app.im.chain.chain_factory.logger') as mock_logger:
                result = ChainFactory.generate(chains_dict)

                mock_logger.info.assert_called_once_with('Creating chains')
                assert result == {"test_chain": mock_chain}

    def test_generate_with_complex_chain_config(self):
        """Test generate with complex chain config."""
        chains_dict = {
            "test_chain": {
                "type": "SCHEDULE",
                "timezone": "UTC",
                "schedule": [
                    {
                        "matcher": {"start_day_expr": "dow", "start_day_values": [1, 2, 3]},
                        "steps": [{"user": "user1"}, {"user": "user2"}]
                    }
                ]
            }
        }

        with patch.object(ChainFactory, '_create_chain') as mock_create_chain:
            mock_chain = Mock()
            mock_create_chain.return_value = mock_chain

            with patch('app.im.chain.chain_factory.logger') as mock_logger:
                result = ChainFactory.generate(chains_dict)

                mock_logger.info.assert_called_once_with('Creating chains')
                assert result == {"test_chain": mock_chain}

    def test_generate_with_very_many_chains(self):
        """Test generate with very many chains."""
        chains_dict = {f"chain{i}": Mock() for i in range(100)}

        with patch.object(ChainFactory, '_create_chain') as mock_create_chain:
            mock_chains = [Mock() for _ in range(100)]
            mock_create_chain.side_effect = mock_chains

            with patch('app.im.chain.chain_factory.logger') as mock_logger:
                result = ChainFactory.generate(chains_dict)

                mock_logger.info.assert_called_once_with('Creating chains')
                assert len(result) == 100
                assert all(f"chain{i}" in result for i in range(100))

    def test_generate_with_chain_creation_exception(self):
        """Test generate with chain creation exception."""
        chains_dict = {
            "test_chain": Mock()
        }

        with patch.object(ChainFactory, '_create_chain') as mock_create_chain:
            mock_create_chain.side_effect = Exception("Chain creation error")

            with patch('app.im.chain.chain_factory.logger') as mock_logger:
                result = ChainFactory.generate(chains_dict)

                mock_logger.exception.assert_called_once_with("Failed to create chain 'test_chain'")
                mock_logger.warning.assert_called_once_with(
                    "Skipping chain 'test_chain' due to creation failure: Chain creation error"
                )
                assert result == {}

    def test_generate_with_chain_creation_partial_exception(self):
        """Test generate with partial chain creation exception."""
        chains_dict = {
            "chain1": Mock(),
            "chain2": Mock(),
            "chain3": Mock()
        }

        with patch.object(ChainFactory, '_create_chain') as mock_create_chain:
            mock_chain1 = Mock()
            mock_chain3 = Mock()
            mock_create_chain.side_effect = [mock_chain1, Exception("Chain2 error"), mock_chain3]

            with patch('app.im.chain.chain_factory.logger') as mock_logger:
                result = ChainFactory.generate(chains_dict)

                mock_logger.exception.assert_called_once_with("Failed to create chain 'chain2'")
                mock_logger.warning.assert_called_once_with(
                    "Skipping chain 'chain2' due to creation failure: Chain2 error"
                )
                assert result == {
                    "chain1": mock_chain1,
                    "chain3": mock_chain3
                }

    def test_generate_passes_registries(self):
        chains_dict = {"c1": [SimpleChainStep(user="alice"), SimpleChainStep(wait="1s")]}
        result = ChainFactory.generate(
            chains_dict,
            users={'alice': {}},
            webhooks={'wh': {}},
        )
        assert 'c1' in result
        assert [s.get_type_and_value() for s in result['c1'].steps] == [
            ('user', 'alice'),
            ('wait', '1s'),
        ]
