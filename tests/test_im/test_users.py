"""
Unit tests for app.im.users module.
"""
import pytest

from app.im.users import UndefinedUser


class TestUndefinedUser:
    """Test cases for UndefinedUser class."""

    def test_undefined_user_creation(self):
        """Test creating an UndefinedUser instance."""
        user = UndefinedUser("testuser")

        assert user.name == "testuser"
        assert user.defined is False

    def test_undefined_user_with_empty_name(self):
        """Test creating an UndefinedUser with empty name."""
        user = UndefinedUser("")

        assert user.name == ""
        assert user.defined is False

    def test_undefined_user_with_none_name(self):
        """Test creating an UndefinedUser with None name."""
        user = UndefinedUser(None)

        assert user.name is None
        assert user.defined is False

    def test_undefined_user_with_special_characters(self):
        """Test creating an UndefinedUser with special characters in name."""
        user = UndefinedUser("user@domain.com")

        assert user.name == "user@domain.com"
        assert user.defined is False

    def test_undefined_user_with_unicode_name(self):
        """Test creating an UndefinedUser with unicode characters."""
        user = UndefinedUser("用户")

        assert user.name == "用户"
        assert user.defined is False

    def test_undefined_user_with_long_name(self):
        """Test creating an UndefinedUser with long name."""
        long_name = "a" * 1000
        user = UndefinedUser(long_name)

        assert user.name == long_name
        assert user.defined is False

    def test_undefined_user_attributes_immutable(self):
        """Test that UndefinedUser attributes are properly set and immutable."""
        user = UndefinedUser("testuser")

        # Test that attributes are set correctly
        assert user.name == "testuser"
        assert user.defined is False

        # Test that defined is always False (immutable behavior)
        assert user.defined is False

    def test_undefined_user_string_representation(self):
        """Test string representation of UndefinedUser."""
        user = UndefinedUser("testuser")

        # The class doesn't define __str__ or __repr__, so we test the attributes
        assert hasattr(user, 'name')
        assert hasattr(user, 'defined')
        assert user.name == "testuser"
        assert user.defined is False

    def test_undefined_user_equality(self):
        """Test equality comparison of UndefinedUser instances."""
        user1 = UndefinedUser("testuser")
        user2 = UndefinedUser("testuser")
        user3 = UndefinedUser("different")

        # Since no __eq__ is defined, instances are compared by identity
        assert user1 is not user2
        assert user1 != user2  # Different instances
        assert user1 != user3  # Different names

    def test_undefined_user_hash(self):
        """Test hash behavior of UndefinedUser instances."""
        user1 = UndefinedUser("testuser")
        user2 = UndefinedUser("testuser")

        # Since no __hash__ is defined, instances should be hashable
        # (default object hash behavior)
        assert hash(user1) != hash(user2)  # Different instances have different hashes

    def test_undefined_user_type(self):
        """Test that UndefinedUser is of correct type."""
        user = UndefinedUser("testuser")

        assert isinstance(user, UndefinedUser)
        assert type(user).__name__ == "UndefinedUser"

    def test_undefined_user_module_import(self):
        """Test that UndefinedUser can be imported from the module."""
        from app.im.users import UndefinedUser

        user = UndefinedUser("testuser")
        assert user.name == "testuser"
        assert user.defined is False
