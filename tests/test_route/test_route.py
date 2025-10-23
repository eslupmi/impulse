"""
Unit tests for app.route.route module.
"""
import pytest

from app.config.validation import RouteConfig
from app.route.route import MainRoute, Route, generate_route


class TestMainRoute:
    """Test cases for MainRoute class."""

    def test_main_route_initialization(self):
        """Test MainRoute initialization with different parameters."""
        # Test basic initialization
        route = MainRoute("default_channel")
        assert route.channel == "default_channel"
        assert route.chain is None
        assert route.routes == []

        # Test with chain
        route = MainRoute("default_channel", "test_chain")
        assert route.channel == "default_channel"
        assert route.chain == "test_chain"
        assert route.routes == []

    def test_main_route_initialization_with_routes(self):
        """Test MainRoute initialization with routes list."""
        routes_list = [
            RouteConfig(
                channel="route1",
                chain="chain1",
                routes=[],
                matchers=["severity=\"critical\""]
            ),
            RouteConfig(
                channel="route2",
                chain="chain2",
                routes=[],
                matchers=["service=\"api\""]
            )
        ]

        route = MainRoute("default_channel", "test_chain", routes_list)

        assert route.channel == "default_channel"
        assert route.chain == "test_chain"
        assert len(route.routes) == 2
        assert route.routes[0].channel == "route1"
        assert route.routes[1].channel == "route2"

    def test_get_route_no_routes(self):
        """Test get_route when no routes are defined."""
        route = MainRoute("default_channel", "test_chain")

        channel, chain = route.get_route({"commonLabels": {"severity": "critical"}})

        assert channel == "default_channel"
        assert chain == "test_chain"

    def test_get_route_with_matching_route(self):
        """Test get_route with matching route."""
        routes_list = [
            RouteConfig(
                channel="critical_channel",
                chain="critical_chain",
                routes=[],
                matchers=["severity=\"critical\""]
            )
        ]

        route = MainRoute("default_channel", "test_chain", routes_list)

        channel, chain = route.get_route({"commonLabels": {"severity": "critical"}})

        assert channel == "critical_channel"
        assert chain == "critical_chain"

    def test_get_route_with_non_matching_route(self):
        """Test get_route with non-matching route."""
        routes_list = [
            RouteConfig(
                channel="critical_channel",
                chain="critical_chain",
                routes=[],
                matchers=["severity=\"critical\""]
            )
        ]

        route = MainRoute("default_channel", "test_chain", routes_list)

        channel, chain = route.get_route({"commonLabels": {"severity": "warning"}})

        assert channel == "default_channel"
        assert chain == "test_chain"

    def test_get_route_with_nested_routes(self):
        """Test get_route with nested routes."""
        nested_route = RouteConfig(
            channel="nested_channel",
            chain="nested_chain",
            routes=[],
            matchers=["service=\"api\""]
        )

        routes_list = [
            RouteConfig(
                channel="critical_channel",
                chain="critical_chain",
                routes=[nested_route],
                matchers=["severity=\"critical\""]
            )
        ]

        route = MainRoute("default_channel", "test_chain", routes_list)

        # Test matching nested route
        channel, chain = route.get_route({
            "commonLabels": {"severity": "critical", "service": "api"}
        })

        assert channel == "nested_channel"
        assert chain == "nested_chain"

    def test_get_uniq_channels(self):
        """Test get_uniq_channels with different route configurations."""
        # Test with no routes
        route = MainRoute("default_channel")
        channels = route.get_uniq_channels()
        assert channels == {"default_channel"}

        # Test with simple routes
        routes_list = [
            RouteConfig(
                channel="route1",
                chain="chain1",
                routes=[],
                matchers=["severity=\"critical\""]
            ),
            RouteConfig(
                channel="route2",
                chain="chain2",
                routes=[],
                matchers=["service=\"api\""]
            )
        ]

        route = MainRoute("default_channel", "test_chain", routes_list)
        channels = route.get_uniq_channels()
        assert channels == {"default_channel", "route1", "route2"}

        # Test with nested routes
        nested_route = RouteConfig(
            channel="nested_channel",
            chain="nested_chain",
            routes=[],
            matchers=["service=\"api\""]
        )

        routes_list = [
            RouteConfig(
                channel="route1",
                chain="chain1",
                routes=[nested_route],
                matchers=["severity=\"critical\""]
            )
        ]

        route = MainRoute("default_channel", "test_chain", routes_list)
        channels = route.get_uniq_channels()
        assert channels == {"default_channel", "route1", "nested_channel"}

    def test_repr(self):
        """Test string representation."""
        route = MainRoute("default_channel", "test_chain")

        assert repr(route) == "test_chain"


