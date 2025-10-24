import os
import yaml
from typing import Dict, List, Optional
from app.logging import logger
from app.tools import NoAliasDumper
from app.config.config import get_config


class IncidentMigrator:
    """
    Handles versioned migrations for incident files.
    
    This migrator works directly with YAML files before they are loaded
    into Incident objects, allowing for breaking changes like field renames.
    """
    
    # Define migration path - each version knows how to migrate to the next
    MIGRATION_CHAIN = {
        'v0.4': 'v3.0.0',
    }
    
    def __init__(self):
        """Initialize the migrator with available migration methods."""
        # Add version migrations here as needed
        # Example: 'v0.4_to_v0.5': self._migrate_v0_4_to_v0_5,
        self._migration_methods = {
            'v0.4_to_v3.0.0': self._migrate_v0_4_to_v3_0_0,
        }
    
    def migrate_file(self, file_path: str, incident_data: Dict, current_version: str, target_version: str):
        """
        Migrate an incident file to the target version.
        
        Args:
            file_path: Path to the incident YAML file
            incident_data: The loaded incident data
            current_version: Current version of the incident data
            target_version: The target version to migrate to
        """
        logger.info(f'Migrating {os.path.basename(file_path)} from {current_version} to {target_version}')
        
        migrated_data = self._migrate_data(incident_data, current_version, target_version)
        
        try:
            with open(file_path, 'w') as f:
                yaml.dump(migrated_data, f, NoAliasDumper, default_flow_style=False)
        except  (OSError, PermissionError, FileNotFoundError) as e:
            logger.error(f'Failed to write migrated incident file {os.path.basename(file_path)}: {str(e)}')
        
        logger.info(f'Successfully migrated {os.path.basename(file_path)}')
    
    def _migrate_data(self, incident_data: Dict, from_version: str, to_version: str) -> Dict:
        """
        Apply sequential migrations from from_version to to_version.
        
        Args:
            incident_data: The incident data dictionary to migrate
            from_version: The current version of the incident data
            to_version: The target version to migrate to
            
        Returns:
            The migrated incident data dictionary
        """
        if not self.MIGRATION_CHAIN:
            incident_data['version'] = to_version
            return incident_data
        
        migration_path = self._get_migration_path(from_version, to_version)
        
        current_data = incident_data.copy()
        
        for i in range(len(migration_path) - 1):
            current_version = migration_path[i]
            next_version = migration_path[i + 1]
            
            current_data = self._apply_single_migration(current_data, current_version, next_version)
        return current_data
    
    def _get_migration_path(self, from_version: str, to_version: str) -> List[str]:
        """
        Find the migration path from from_version to to_version.
        
        Args:
            from_version: Starting version
            to_version: Target version
            
        Returns:
            List of versions in migration path
        """
        path = [from_version]
        current = from_version
        
        while current != to_version:
            next_version = self.MIGRATION_CHAIN[current]
            path.append(next_version)
            current = next_version
        
        return path
    
    def _apply_single_migration(self, data: Dict, from_version: str, to_version: str) -> Dict:
        """
        Apply a single migration step.
        
        Args:
            data: The incident data to migrate
            from_version: Current version
            to_version: Target version for this step
            
        Returns:
            The migrated data
        """
        method_key = f"{from_version}_to_{to_version}"
        migration_method = self._migration_methods[method_key]
        migrated_data = migration_method(data)
        migrated_data['version'] = to_version
        return migrated_data
    
    def _migrate_v0_4_to_v3_0_0(self, data: Dict) -> Dict:
        migrated = data.copy()
        migrated['payload'] = migrated.pop('last_state')
        
        config = get_config()
        migrated['messenger_type'] = config.messenger.type.value
        return migrated
