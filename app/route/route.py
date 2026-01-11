from typing import List, Optional

from app.config.validation import RouteConfig
from app.logging import logger
from app.route.matcher import Matcher


class MainRoute:
    def __init__(self, channel: str, chain: str = None, routes_list: List[RouteConfig] = None):
        self.channel = channel
        self.chain = chain
        self.routes = []
        if routes_list:
            for r in routes_list:
                if not r.routes:
                    route = Route(r.channel, r.chain, [], r.matchers)
                    self.routes.append(route)
                else:
                    route = Route(r.channel, r.chain, r.routes, r.matchers)
                    self.routes.append(route)

    def get_route(self, alert_state):
        if len(self.routes) == 0:
            return self.channel, self.chain
        else:
            for r in self.routes:
                match, channel, chain = r.get_route(alert_state)
                if match:
                    return channel, chain
            return self.channel, self.chain

    def get_uniq_channels(self):
        channels = []
        channels.append(self.channel)
        for r in self.routes:
            if len(r.routes) == 0:
                channels.append(r.channel)
            else:
                channels = r.get_channels(channels)
        return set(channels)

    def __repr__(self):
        return self.chain


class Route(MainRoute):
    def __init__(self, channel: str, chain: str, routes_list: List[RouteConfig], matchers: List[str]):
        super().__init__(channel, chain, routes_list)
        self.matchers = [Matcher(m) for m in matchers]

    def get_route(self, alert_state):
        for m in self.matchers:
            if not m.matches(alert_state):
                return False, None, None
        if len(self.routes) == 0:
            return True, self.channel, self.chain
        else:
            for r in self.routes:
                match, channel, chain = r.get_route(alert_state)
                if match:
                    return True, channel, chain
            return True, self.channel, self.chain

    def get_channels(self, channels):
        channels.append(self.channel)
        if len(self.routes) != 0:
            for r in self.routes:
                channels = r.get_channels(channels)
        return channels


def generate_route(route_config: Optional[RouteConfig]):
    logger.info('Creating route')
    if not route_config:
        return MainRoute('default')
    main_channel_name = route_config.channel
    main_chain = route_config.chain
    routes = route_config.routes

    route_ = MainRoute(main_channel_name, main_chain, routes)
    logger.info("Route created")
    return route_
