"""
Participant Registry Management

This module manages participant registration and condition assignment for the study.
It handles:
- Storing participant data in a JSON registry
- Random condition assignment for new participants
- Retrieving existing participant data
- Ensuring session persistence across technical difficulties

The registry is stored at: storage/participants/participant_registry.json
"""

import json
import random
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from config.conditions import STUDY_CONDITIONS, get_condition_by_key

logger = logging.getLogger(__name__)


class ParticipantRegistry:
    """
    Manages participant registration and condition assignment.
    
    Participants are identified by a login code and are randomly assigned
    to one of the conditions specified in STUDY_CONDITIONS.
    """
    
    def __init__(self, registry_file: str = 'storage/participants/participant_registry.json'):
        """
        Initialize the participant registry.
        
        Args:
            registry_file: Path to the JSON file storing participant data
        """
        self.registry_file = Path(registry_file)
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create empty registry if it doesn't exist
        if not self.registry_file.exists():
            self._save_registry({})
            logger.info(f"Created new participant registry at {self.registry_file}")
    
    def _load_registry(self) -> Dict[str, Any]:
        """Load the participant registry from disk."""
        try:
            with open(self.registry_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Corrupted registry file at {self.registry_file}, creating new one")
            return {}
        except Exception as e:
            logger.error(f"Error loading registry: {e}")
            return {}
    
    def _save_registry(self, registry: Dict[str, Any]) -> None:
        """Save the participant registry to disk."""
        try:
            with open(self.registry_file, 'w') as f:
                json.dump(registry, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving registry: {e}")
    
    def get_or_assign_condition(self, participant_code: str) -> str:
        """
        Get existing condition for participant or assign a new one.
        
        Args:
            participant_code: The participant's login code
        
        Returns:
            str: The condition key assigned to this participant
        
        Raises:
            ValueError: If STUDY_CONDITIONS is empty or contains invalid conditions
        """
        # Validate study configuration
        if not STUDY_CONDITIONS:
            raise ValueError("STUDY_CONDITIONS is empty. Configure at least one condition in config/conditions.py")
        
        # Load registry
        registry = self._load_registry()
        
        # Check if participant exists
        if participant_code in registry:
            participant = registry[participant_code]
            condition_key = participant['condition']
            logger.info(f"Returning participant {participant_code}: condition={condition_key}")
            return condition_key
        
        # New participant - Set condition based on participant code
        if participant_code[0].upper() == 'G':
            condition_key = 'general'
        elif participant_code[0].upper() == 'T':
            condition_key = 'teacher_to_adviser'
        else:
            condition_key = random.choice(STUDY_CONDITIONS)

        # Validate the condition exists
        try:
            get_condition_by_key(condition_key)
        except ValueError as e:
            logger.error(f"Invalid condition in STUDY_CONDITIONS: {condition_key}")
            raise
        
        # Create new participant entry
        participant_data = {
            'condition': condition_key,
            'created_at': datetime.now().isoformat()
        }
        
        registry[participant_code] = participant_data
        self._save_registry(registry)
        
        logger.info(f"Assigned new participant {participant_code}: condition={condition_key}")
        return condition_key
    
    def get_participant_info(self, participant_code: str) -> Optional[Dict[str, Any]]:
        """
        Get full information for a participant.
        
        Args:
            participant_code: The participant's login code
        
        Returns:
            dict: Participant information or None if not found
        """
        registry = self._load_registry()
        return registry.get(participant_code)
    
    def participant_exists(self, participant_code: str) -> bool:
        """
        Check if a participant is already registered.
        
        Args:
            participant_code: The participant's login code
        
        Returns:
            bool: True if participant exists, False otherwise
        """
        registry = self._load_registry()
        return participant_code in registry
    
    def get_condition_counts(self) -> Dict[str, int]:
        """
        Get the number of participants assigned to each condition.
        
        Returns:
            dict: Mapping of condition keys to participant counts
        """
        registry = self._load_registry()
        counts = {condition: 0 for condition in STUDY_CONDITIONS}
        
        for participant_data in registry.values():
            condition = participant_data.get('condition')
            if condition in counts:
                counts[condition] += 1
        
        return counts
    
    def get_total_participants(self) -> int:
        """
        Get the total number of registered participants.
        
        Returns:
            int: Total number of participants
        """
        registry = self._load_registry()
        return len(registry)
    
    def clear_registry(self) -> None:
        """
        Clear all participant data. Use with caution!
        This is useful for testing or starting a new study.
        """
        self._save_registry({})
        logger.warning("Participant registry cleared")


# Global registry instance
participant_registry = ParticipantRegistry()


def get_or_assign_participant_condition(participant_code: str) -> str:
    """
    Convenience function to get or assign a participant's condition.
    
    Args:
        participant_code: The participant's login code
    
    Returns:
        str: The condition key assigned to this participant
    """
    return participant_registry.get_or_assign_condition(participant_code)


def get_participant_stats() -> Dict[str, Any]:
    """
    Get statistics about participant distribution across conditions.
    
    Returns:
        dict: Statistics including total participants and per-condition counts
    """
    return {
        'total_participants': participant_registry.get_total_participants(),
        'condition_counts': participant_registry.get_condition_counts(),
        'study_conditions': STUDY_CONDITIONS
    }
