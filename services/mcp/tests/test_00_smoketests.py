"""Five no-brainer smoke tests — the absolute basics that must always pass."""

from __future__ import annotations


def test_package_imports():
    """The mcp_aggregator package can be imported without error."""
    import mcp_aggregator

    assert hasattr(mcp_aggregator, "__name__")


def test_config_module_loads():
    """config.py loads and exposes expected attributes."""
    from mcp_aggregator import config as cfg

    assert hasattr(cfg, "MCP_HOST")
    assert hasattr(cfg, "MCP_PORT")
    assert hasattr(cfg, "HEALTH_INTERVAL")
    assert isinstance(cfg.MCP_PORT, int)


def test_health_status_enum():
    """Status enum has exactly the three expected members."""
    from mcp_aggregator.health import Status

    assert set(Status.__members__) == {"HEALTHY", "UNHEALTHY", "UNKNOWN"}
    assert Status.HEALTHY.value == "healthy"
    assert Status.UNHEALTHY.value == "unhealthy"
    assert Status.UNKNOWN.value == "unknown"


def test_backend_health_dataclass():
    """BackendHealth can be instantiated with defaults."""
    from mcp_aggregator.health import BackendHealth, Status

    bh = BackendHealth(name="test")
    assert bh.name == "test"
    assert bh.status == Status.UNKNOWN
    assert bh.consecutive_failures == 0
    assert bh.last_error == ""


def test_enabled_helper():
    """_enabled() correctly parses boolean-ish strings."""
    import os

    from mcp_aggregator import config

    # We test the helper function directly
    assert config._enabled("__TEST_TRUE__", "true") is True
    assert config._enabled("__TEST_FALSE__", "false") is False
    assert config._enabled("__UNSET_VAR__") is False  # default="false"

    os.environ["__TEST_ENABLED__"] = "yes"
    try:
        assert config._enabled("__TEST_ENABLED__") is True
    finally:
        del os.environ["__TEST_ENABLED__"]
