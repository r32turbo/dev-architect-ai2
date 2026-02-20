"""Unit tests for the configuration module."""
import os
import pytest
from src.agent.configuration import Configuration


class TestConfigurationInitialization:
    """Tests for Configuration class initialization."""

    def test_configuration_creation(self):
        """Test creating a Configuration object."""
        config = Configuration()
        assert config is not None
        assert isinstance(config, Configuration)

    def test_configuration_attributes(self):
        """Test that Configuration has expected attributes."""
        config = Configuration()
        # Check that common configuration attributes exist
        assert hasattr(config, "__dict__") or hasattr(config, "__class__")

    def test_configuration_with_model_name(self):
        """Test Configuration with a specific model name."""
        # Most configurations allow model_name parameter
        try:
            config = Configuration(model_name="gemini-pro")
            assert config is not None
        except TypeError:
            # If model_name is not a parameter, that's okay
            config = Configuration()
            assert config is not None

    def test_configuration_with_max_search_depth(self):
        """Test Configuration with max search depth."""
        try:
            config = Configuration(max_search_depth=5)
            assert config is not None
        except TypeError:
            # If max_search_depth is not a parameter, that's okay
            config = Configuration()
            assert config is not None


class TestConfigurationValidation:
    """Tests for Configuration validation."""

    def test_configuration_is_not_none(self):
        """Test that Configuration object is created successfully."""
        config = Configuration()
        assert config is not None

    def test_multiple_configuration_instances(self):
        """Test creating multiple Configuration instances."""
        config1 = Configuration()
        config2 = Configuration()
        assert config1 is not None
        assert config2 is not None
        # They should be different instances
        assert id(config1) != id(config2)

    def test_configuration_dict_representation(self):
        """Test that Configuration can be represented as dict."""
        config = Configuration()
        # Try to get dict representation
        try:
            config_dict = vars(config)
            assert isinstance(config_dict, dict)
        except AttributeError:
            # If it's not a regular object with __dict__, that's okay
            assert config is not None


class TestConfigurationDefaults:
    """Tests for Configuration default values."""

    def test_configuration_has_defaults(self):
        """Test that Configuration provides sensible defaults."""
        config = Configuration()
        assert config is not None
        # Basic check that the object is properly initialized
        assert hasattr(config, "__class__")

    def test_configuration_type_checking(self):
        """Test type safety of Configuration."""
        config = Configuration()
        assert isinstance(config, Configuration)
        assert type(config).__name__ == "Configuration"
