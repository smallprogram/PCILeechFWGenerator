"""
Configuration Manager

Manages build configuration profiles and persistence.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..models.config import BuildConfiguration


class ConfigManager:
    """Manages build configuration and profiles."""

    def __init__(self):
        self.config_dir = Path.home() / ".pcileech" / "profiles"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._current_config: Optional[BuildConfiguration] = None

    def get_current_config(self) -> BuildConfiguration:
        """Get current configuration, creating default if none exists."""
        if self._current_config is None:
            self._current_config = BuildConfiguration()
        return self._current_config

    def set_current_config(self, config: BuildConfiguration) -> None:
        """Set current configuration."""
        self._current_config = config
        # Update last used timestamp
        self._current_config.last_used = datetime.now().isoformat()

    def save_profile(self, name: str, config: BuildConfiguration) -> None:
        """Save configuration profile to ~/.pcileech/profiles/."""
        # Update metadata
        config.name = name
        config.created_at = config.created_at or datetime.now().isoformat()
        config.last_used = datetime.now().isoformat()

        # Save to file
        profile_path = self.config_dir / f"{self._sanitize_filename(name)}.json"
        config.save_to_file(profile_path)

    def load_profile(self, name: str) -> BuildConfiguration:
        """Load configuration profile."""
        profile_path = self.config_dir / f"{self._sanitize_filename(name)}.json"
        if not profile_path.exists():
            raise FileNotFoundError(f"Profile '{name}' not found")

        config = BuildConfiguration.load_from_file(profile_path)
        # Update last used timestamp
        config.last_used = datetime.now().isoformat()
        self.save_profile(name, config)  # Save updated timestamp

        return config

    def list_profiles(self) -> List[Dict[str, str]]:
        """List available configuration profiles."""
        profiles = []
        for profile_file in self.config_dir.glob("*.json"):
            try:
                with open(profile_file, "r") as f:
                    data = json.load(f)
                    profiles.append(
                        {
                            "name": data.get("name", profile_file.stem),
                            "description": data.get("description", ""),
                            "created_at": data.get("created_at", ""),
                            "last_used": data.get("last_used", ""),
                            "filename": profile_file.name,
                        }
                    )
            except (json.JSONDecodeError, KeyError):
                # Skip invalid profile files
                continue

        # Sort by last used (most recent first)
        profiles.sort(key=lambda x: x.get("last_used", ""), reverse=True)
        return profiles

    def delete_profile(self, name: str) -> bool:
        """Delete a configuration profile."""
        profile_path = self.config_dir / f"{self._sanitize_filename(name)}.json"
        if profile_path.exists():
            profile_path.unlink()
            return True
        return False

    def profile_exists(self, name: str) -> bool:
        """Check if a profile exists."""
        profile_path = self.config_dir / f"{self._sanitize_filename(name)}.json"
        return profile_path.exists()

    def create_default_profiles(self) -> None:
        """Create default configuration profiles."""
        default_profiles = [
            {
                "name": "Network Device Standard",
                "description": "Standard configuration for network devices",
                "config": BuildConfiguration(
                    board_type="75t",
                    device_type="network",
                    advanced_sv=True,
                    enable_variance=True,
                    behavior_profiling=False,
                    profile_duration=30.0,
                    power_management=True,
                    error_handling=True,
                    performance_counters=True,
                    flash_after_build=False,
                ),
            },
            {
                "name": "Storage Device Optimized",
                "description": "Optimized configuration for storage devices",
                "config": BuildConfiguration(
                    board_type="100t",
                    device_type="storage",
                    advanced_sv=True,
                    enable_variance=True,
                    behavior_profiling=True,
                    profile_duration=45.0,
                    power_management=True,
                    error_handling=True,
                    performance_counters=True,
                    flash_after_build=False,
                ),
            },
            {
                "name": "Quick Development",
                "description": "Fast configuration for development and testing",
                "config": BuildConfiguration(
                    board_type="35t",
                    device_type="generic",
                    advanced_sv=False,
                    enable_variance=False,
                    behavior_profiling=False,
                    profile_duration=15.0,
                    power_management=False,
                    error_handling=False,
                    performance_counters=False,
                    flash_after_build=True,
                ),
            },
            {
                "name": "Full Featured",
                "description": "All features enabled for comprehensive analysis",
                "config": BuildConfiguration(
                    board_type="100t",
                    device_type="generic",
                    advanced_sv=True,
                    enable_variance=True,
                    behavior_profiling=True,
                    profile_duration=60.0,
                    power_management=True,
                    error_handling=True,
                    performance_counters=True,
                    flash_after_build=False,
                ),
            },
        ]

        for profile_data in default_profiles:
            if not self.profile_exists(profile_data["name"]):
                config = profile_data["config"]
                config.name = profile_data["name"]
                config.description = profile_data["description"]
                self.save_profile(profile_data["name"], config)

    def export_profile(self, name: str, export_path: Path) -> None:
        """Export a profile to a specific path."""
        config = self.load_profile(name)
        config.save_to_file(export_path)

    def import_profile(self, import_path: Path, new_name: Optional[str] = None) -> str:
        """Import a profile from a file."""
        config = BuildConfiguration.load_from_file(import_path)

        # Use provided name or extract from config
        profile_name = new_name or config.name or import_path.stem

        # Ensure unique name
        original_name = profile_name
        counter = 1
        while self.profile_exists(profile_name):
            profile_name = f"{original_name} ({counter})"
            counter += 1

        self.save_profile(profile_name, config)
        return profile_name

    def get_profile_summary(self, name: str) -> Dict[str, str]:
        """Get a summary of a profile's configuration."""
        try:
            config = self.load_profile(name)
            return {
                "name": config.name,
                "description": config.description,
                "board_type": config.board_type,
                "device_type": config.device_type,
                "features": config.feature_summary,
                "advanced": "Yes" if config.is_advanced else "No",
                "last_used": config.last_used or "Never",
            }
        except Exception:
            return {"error": "Failed to load profile"}

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize profile name for use as filename."""
        # Replace invalid characters with underscores
        invalid_chars = '<>:"/\\|?*'
        sanitized = name
        for char in invalid_chars:
            sanitized = sanitized.replace(char, "_")

        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip(" .")

        # Ensure it's not empty
        if not sanitized:
            sanitized = "unnamed_profile"

        return sanitized

    def validate_config(self, config: BuildConfiguration) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []

        try:
            # This will raise ValueError if invalid
            BuildConfiguration(**config.to_dict())
        except ValueError as e:
            issues.append(str(e))

        # Additional validation rules
        if config.behavior_profiling and config.profile_duration < 10:
            issues.append("Behavior profiling duration should be at least 10 seconds")

        if config.board_type == "35t" and config.is_advanced:
            issues.append("35t board may have limited resources for advanced features")

        return issues
