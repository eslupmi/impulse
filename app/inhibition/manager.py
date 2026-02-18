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

        required_children_by_source, required_parents_by_target, tracked_ids = self._build_required_inhibition_graph()
        await self._reconcile_existing_inhibition_links(required_children_by_source, required_parents_by_target)

        updated_sources = await self._apply_missing_required_links(required_children_by_source)
        if updated_sources and self.application.type != MessengerType.TELEGRAM:
            await self._update_sources_messages(updated_sources)

        await self._cleanup_untracked_inhibition(tracked_ids)

        logger.debug("Applied current inhibition to existing incidents")

    def _build_required_inhibition_graph(self):
        required_children_by_source: Dict[str, Set[str]] = {}
        required_parents_by_target: Dict[str, Set[str]] = {}
        tracked_ids: Set[str] = set()

        for rule_idx, rule in enumerate(self.rules):
            source_ids = self.sources[rule_idx]
            target_ids = self.targets[rule_idx]
            tracked_ids.update(source_ids)
            tracked_ids.update(target_ids)

            for source_uniq_id in source_ids:
                source = self.incidents.uniq_ids.get(source_uniq_id)
                if not source or source.status == 'resolved':
                    continue

                for target_uniq_id in target_ids:
                    if source_uniq_id == target_uniq_id:
                        continue

                    target = self.incidents.uniq_ids.get(target_uniq_id)
                    if not target:
                        continue

                    if not rule.equal_labels_match(source, target):
                        continue

                    required_children_by_source.setdefault(source_uniq_id, set()).add(target_uniq_id)
                    required_parents_by_target.setdefault(target_uniq_id, set()).add(source_uniq_id)

        return required_children_by_source, required_parents_by_target, tracked_ids

    async def _reconcile_existing_inhibition_links(
        self,
        required_children_by_source: Dict[str, Set[str]],
        required_parents_by_target: Dict[str, Set[str]]
    ):
        for incident in self._iter_active_incidents():
            await self._reconcile_source_links(incident, required_children_by_source.get(incident.uniq_id, set()))
            await self._reconcile_target_links(incident, required_parents_by_target.get(incident.uniq_id, set()))

    async def _reconcile_source_links(self, source: 'Incident', required_childs: Set[str]):
        source_changed = False

        for child_uniq_id in list(source.childs):
            if child_uniq_id in required_childs:
                continue

            source.childs.remove(child_uniq_id)
            source_changed = True

            child = self.incidents.uniq_ids.get(child_uniq_id)
            if child and source.uniq_id in child.parents:
                child.parents.remove(source.uniq_id)
                child.dump()
                await self._unfreeze_target_if_no_parents(child)

        if source_changed:
            source.dump()

    async def _reconcile_target_links(self, target: 'Incident', required_parents: Set[str]):
        target_changed = False

        for parent_uniq_id in list(target.parents):
            if parent_uniq_id in required_parents:
                continue

            target.parents.remove(parent_uniq_id)
            target_changed = True

            parent = self.incidents.uniq_ids.get(parent_uniq_id)
            if parent and target.uniq_id in parent.childs:
                parent.childs.remove(target.uniq_id)
                parent.dump()

        if target_changed:
            target.dump()
            await self._unfreeze_target_if_no_parents(target)

    async def _apply_missing_required_links(self, required_children_by_source: Dict[str, Set[str]]) -> Set[str]:
        updated_sources: Set[str] = set()

        for source_uniq_id, target_uniq_ids in required_children_by_source.items():
            source = self.incidents.uniq_ids.get(source_uniq_id)
            if not source:
                continue

            for target_uniq_id in target_uniq_ids:
                target = self.incidents.uniq_ids.get(target_uniq_id)
                if not target:
                    continue

                if await self._freeze_target(source, target):
                    updated_sources.add(source_uniq_id)

        return updated_sources

    async def _update_sources_messages(self, source_ids: Set[str]):
        for source_uniq_id in source_ids:
            source = self.incidents.uniq_ids.get(source_uniq_id)
            if source:
                await self.application.update_incident_message(source)

    async def _cleanup_untracked_inhibition(self, tracked_ids: Set[str]):
        for incident in self._iter_active_incidents():
            if incident.uniq_id not in tracked_ids and (incident.childs or incident.parents or incident.frozen_by_inhibition):
                await self._cleanup_untracked_incident(incident)

    def _iter_active_incidents(self):
        for uniq_id in self.incidents.active_map.values():
            incident = self.incidents.uniq_ids.get(uniq_id)
            if incident:
                yield incident
    
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
        if rule.is_target(incident):
            self.targets[rule_idx].add(incident.uniq_id)
            await self._freeze_matching_targets(
                incident, self.sources[rule_idx], rule, incident_is_target=True
            )
        if rule.is_source(incident):
            self.sources[rule_idx].add(incident.uniq_id)
            done = await self._freeze_matching_targets(
                incident, self.targets[rule_idx], rule, incident_is_target=False
            )
            if done and self.application.type != MessengerType.TELEGRAM:
                await self.application.update_incident_message(incident)

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
