from app.plugins.registry import PluginEntry, plugin_registry


def register_builtin_plugins() -> None:
    """Register built-in agent/worker/provider plugins (extensible without core changes)."""
    for name, kind, desc in [
        ("openai", "provider", "OpenAI GPT models"),
        ("anthropic", "provider", "Anthropic Claude models"),
        ("mock", "provider", "Offline mock provider"),
        ("cursor", "worker", "Cursor IDE worker (manual handoff)"),
        ("claude_code", "worker", "Claude Code CLI worker"),
        ("terminal", "worker", "Generic terminal worker"),
        ("github_actions", "worker", "GitHub Actions CI worker (planned)"),
        ("markdown_export", "exporter", "Session markdown export"),
    ]:
        plugin_registry.register(
            PluginEntry(kind=kind, name=name, description=desc)
        )