class TestRoute:
    """Test cases for Route class."""

    def test_route_initialization(self):
        """Test Route initialization."""
        matchers = ["severity=\"critical\"", "service=\"api\""]
        routes_list = []

        route = Route("test_channel", "test_chain", routes_list, matchers)

        assert route.channel == "test_channel"
        assert route.chain == "test_chain"
        assert route.routes == []
        assert len(route.matchers) == 2

    def test_get_route_all_matchers_match(self):
        """Test get_route when all matchers match."""
        matchers = ["severity=\"critical\"", "service=\"api\""]
        route = Route("test_channel", "test_chain", [], matchers)

        alert_state = {
            "commonLabels": {
                "severity": "critical",
                "service": "api"
            }
        }

        match, channel, chain = route.get_route(alert_state)

        assert match is True
        assert channel == "test_channel"
        assert chain == "test_chain"

    def test_get_route_some_matchers_dont_match(self):
        """Test get_route when some matchers don't match."""
        matchers = ["severity=\"critical\"", "service=\"api\""]
        route = Route("test_channel", "test_chain", [], matchers)

        alert_state = {
            "commonLabels": {
                "severity": "critical",
                "service": "database"  # Different service
            }
        }

        match, channel, chain = route.get_route(alert_state)

        assert match is False
        assert channel is None
        assert chain is None

    def test_get_route_no_matchers(self):
        """Test get_route with no matchers."""
        route = Route("test_channel", "test_chain", [], [])

        alert_state = {"commonLabels": {"severity": "critical"}}

        match, channel, chain = route.get_route(alert_state)

        assert match is True
        assert channel == "test_channel"
        assert chain == "test_chain"

    def test_get_route_with_nested_routes(self):
        """Test get_route with nested routes."""
        nested_route = RouteConfig(
            channel="nested_channel",
            chain="nested_chain",
            routes=[],
            matchers=["environment=\"production\""]
        )

        matchers = ["severity=\"critical\""]
        routes_list = [nested_route]
        route = Route("test_channel", "test_chain", routes_list, matchers)

        alert_state = {
            "commonLabels": {
                "severity": "critical",
                "environment": "production"
            }
        }

        match, channel, chain = route.get_route(alert_state)

        assert match is True
        assert channel == "nested_channel"
        assert chain == "nested_chain"

    def test_get_route_nested_routes_no_match(self):
        """Test get_route with nested routes that don't match."""
        nested_route = RouteConfig(
            channel="nested_channel",
            chain="nested_chain",
            routes=[],
            matchers=["environment=\"production\""]
        )

        matchers = ["severity=\"critical\""]
        routes_list = [nested_route]
        route = Route("test_channel", "test_chain", routes_list, matchers)

        alert_state = {
            "commonLabels": {
                "severity": "critical",
                "environment": "staging"  # Different environment
            }
        }

        match, channel, chain = route.get_route(alert_state)

        assert match is True
        assert channel == "test_channel"
        assert chain == "test_chain"

    def test_get_channels(self):
        """Test get_channels with different route configurations."""
        # Test with no routes
        route = Route("test_channel", "test_chain", [], ["severity=\"critical\""])
        channels = []
        result = route.get_channels(channels)
        assert result == ["test_channel"]

        # Test with nested routes
        nested_route = RouteConfig(
            channel="nested_channel",
            chain="nested_chain",
            routes=[],
            matchers=["environment=\"production\""]
        )

        routes_list = [nested_route]
        route = Route("test_channel", "test_chain", routes_list, ["severity=\"critical\""])

        channels = []
        result = route.get_channels(channels)
        assert result == ["test_channel", "nested_channel"]


class TestGenerateRoute:
    """Test cases for generate_route function."""

    def test_generate_route_none_config(self):
        """Test generate_route with None config."""
        route = generate_route(None)

        assert isinstance(route, MainRoute)
        assert route.channel == "default"
        assert route.chain is None

    def test_generate_route_with_config(self):
        """Test generate_route with valid config."""
        config = RouteConfig(
            channel="test_channel",
            chain="test_chain",
            routes=[],
            matchers=[]
        )

        route = generate_route(config)

        assert isinstance(route, MainRoute)
        assert route.channel == "test_channel"
        assert route.chain == "test_chain"

    def test_generate_route_with_nested_routes(self):
        """Test generate_route with nested routes."""
        nested_route = RouteConfig(
            channel="nested_channel",
            chain="nested_chain",
            routes=[],
            matchers=["environment=\"production\""]
        )

        config = RouteConfig(
            channel="main_channel",
            chain="main_chain",
            routes=[nested_route],
            matchers=["severity=\"critical\""]
        )

        route = generate_route(config)

        assert isinstance(route, MainRoute)
        assert route.channel == "main_channel"
        assert route.chain == "main_chain"
        assert len(route.routes) == 1
        assert route.routes[0].channel == "nested_channel"
        assert route.routes[0].chain == "nested_chain"
