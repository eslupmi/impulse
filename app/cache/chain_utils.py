from typing import Any, Union

from app.im.chain.chain import Chain
from app.im.groups import UserGroup
from app.route.route import MainRoute, Route


def extract_user_ids_from_chains(chains: dict[str, Chain], users: dict[str, Any], user_groups: dict[str, UserGroup]) -> set[str]:
    """
    Extract all user IDs from chains configuration.
    Recursively processes chains to find all users and users in user_groups.
    
    Args:
        chains: Dictionary of chain name to Chain object
        users: Dictionary of user name to User object
        user_groups: Dictionary of user group name to UserGroup object
        
    Returns:
        Set of user IDs
    """
    user_ids = set()
    processed_chains = set()
    
    def process_chain(chain: Chain) -> None:
        """Recursively process chain steps from config file"""
        if chain.name in processed_chains:
            return
        processed_chains.add(chain.name)
        
        for step in chain.steps:
            if isinstance(step, dict):
                if 'user' in step and step['user']:
                    user_name = step['user']
                    if user_name in users:
                        user_obj = users[user_name]
                        user_id = getattr(user_obj, 'id', None)
                        if user_id:
                            user_ids.add(str(user_id))
                elif 'user_group' in step and step['user_group']:
                    group_name = step['user_group']
                    if group_name in user_groups:
                        group = user_groups[group_name]
                        for user_obj in group.users:
                            user_id = getattr(user_obj, 'id', None)
                            if user_id:
                                user_ids.add(str(user_id))
                elif 'chain' in step and step['chain']:
                    nested_chain_name = step['chain']
                    if nested_chain_name in chains:
                        process_chain(chains[nested_chain_name])
            elif hasattr(step, 'get_type_and_value'):
                step_type, step_value = step.get_type_and_value()
                if step_type == 'user':
                    if step_value in users:
                        user_obj = users[step_value]
                        user_id = getattr(user_obj, 'id', None)
                        if user_id:
                            user_ids.add(str(user_id))
                elif step_type == 'user_group':
                    if step_value in user_groups:
                        group = user_groups[step_value]
                        for user_obj in group.users:
                            user_id = getattr(user_obj, 'id', None)
                            if user_id:
                                user_ids.add(str(user_id))
                elif step_type == 'chain':
                    if step_value in chains:
                        process_chain(chains[step_value])
    
    # Process all chains
    for chain in chains.values():
        process_chain(chain)
    
    return user_ids


def extract_user_ids_from_route(route: Union[Route, MainRoute], chains: dict[str, Chain], users: dict[str, Any], user_groups: dict[str, UserGroup]) -> set[str]:
    """
    Extract all user IDs from route configuration.
    Gets chains referenced in route and extracts users from them.
    
    Args:
        route: Route object (MainRoute or Route)
        chains: Dictionary of chain name to Chain object
        users: Dictionary of user name to User object
        user_groups: Dictionary of user group name to UserGroup object
        
    Returns:
        Set of user IDs
    """
    user_ids = set()
    processed_chains = set()
    
    def get_chain_names_from_route(route_obj):
        """Recursively process routes from config file to get chain names"""
        chain_names = set()
        
        if route_obj.chain:
            chain_names.add(route_obj.chain)
        
        if hasattr(route_obj, 'routes') and route_obj.routes:
            for sub_route in route_obj.routes:
                chain_names.update(get_chain_names_from_route(sub_route))
        
        return chain_names
    
    chain_names = get_chain_names_from_route(route)
    for chain_name in chain_names:
        if chain_name in chains and chain_name not in processed_chains:
            chain_user_ids = extract_user_ids_from_chains({chain_name: chains[chain_name]}, users, user_groups)
            user_ids.update(chain_user_ids)
            processed_chains.add(chain_name)
    
    return user_ids
