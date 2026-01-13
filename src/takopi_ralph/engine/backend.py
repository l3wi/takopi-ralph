"""Ralph engine backend for takopi.

Ralph wraps an inner engine (currently only Claude) with autonomous
loop semantics, PRD-driven development, and circuit breaker protection.
"""

from __future__ import annotations

from pathlib import Path

from takopi.api import EngineBackend, EngineConfig, Runner
from takopi.engines import list_backends
from takopi.utils.paths import get_run_base_dir

from .runner import RalphRunner

# Supported engines (will expand in future updates)
SUPPORTED_ENGINES = {"claude"}


def build_ralph_runner(config: EngineConfig, config_path: Path) -> Runner:
    """Build a RalphRunner from configuration.

    Config options (in takopi.toml [ralph] section):
        engine: Inner engine to use (default: "claude", only "claude" supported)
        max_loops: Maximum loop iterations (default: 100)
        prd_path: Path to prd.json (default: "prd.json")
        state_dir: Directory for state files (default: ".ralph")

    The inner engine's config is read from its own section (e.g., [claude]).
    """
    # Get working directory - use run base dir (set by takopi for current project)
    # Falls back to cwd if not in a takopi run context
    cwd = get_run_base_dir() or Path.cwd()

    # Get engine from config (default: claude)
    engine_id = config.get("engine", "claude")

    # Validate engine is supported
    if engine_id not in SUPPORTED_ENGINES:
        supported_list = ", ".join(sorted(SUPPORTED_ENGINES))
        raise ValueError(
            f"Ralph currently only supports these engines: {supported_list}. "
            f"Got '{engine_id}'. Other engines will be supported in future updates."
        )

    # Get the inner runner from Takopi's registry
    backends = {b.id: b for b in list_backends()}
    inner_backend = backends.get(engine_id)
    if inner_backend is None:
        raise ValueError(
            f"Engine '{engine_id}' not found in Takopi backends. "
            f"Make sure the engine is installed and registered."
        )

    # Build inner runner with its own config section
    # The inner engine reads from its own [engine_id] section in takopi.toml
    inner_runner = inner_backend.build_runner(config, config_path)

    # Extract Ralph-specific configuration
    max_loops = config.get("max_loops", 100)
    prd_path = config.get("prd_path", "prd.json")
    state_dir = config.get("state_dir", ".ralph")

    return RalphRunner(
        inner_runner=inner_runner,
        cwd=cwd,
        max_loops=max_loops,
        prd_path=prd_path,
        state_dir=state_dir,
    )


BACKEND = EngineBackend(
    id="ralph_engine",
    build_runner=build_ralph_runner,
    cli_cmd="claude",  # Ralph uses Claude under the hood (for now)
    install_cmd="pip install takopi-ralph",
)
