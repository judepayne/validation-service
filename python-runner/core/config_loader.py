"""Two-tier configuration loading with URI fetching and caching."""

import os
import yaml
import hashlib
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigLoader:
    """Handles two-tier configuration: local config + business config."""

    def __init__(self, local_config_path: str, cache_dir: Optional[str] = None):
        """
        Initialize config loader.

        Args:
            local_config_path: Path to local-config.yaml (tier 1)
            cache_dir: Directory for caching remote configs/rules (default: /tmp/validation-cache)
        """
        self.local_config_path = local_config_path
        self.cache_dir = Path(cache_dir or "/tmp/validation-cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load local config
        self.local_config = self._load_yaml(local_config_path)

        # Load business config (may be remote)
        business_config_uri = self.local_config.get("business_config_uri")

        if business_config_uri:
            self.business_config = self._load_config_from_uri(business_config_uri)
        else:
            # Backward compatibility: if no business_config_uri, treat local config as business config
            self.business_config = self.local_config

    def _load_yaml(self, path: str) -> Dict[str, Any]:
        """Load YAML file from disk."""
        with open(path) as f:
            return yaml.safe_load(f)

    def _load_config_from_uri(self, uri: str) -> Dict[str, Any]:
        """
        Load config from URI (with caching).

        Supports:
        - Relative paths - ../business-config.yaml
        - file:// - Local filesystem (absolute paths)
        - https:// - Remote HTTP/HTTPS
        - http:// - Remote HTTP

        Args:
            uri: Config URI or relative path

        Returns:
            Parsed YAML config
        """
        parsed = urllib.parse.urlparse(uri)

        # Handle relative paths (no scheme)
        if not parsed.scheme or parsed.scheme == '':
            # Relative path - resolve relative to local config directory
            config_dir = os.path.dirname(os.path.abspath(self.local_config_path))
            path = os.path.join(config_dir, uri)
            return self._load_yaml(path)

        if parsed.scheme == 'file':
            # Local file - load directly (absolute path)
            path = urllib.parse.unquote(parsed.path)
            return self._load_yaml(path)

        elif parsed.scheme in ('http', 'https'):
            # Remote file - cache it
            cache_key = hashlib.sha256(uri.encode()).hexdigest()
            cache_path = self.cache_dir / f"config_{cache_key}.yaml"

            if cache_path.exists():
                # Use cached version
                return self._load_yaml(str(cache_path))
            else:
                # Fetch and cache
                content = self._fetch_uri(uri)
                cache_path.write_text(content)
                return yaml.safe_load(content)

        else:
            raise ValueError(f"Unsupported URI scheme: {parsed.scheme} in {uri}")

    def _fetch_uri(self, uri: str) -> str:
        """Fetch content from HTTP/HTTPS URI."""
        try:
            with urllib.request.urlopen(uri) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            raise RuntimeError(f"Failed to fetch config from {uri}: {e}")

    def get_business_config(self) -> Dict[str, Any]:
        """Get business configuration (tier 2)."""
        return self.business_config

    def get_local_config(self) -> Dict[str, Any]:
        """Get local configuration (tier 1)."""
        return self.local_config

    def get_rules_base_uri(self) -> Optional[str]:
        """Get rules base URI from business config."""
        return self.business_config.get('rules_base_uri')

    def resolve_rule_uri(self, entity_type: str, rule_id: str) -> str:
        """
        Resolve rule URI from entity type and rule ID.

        Logic:
        1. If rules_base_uri exists: {base_uri}/{entity_type}/{rule_id}.py
        2. Otherwise: relative path ../rules/{entity_type}/{rule_id}.py

        Args:
            entity_type: Entity type (loan, facility, deal)
            rule_id: Rule ID (rule_001_v1)

        Returns:
            Absolute URI or relative path
        """
        base_uri = self.get_rules_base_uri()
        rule_filename = f"{rule_id}.py"

        if base_uri:
            # Construct URI from base
            if not base_uri.endswith('/'):
                base_uri += '/'
            return f"{base_uri}{entity_type}/{rule_filename}"
        else:
            # Backward compatibility: relative path
            return f"../rules/{entity_type}/{rule_filename}"
