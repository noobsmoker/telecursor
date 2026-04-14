"""
Trajectory Anonymizer
Removes/replaces personally identifiable information from trajectories
"""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Dict, Optional, List
from pathlib import Path


@dataclass
class AnonymizationConfig:
    """Configuration for trajectory anonymization"""
    # Session-level anonymization
    hash_user_id: bool = True
    salt: Optional[str] = None  # Custom salt for hashing
    
    # URL anonymization
    hash_urls: bool = True
    keep_url_patterns: bool = False  # Keep domain/structure patterns
    
    # DOM path handling
    remove_dom_paths: bool = False
    simplify_dom_paths: bool = True
    
    # Element IDs
    remove_element_ids: bool = False
    hash_element_ids: bool = True
    
    # Preserve privacy budget info
    preserve_privacy_metadata: bool = True
    
    # Quality filtering
    min_samples: int = 10
    max_duration_ms: int = 600000


class TrajectoryAnonymizer:
    """
    Anonymize cursor trajectory data while preserving utility.
    
    Applies:
    1. Session ID hashing (SHA-256 with salt)
    2. URL normalization/hashing
    3. DOM path simplification
    4. Element ID hashing
    """
    
    def __init__(self, config: Optional[AnonymizationConfig] = None):
        self.config = config or AnonymizationConfig()
        self._salt = self.config.salt or self._generate_salt()
    
    def _generate_salt(self) -> str:
        """Generate a random salt for hashing"""
        import secrets
        return secrets.token_hex(16)
    
    def _hash_string(self, text: str) -> str:
        """Hash a string with salt"""
        if not text:
            return ""
        combined = f"{self._salt}{text}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]
    
    def _hash_url(self, url: str) -> str:
        """
        Hash URL while optionally preserving structure.
        """
        if not url:
            return ""
        
        if self.config.keep_url_patterns:
            # Keep domain pattern but hash the rest
            match = re.match(r'^(https?://[^/]+)(/.*)?$', url)
            if match:
                domain, path = match.groups()
                domain_hash = self._hash_string(domain)[:16]
                return f"https://{domain_hash}.example{path or ''}"
        
        # Full hash
        return self._hash_string(url)
    
    def _simplify_dom_path(self, dom_path: str) -> str:
        """
        Simplify DOM path by removing dynamic attributes.
        
        Example:
          #nav-menu > li:nth-child(3) > a.active[href="/users/123"]
          -> #nav-menu > li > a
        """
        if not dom_path:
            return ""
        
        # Remove :nth-child, :nth-of-type, etc.
        dom_path = re.sub(r':nth-(?:child|of-type)\(\d+\)', '', dom_path)
        
        # Remove IDs (already have # prefix)
        dom_path = re.sub(r'#[\w-]+', '#ID', dom_path)
        
        # Remove classes (already have . prefix) - keep only first class
        dom_path = re.sub(r'\.([\w-]+)', lambda m: '.CLASS' if m.group(0).count('.') > 1 else m.group(0), dom_path)
        
        # Remove dynamic attributes like [href], [data-*], etc.
        dom_path = re.sub(r'\[[^\]]+\]', '[ATTR]', dom_path)
        
        # Remove trailing > with nothing after
        dom_path = re.sub(r'\s*>\s*$', '', dom_path)
        
        return dom_path.strip()
    
    def anonymize(self, trajectory: Dict) -> Optional[Dict]:
        """
        Anonymize a single trajectory.
        
        Args:
            trajectory: Raw trajectory dict
            
        Returns:
            Anonymized trajectory or None if filtering criteria not met
        """
        # Check quality criteria
        samples = trajectory.get('samples', [])
        if len(samples) < self.config.min_samples:
            return None
        
        duration = trajectory.get('duration_ms', 0)
        if duration > self.config.max_duration_ms:
            return None
        
        # Create anonymized copy
        anonymized = trajectory.copy()
        
        # Anonymize session_id
        if self.config.hash_user_id and 'session_id' in anonymized:
            original_id = anonymized['session_id']
            # If already hashed, re-hash with our salt
            if len(original_id) == 32 and re.match(r'^[a-f0-9]{32}$', original_id):
                anonymized['session_id'] = self._hash_string(original_id)
            else:
                anonymized['session_id'] = self._hash_string(original_id)
        
        # Anonymize page context URLs
        if 'page_context' in anonymized:
            pc = anonymized['page_context'].copy()
            
            if 'url_hash' in pc:
                # Already hashed, keep as-is
                pass
            elif 'url' in pc and self.config.hash_urls:
                pc['url_hash'] = self._hash_url(pc.pop('url', ''))
            
            if self.config.simplify_dom_paths and 'dom_path' in pc:
                pc['dom_path'] = self._simplify_dom_path(pc['dom_path'])
            
            if self.config.remove_dom_paths and 'dom_path' in pc:
                del pc['dom_path']
            
            if self.config.remove_element_ids and 'element_id' in pc:
                del pc['element_id']
            elif self.config.hash_element_ids and 'element_id' in pc:
                pc['element_id'] = self._hash_string(pc['element_id'])
            
            anonymized['page_context'] = pc
        
        # Anonymize samples - remove element IDs/tags if configured
        if 'samples' in anonymized:
            for sample in anonymized['samples']:
                if self.config.remove_element_ids:
                    sample.pop('element_id', None)
                elif self.config.hash_element_ids and 'element_id' in sample:
                    sample['element_id'] = self._hash_string(sample['element_id'])
                
                # Keep element_tag for now (anonymized by nature)
        
        # Mark as anonymized in privacy metadata
        if self.config.preserve_privacy_metadata:
            if 'privacy' not in anonymized:
                anonymized['privacy'] = {}
            anonymized['privacy']['anonymized'] = True
        
        return anonymized
    
    def anonymize_batch(self, trajectories: List[Dict]) -> List[Dict]:
        """
        Anonymize a batch of trajectories.
        
        Returns:
            List of anonymized trajectories (filtered by quality criteria)
        """
        results = []
        for traj in trajectories:
            anonymized = self.anonymize(traj)
            if anonymized is not None:
                results.append(anonymized)
        return results
    
    def anonymize_file(self, input_path: str, output_path: str) -> Dict:
        """
        Anonymize trajectories from a JSON file.
        
        Args:
            input_path: Path to input JSON file
            output_path: Path to output JSON file
            
        Returns:
            Dict with processing statistics
        """
        with open(input_path, 'r') as f:
            data = json.load(f)
        
        # Handle both single trajectory and array
        if isinstance(data, dict) and 'samples' in data:
            trajectories = [data]
        elif isinstance(data, list):
            trajectories = data
        else:
            raise ValueError("Invalid input format")
        
        original_count = len(trajectories)
        anonymized = self.anonymize_batch(trajectories)
        
        with open(output_path, 'w') as f:
            json.dump(anonymized, f, indent=2)
        
        return {
            'original_count': original_count,
            'anonymized_count': len(anonymized),
            'filtered_count': original_count - len(anonymized),
            'salt_used': self._salt[:8] + '...'
        }


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Anonymize cursor trajectories')
    parser.add_argument('input', help='Input JSON file')
    parser.add_argument('output', help='Output JSON file')
    parser.add_argument('--salt', help='Custom salt for hashing')
    parser.add_argument('--keep-url-patterns', action='store_true',
                        help='Keep URL structure patterns')
    
    args = parser.parse_args()
    
    config = AnonymizationConfig(
        salt=args.salt,
        keep_url_patterns=args.keep_url_patterns
    )
    
    anonymizer = TrajectoryAnonymizer(config)
    stats = anonymizer.anonymize_file(args.input, args.output)
    
    print(f"Anonymization complete:")
    print(f"  Original: {stats['original_count']}")
    print(f"  Anonymized: {stats['anonymized_count']}")
    print(f"  Filtered: {stats['filtered_count']}")


if __name__ == '__main__':
    main()