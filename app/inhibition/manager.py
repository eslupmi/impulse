from typing import Dict, List, Set, TYPE_CHECKING

from app.config.validation import InhibitRule
from app.incident.unfreeze import unfreeze_incident
from app.inhibition.rule import InhibitionRule
from app.logging import logger

if TYPE_CHECKING:
    from app.incident.incident import Incident
    from app.incident.incidents import Incidents
    from app.im.application import Application
    from app.queue.queue import AsyncQueue


class InhibitionManager:
    """Manages inhibition rules and tracks source/target incidents.
    
    This class implements AlertManager-style inhibition for Impulse incidents.
    Unlike AlertManager which just mutes alerts, Impulse freezes target incidents
    and tracks parent/child relationships.
    """
    __slots__ = ['incidents', 'application', 'queue', 'rules', 'sources', 'targets']
    
    def __init__(self, rules: List[InhibitRule], incidents: 'Incidents', application: 'Application', 
                 queue: 'AsyncQueue'):
        """Initialize the InhibitionManager.
        
        Args:
            rules: List of InhibitRule config objects from the configuration
            incidents: The Incidents instance for accessing incident data
            application: The Application instance for messenger updates
            queue: The AsyncQueue instance for scheduling events
        """
        self.incidents = incidents
        self.application = application
        self.queue = queue
        self._init_rules(rules)
    
    def _init_rules(self, rules: List[InhibitRule]):
        """Initialize rules and tracking sets.
        
        Args:
            rules: List of InhibitRule config objects
        """
        self.rules: List[InhibitionRule] = [
            InhibitionRule(
                source_matchers=rule.source_matchers,
                target_matchers=rule.target_matchers,
                equal_labels=rule.equal or []
            )
            for rule in rules
        ]
        self.sources: Dict[int, Set[str]] = {i: set() for i in range(len(self.rules))}
        self.targets: Dict[int, Set[str]] = {i: set() for i in range(len(self.rules))}
    
    def reload_rules(self, rules: List[InhibitRule]):
        """Reload rules from configuration and rebuild tracking state.
        
        This method should be called when configuration is reloaded (e.g., SIGHUP).
        It clears all tracking state and rebuilds from active incidents.
        
        Args:
            rules: New list of InhibitRule config objects
        """
        logger.info("Reloading inhibition rules")
        self._init_rules(rules)
        self.restore_from_incidents()
        logger.info("Inhibition rules reloaded")
    
    def restore_from_incidents(self):
        """On startup, rebuild sources/targets from active incidents.
        
        Iterates over all active incidents and categorizes them into source/target
        sets based on the configured rules. Processes ALL active incidents to ensure
        fully consistent state with persisted childs/parents relationships.
        """
        if not self.rules:
            return
            
        logger.info("Restoring inhibition state from active incidents")
        
        for uniq_id in self.incidents.active_map.values():
            incident = self.incidents.uniq_ids.get(uniq_id)
            if not incident:
                continue
            
            for rule_idx, rule in enumerate(self.rules):
                if rule.is_source(incident):
                    self.sources[rule_idx].add(incident.uniq_id)
                    logger.debug("Restored source incident", 
                               extra={'uuid': incident.uuid, 'rule_idx': rule_idx,
                                     'status': incident.status, 'childs': len(incident.childs)})
                
                if rule.is_target(incident):
                    self.targets[rule_idx].add(incident.uniq_id)
                    logger.debug("Restored target incident",
                               extra={'uuid': incident.uuid, 'rule_idx': rule_idx,
                                     'status': incident.status, 'parents': len(incident.parents)})
        
        logger.info("Inhibition state restoration complete",
                   extra={'sources_count': sum(len(s) for s in self.sources.values()),
                         'targets_count': sum(len(t) for t in self.targets.values())})
    
    def would_be_inhibited(self, incident: 'Incident') -> bool:
        """Check if an incident would be inhibited by existing sources.
        
        This method checks if there are any active source incidents that would
        cause this incident to be frozen. Used to determine if a thread should
        be created in the messenger.
        
        Args:
            incident: The incident to check
            
        Returns:
            True if the incident would be inhibited, False otherwise
        """
        if not self.rules:
            return False
        
        for rule_idx, rule in enumerate(self.rules):
            if not rule.is_target(incident):
                continue
            
            for source_uniq_id in self.sources[rule_idx]:
                source = self.incidents.uniq_ids.get(source_uniq_id)
                if not source:
                    continue
                
                if rule.equal_labels_match(source, incident):
                    return True
        
        return False

    async def process_incident(self, incident: 'Incident'):
        """Process a new or updated incident against all rules.
        
        This is the main entry point called from AlertHandler when an incident
        is created or fires again.
        
        Args:
            incident: The incident to process
        """
        if not self.rules:
            return
        
        for rule_idx, rule in enumerate(self.rules):
            await self._process_incident_for_rule(incident, rule_idx, rule)
    
    async def _process_incident_for_rule(self, incident: 'Incident', rule_idx: int, rule: InhibitionRule):
        """Process an incident against a single rule.
        
        The flow is:
        1. Check if incident is target -> add to targets set
        2. Iterate sources set to find matching sources
        3. If source found: add relationships, freeze target
        4. Check if incident is source -> add to sources set
        5. Iterate targets set to find matching targets
        6. If targets found: add relationships, freeze targets
        
        Args:
            incident: The incident to process
            rule_idx: The index of the rule being processed
            rule: The InhibitionRule to apply
        """
        if rule.is_target(incident):
            self.targets[rule_idx].add(incident.uniq_id)
            await self._freeze_matching_targets(
                incident, self.sources[rule_idx], rule, incident_is_target=True
            )
        
        if rule.is_source(incident):
            self.sources[rule_idx].add(incident.uniq_id)
            await self._freeze_matching_targets(
                incident, self.targets[rule_idx], rule, incident_is_target=False
            )
    
    async def _freeze_matching_targets(
        self, 
        incident: 'Incident', 
        candidates: Set[str], 
        rule: InhibitionRule, 
        incident_is_target: bool
    ):
        """Check candidates and freeze matching source-target pairs.
        
        Args:
            incident: The incident being processed
            candidates: Set of uniq_ids to check against
            rule: The rule to use for equal_labels matching
            incident_is_target: If True, incident is target and candidates are sources;
                               if False, incident is source and candidates are targets
        """
        for candidate_uniq_id in candidates:
            if candidate_uniq_id == incident.uniq_id:
                continue
            
            candidate = self.incidents.uniq_ids.get(candidate_uniq_id)
            if not candidate:
                continue
            
            if incident_is_target:
                source, target = candidate, incident
            else:
                source, target = incident, candidate
            
            if rule.equal_labels_match(source, target):
                await self._freeze_target(source, target)
    
    async def handle_resolved(self, incident: 'Incident'):
        """Handle a resolved incident.
        
        If the incident is a source, remove it from source relationships
        and potentially unfreeze targets.
        
        Args:
            incident: The incident that was resolved
        """
        if not self.rules:
            return
        
        for rule_idx in range(len(self.rules)):
            if incident.uniq_id in self.sources[rule_idx]:
                await self._cleanup_source(incident)
    
    async def handle_closed(self, incident: 'Incident'):
        """Handle a closed incident.
        
        For sources: Same as resolved + remove from sources set
        For targets: If not frozen, just remove from targets set
        
        Args:
            incident: The incident that was closed
        """
        if not self.rules:
            return
        
        for rule_idx in range(len(self.rules)):
            if incident.uniq_id in self.sources[rule_idx]:
                await self._cleanup_source(incident)
                self.sources[rule_idx].discard(incident.uniq_id)
            
            if incident.uniq_id in self.targets[rule_idx]:
                if not incident.is_frozen():
                    self.targets[rule_idx].discard(incident.uniq_id)
    
    async def _cleanup_source(self, source: 'Incident'):
        """Clean up relationships when a source incident resolves or closes.
        
        Removes the source from all its children's parents lists,
        and unfreezes children that have no remaining parents.
        
        Args:
            source: The source incident
        """
        children_to_process = list(source.childs)
        
        for child_uniq_id in children_to_process:
            target = self.incidents.uniq_ids.get(child_uniq_id)
            if not target:
                continue
            
            if source.uniq_id in target.parents:
                target.parents.remove(source.uniq_id)
                target.dump()
                logger.debug("Removed parent from target",
                           extra={'source_uuid': source.uuid, 'target_uuid': target.uuid})
            
            if child_uniq_id in source.childs:
                source.childs.remove(child_uniq_id)
            
            await self._unfreeze_target_if_no_parents(target)
        
        source.dump()
    
    async def _freeze_target(self, source: 'Incident', target: 'Incident'):
        """Freeze a target incident due to inhibition.
        
        Updates parent/child relationships and freezes the target.
        If target was already in the system (source came after), updates messenger.
        
        Args:
            source: The source incident causing the inhibition
            target: The target incident to be frozen
        """
        if source.uniq_id in target.parents:
            return
        
        if target.uniq_id not in source.childs:
            source.childs.append(target.uniq_id)
            source.dump()
        
        if source.uniq_id not in target.parents:
            target.parents.append(source.uniq_id)
        
        was_frozen = target.is_frozen()
        target.freeze_by_inhibition()
        await self.queue.delete_by_id(target.uniq_id, delete_steps=True, delete_status=False)
        
        logger.info("Target frozen by inhibition",
                   extra={'source_uuid': source.uuid, 'target_uuid': target.uuid})
        
        if not was_frozen and target.ts:
            await self._update_target_thread(target)
    
    async def _unfreeze_target_if_no_parents(self, target: 'Incident'):
        """Schedule unfreeze for a target incident if it has no remaining parents.
        
        Args:
            target: The target incident to potentially unfreeze
        """
        if target.parents:
            return
        
        if not target.frozen_by_inhibition:
            return
        
        logger.info("Target has no more parents - scheduling unfreeze", extra={'uuid': target.uuid})
        await unfreeze_incident(target, self.application, self.queue)
    
    async def _update_target_thread(self, target: 'Incident'):
        """Update the messenger thread for a target incident.
        
        Args:
            target: The target incident whose thread should be updated
        """
        try:
            await self.application.update_thread(target)
            logger.info("Updated target thread to show inhibition", extra={'uuid': target.uuid})
        except Exception as e:
            logger.error("Failed to update target thread",
                        extra={'uuid': target.uuid, 'error': str(e)})
