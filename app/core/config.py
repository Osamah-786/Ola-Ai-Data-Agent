"""Server-side feature configuration without loading local secret files."""

import os


def live_agents_enabled() -> bool:
    """Return true only when the deployment explicitly opts in."""
    return os.getenv("ENABLE_LIVE_AGENTS", "false").strip().lower() == "true"
