"""
Unit tests for app.im.groups module.
"""
from unittest.mock import Mock, patch

import pytest

from app.im.groups import UserGroup, generate_user_groups
from app.im.users import UndefinedUser


class TestUserGroup:
    """Test cases for UserGroup class."""

    def test_user_group_creation(self):
        """Test creating a UserGroup instance."""
        users = [Mock(), Mock()]
        group = UserGroup("test_group", users)
        
        assert group.name == "test_group"
        assert group.users == users

    def test_user_group_with_empty_users(self):
        """Test creating a UserGroup with empty users list."""
        group = UserGroup("empty_group", [])
        
        assert group.name == "empty_group"
        assert group.users == []

    def test_user_group_with_single_user(self):
        """Test creating a UserGroup with single user."""
        user = Mock()
        group = UserGroup("single_group", [user])
        
        assert group.name == "single_group"
        assert group.users == [user]
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
        """Test generate_user_groups with user groups and users."""
        # Mock users dictionary
        mock_user1 = Mock()
        mock_user2 = Mock()
        users = {
            "user1": mock_user1,
            "user2": mock_user2
        }
        
        # Mock user groups dictionary
        user_groups_dict = {
            "group1": Mock(users=["user1", "user2"]),
            "group2": Mock(users=["user1"])
        }
        
        with patch('app.im.groups.logger') as mock_logger:
            result = generate_user_groups(user_groups_dict, users)
            
            # Check that logger was called
            mock_logger.info.assert_called_once_with('Creating user_groups')
            
            # Check result structure
            assert len(result) == 2
            assert "group1" in result
            assert "group2" in result
            
            # Check UserGroup objects
            assert isinstance(result["group1"], UserGroup)
            assert isinstance(result["group2"], UserGroup)
            
            # Check group1 users
            assert len(result["group1"].users) == 2
            assert result["group1"].users[0] == mock_user1
            assert result["group1"].users[1] == mock_user2
            
            # Check group2 users
            assert len(result["group2"].users) == 1
            assert result["group2"].users[0] == mock_user1

    def test_generate_user_groups_with_undefined_users(self):
        """Test generate_user_groups with undefined users."""
        users = {"existing_user": Mock()}
        
        user_groups_dict = {
            "group1": Mock(users=["existing_user", "undefined_user"])
        }
        
        with patch('app.im.groups.logger'):
            result = generate_user_groups(user_groups_dict, users)
            
            assert len(result) == 1
            assert "group1" in result
            
            group = result["group1"]
            assert isinstance(group, UserGroup)
            assert len(group.users) == 2
            
            # First user should be the existing user
            assert group.users[0] == users["existing_user"]
            
            # Second user should be UndefinedUser
            assert isinstance(group.users[1], UndefinedUser)
            assert group.users[1].name == "undefined_user"

    def test_generate_user_groups_empty_group(self):
        """Test generate_user_groups with empty group."""
        users = {"user1": Mock()}
        
        user_groups_dict = {
            "empty_group": Mock(users=[])
        }
        
        with patch('app.im.groups.logger'):
            result = generate_user_groups(user_groups_dict, users)
            
            assert len(result) == 1
            assert "empty_group" in result
            
            group = result["empty_group"]
            assert isinstance(group, UserGroup)
            assert group.users == []

    def test_generate_user_groups_no_users_dict(self):
        """Test generate_user_groups with user groups but no users dict."""
        user_groups_dict = {
            "group1": Mock(users=["user1", "user2"])
        }
        
        with patch('app.im.groups.logger'):
            # Test with empty users dict instead of None
            result = generate_user_groups(user_groups_dict, {})
            
            assert len(result) == 1
            assert "group1" in result
            
            group = result["group1"]
            assert isinstance(group, UserGroup)
            assert len(group.users) == 2
            
            # Both users should be UndefinedUser instances
            assert isinstance(group.users[0], UndefinedUser)
            assert isinstance(group.users[1], UndefinedUser)
            assert group.users[0].name == "user1"
            assert group.users[1].name == "user2"
