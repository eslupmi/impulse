from typing import Dict, List, Set, TYPE_CHECKING

from app.config.validation import InhibitRule, MessengerType
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
        self.incidents = incidents
        self.application = application
        self.queue = queue
        self._init_rules(rules)
    
    def reload_rules(self, rules: List[InhibitRule]):
        logger.info("Reloading inhibition rules")
        self._init_rules(rules)
        self.restore_from_incidents()
        logger.info("Inhibition rules reloaded")
    
    def restore_from_incidents(self):
        if not self.rules:
            return
            
        logger.debug("Restoring inhibition state from active incidents")
        
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
        
        logger.debug("Inhibition state restoration complete",
                   extra={'sources_count': sum(len(s) for s in self.sources.values()),
                         'targets_count': sum(len(t) for t in self.targets.values())})

    async def apply_current_inhibition(self):
        logger.debug("Applying current inhibition to existing incidents")

        source_ids = set().union(*self.sources.values()) if self.sources else set()
        target_ids = set().union(*self.targets.values()) if self.targets else set()

        for uniq_id in self.incidents.active_map.values():
            incident = self.incidents.uniq_ids.get(uniq_id)
            if not incident:
                continue

            if uniq_id in source_ids or uniq_id in target_ids:
                await self.process_incident(incident)
                continue

        logger.debug("Applied current inhibition to existing incidents")
    
    def would_be_inhibited(self, incident: 'Incident') -> bool:
        if not self.rules:
            return False
        
        for rule_idx, rule in enumerate(self.rules):
            if not rule.is_target(incident):
                continue
            
            for source_uniq_id in self.sources[rule_idx]:
                source = self.incidents.uniq_ids.get(source_uniq_id)
                if not source:
                    continue
                
                if rule.equal_labels_match(source, incident) and source.status != 'resolved':
                    return True
        
        return False

    async def process_incident(self, incident: 'Incident'):
        if not self.rules:
            return
        
        for rule_idx, rule in enumerate(self.rules):
            await self._process_incident_for_rule(incident, rule_idx, rule)
    
    async def handle_resolved(self, incident: 'Incident'):
        if not self.rules:
            return

        for rule_idx in range(len(self.rules)):
            if incident.uniq_id in self.sources[rule_idx]:
                await self._cleanup_source(incident)
    
    async def handle_closed(self, incident: 'Incident'):
        if not self.rules:
            return
        
        for rule_idx in range(len(self.rules)):
            if incident.uniq_id in self.sources[rule_idx]:
                await self._cleanup_source(incident)
                self.sources[rule_idx].discard(incident.uniq_id)
            
            if incident.uniq_id in self.targets[rule_idx]:
                if not incident.is_frozen():
                    self.targets[rule_idx].discard(incident.uniq_id)

    def _init_rules(self, rules: List[InhibitRule]):
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
    
    async def _cleanup_source(self, source: 'Incident'):
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

    async def _cleanup_untracked_incident(self, incident: 'Incident'):
        if incident.childs:
            await self._cleanup_source(incident)

        if incident.parents:
            for parent_uniq_id in list(incident.parents):
                parent = self.incidents.uniq_ids.get(parent_uniq_id)
                if parent and incident.uniq_id in parent.childs:
                    parent.childs.remove(incident.uniq_id)
                    parent.dump()
                incident.parents.remove(parent_uniq_id)
            incident.dump()

        await self._unfreeze_target_if_no_parents(incident)

    async def _process_incident_for_rule(self, incident: 'Incident', rule_idx: int, rule: InhibitionRule):
        done_1 = False
        done_2 = False
        if rule.is_target(incident):
            done_1 = True
            self.targets[rule_idx].add(incident.uniq_id)
            await self._freeze_matching_targets(
                incident, self.sources[rule_idx], rule, incident_is_target=True
            )
        if rule.is_source(incident):
            done_2 = True
            self.sources[rule_idx].add(incident.uniq_id)
            done = await self._freeze_matching_targets(
                incident, self.targets[rule_idx], rule, incident_is_target=False
            )
            if done and self.application.type != MessengerType.TELEGRAM:
                await self.application.update_incident_message(incident)
        if not done_1 and not done_2:
            await self._cleanup_untracked_incident(incident)

    async def _freeze_matching_targets(
        self,
        incident: 'Incident',
        candidates: Set[str],
        rule: InhibitionRule,
        incident_is_target: bool
    ):
        done = False
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

            if rule.equal_labels_match(source, target) and source.status != 'resolved':
                if await self._freeze_target(source, target):
                    done = True
        return done
    
    async def _freeze_target(self, source: 'Incident', target: 'Incident'):
        if source.uniq_id in target.parents:
            return False
        
        if target.uniq_id not in source.childs:
            source.childs.append(target.uniq_id)
            source.dump()
        
        if source.uniq_id not in target.parents:
            target.parents.append(source.uniq_id)
        target.freeze_by_inhibition()
        await self.queue.delete_by_id(target.uniq_id, delete_steps=True, delete_status=False)
        
        logger.info("Target frozen by inhibition",
                   extra={'source_uuid': source.uuid, 'target_uuid': target.uuid})
        if target.ts != '':
            await self.application.update_incident_message(target)
        return True

    async def _unfreeze_target_if_no_parents(self, target: 'Incident'):
        if target.parents:
            return
        
        if not target.frozen_by_inhibition:
            return
        
        logger.info("Target has no more parents - scheduling unfreeze", extra={'uuid': target.uuid})
        await unfreeze_incident(target, self.application, self.queue)
        await self.application.update_incident_message(target)
