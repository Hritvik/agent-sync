"""Path utilities for agent-sync configuration."""

import os
from pathlib import Path
from platform import system


def get_config_dir() -> Path:
    """Get the agent-sync configuration directory."""
    # Respect XDG_CONFIG_HOME on Linux/macOS, APPDATA on Windows
    if system() == "Windows":
        config_home = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    
    return config_home / "agent-sync"


def get_servers_path() -> Path:
    """Get the path to the servers.yaml configuration file."""
    return get_config_dir() / "servers.yaml"


def get_profiles_path() -> Path:
    """Get the path to the profiles.yaml configuration file."""
    return get_config_dir() / "profiles.yaml"


def get_state_path() -> Path:
    """Get the path to the state.json file."""
    return get_config_dir() / "state.json"


def get_backups_dir() -> Path:
    """Get the path to the backups directory."""
    return get_config_dir() / "backups"


def get_skills_dir() -> Path:
    """Get the path to the canonical skills directory."""
    return Path.home() / ".agents" / "skills"


def get_skills_registry_path() -> Path:
    """Get the path to the skills.yaml configuration file."""
    return get_config_dir() / "skills.yaml"


def ensure_config_dirs() -> None:
    """Ensure all configuration directories exist."""
    get_config_dir().mkdir(parents=True, exist_ok=True)
    get_backups_dir().mkdir(parents=True, exist_ok=True)


def ensure_skills_dir() -> None:
    """Ensure the canonical skills directory exists."""
    get_skills_dir().mkdir(parents=True, exist_ok=True)
