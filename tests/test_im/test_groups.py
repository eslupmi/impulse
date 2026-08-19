"""
Unit tests for app.im.groups module.
"""
from unittest.mock import Mock, patch, AsyncMock

import pytest

from app.im.groups import Group
from app.im.user_groups import generate_user_groups, UserGroup


class TestUserGroup:
    """Test cases for UserGroup class."""

    def test_user_group_creation(self):
        group = UserGroup("test_group", ["user1", "user2"])

        assert group.name == "test_group"
        assert group.users == ["user1", "user2"]

    def test_user_group_with_empty_users(self):
        group = UserGroup("empty_group", [])

        assert group.name == "empty_group"
        assert group.users == []

    def test_user_group_with_single_user(self):
        group = UserGroup("single_group", ["user1"])

        assert group.name == "single_group"
        assert group.users == ["user1"]
        assert len(group.users) == 1


class TestGenerateUserGroups:
    """Test cases for generate_user_groups function."""

    def test_generate_user_groups_empty_input(self):
        """Test generate_user_groups with empty input."""
        result = generate_user_groups()

        assert result == {}

    def test_generate_user_groups_none_input(self):
        """Test generate_user_groups with None input."""
        result = generate_user_groups(None, None)

        assert result == {}

    def test_generate_user_groups_with_users(self):
        mock_users = Mock()
        mock_users.get = lambda name, d=None: Mock() if name in ["user1", "user2"] else None

        user_groups_dict = {
            "group1": Mock(users=["user1", "user2"]),
            "group2": Mock(users=["user1"])
        }

        with patch('app.im.user_groups.logger') as mock_logger:
            result = generate_user_groups(user_groups_dict, mock_users)

            mock_logger.info.assert_called_once_with('Creating user_groups')

            assert len(result) == 2
            assert isinstance(result["group1"], UserGroup)
            assert isinstance(result["group2"], UserGroup)
            assert len(result["group1"].users) == 2
            assert len(result["group2"].users) == 1

    def test_generate_user_groups_skips_undefined_users(self):
        mock_users = Mock()
        mock_users.get = lambda name, d=None: Mock() if name == "existing_user" else None

        user_groups_dict = {
            "group1": Mock(users=["existing_user", "undefined_user"])
        }

        with patch('app.im.user_groups.logger') as mock_logger:
            result = generate_user_groups(user_groups_dict, mock_users)

            group = result["group1"]
            assert len(group.users) == 1
            assert group.users[0] == "existing_user"
            mock_logger.warning.assert_called_once()

    def test_generate_user_groups_empty_group(self):
        mock_users = Mock()
        mock_users.get = lambda name, d=None: Mock()

        user_groups_dict = {"empty_group": Mock(users=[])}

        with patch('app.im.user_groups.logger'):
            result = generate_user_groups(user_groups_dict, mock_users)

            assert result["empty_group"].users == []

    def test_generate_user_groups_all_undefined(self):
        mock_users = Mock()
        mock_users.get = lambda name, d=None: None

        user_groups_dict = {"group1": Mock(users=["user1", "user2"])}

        with patch('app.im.user_groups.logger') as mock_logger:
            result = generate_user_groups(user_groups_dict, mock_users)

            assert result["group1"].users == []
            assert mock_logger.warning.call_count == 2


class TestGroup:
    """Test cases for Group class."""

    def test_group_creation_with_all_fields(self):
        """Test creating a Group instance with all fields."""
        group = Group(
            config_name="test_group",
            name="Real Group Name",
            id_="G123456",
            exists=True
        )

        assert group.config_name == "test_group"
        assert group.name == "Real Group Name"
        assert group.id == "G123456"
        assert group.exists is True
        assert group.defined is True

    def test_group_creation_minimal(self):
        """Test creating a Group instance with minimal fields."""
        group = Group(config_name="test_group")

        assert group.config_name == "test_group"
        assert group.name is None
        assert group.id is None
        assert group.exists is False
        assert group.defined is True

    def test_group_repr_with_name(self):
        """Test __repr__ when group has real name from API."""
        group = Group(
            config_name="config_group",
            name="API Group Name",
            id_="G123",
            exists=True
        )

        assert repr(group) == "API Group Name"

    def test_group_repr_without_name(self):
        """Test __repr__ when group has no real name (falls back to config_name)."""
        group = Group(
            config_name="config_group",
            id_="G123",
            exists=False
        )

        assert repr(group) == "config_group"

    def test_group_with_existing_id_but_no_name(self):
        """Test group that exists but name wasn't fetched."""
        group = Group(
            config_name="test_group",
            name=None,
            id_="G123",
            exists=True
        )

        assert group.config_name == "test_group"
        assert group.name is None
        assert group.id == "G123"
        assert group.exists is True
        assert repr(group) == "test_group"  # Falls back to config_name

    def test_group_serialize_keeps_configured_id_when_missing(self):
        group = Group(
            config_name="group_1",
            name=None,
            id_="S0A3WML2S7P",
            exists=False,
        )

        assert group.serialize() == {
            "exists": False,
            "id": "S0A3WML2S7P",
        }
