from typing import List

from app.incident.incident import Incident
from app.route.matcher import Matcher


class InhibitionRule:
    """Represents a single inhibition rule with matching logic.
    
    Reuses the existing Matcher class from app/route/matcher.py which supports
    all AlertManager matcher syntax (=, !=, =~, !~).
    """
    
    def __init__(self, source_matchers: List[str], target_matchers: List[str], equal_labels: List[str]):
        """Initialize an inhibition rule.
        
        Args:
            source_matchers: List of matcher strings for source incidents (e.g., 'severity =~ "critical"')
            target_matchers: List of matcher strings for target incidents (e.g., 'severity =~ "warning"')
            equal_labels: List of labels that must be equal between source and target incidents
        """
        self.source_matchers = [Matcher(m) for m in source_matchers]
        self.target_matchers = [Matcher(m) for m in target_matchers]
        self.equal_labels = equal_labels or []
    
    def is_source(self, incident: Incident) -> bool:
        """Check if incident matches all source matchers.
        
        Args:
            incident: The incident to check
            
        Returns:
            True if incident matches all source matchers
        """
        return all(m.matches(incident.payload) for m in self.source_matchers)
    
    def is_target(self, incident: Incident) -> bool:
        """Check if incident matches all target matchers.
        
        Args:
            incident: The incident to check
            
        Returns:
            True if incident matches all target matchers
        """
        return all(m.matches(incident.payload) for m in self.target_matchers)
    
    def equal_labels_match(self, source: Incident, target: Incident) -> bool:
        """Check if equal labels have same values in both incidents.
        
        Args:
            source: The source incident
            target: The target incident
            
        Returns:
            True if all equal labels have the same value in both incidents
        """
        if not self.equal_labels:
            return True
        source_labels = source.payload.get('commonLabels', {})
        target_labels = target.payload.get('commonLabels', {})
        return all(
            source_labels.get(label) == target_labels.get(label)
            for label in self.equal_labels
        )
