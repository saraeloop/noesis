# Phase 1: CLI Modernization Plan (Final)

> **Goal**: Transform the Noēsis CLI into a polished, observability-first terminal experience with a unified registry as the single source of truth.

---

## 1. The Ideal First Impression

When a user types `noesis`:

```
╭─────────────────────────────────────────────────────────────────────────────╮
│  ◉ Noēsis v1.0.0                                    Cognitive Runtime CLI   │
├─────────────────────────────────────────────────────────────────────────────┤
│   Observable episodes · Governance · Deterministic replay                   │
│                                                                             │
│   ┌─ Quick Start ────────────────────────────────────────────────────────┐  │
│   │  $ noesis run "Summarize this repo"         Run a baseline episode   │  │
│   │  $ noesis ps                                Recent episodes          │  │
│   │  $ noesis view <episode_id>                 Inspect dashboard        │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌─ Recent Episodes ────────────────────────────────────────────────────┐  │
│   │  12:34  ep_01JX…YZ  success   "Summarize the changelog"      0.8s    │  │
│   │  11:02  ep_01JW…AB  vetoed    "Deploy to prod"               1.2s    │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌─ Observe ──────────────────┐  ┌─ Verify ─────────────────────────────┐  │
│   │  ps         Recent runs    │  │  artifacts      Check integrity      │  │
│   │  view       Dashboard      │  │  diagnostics    Replay compare       │  │
│   │  events     Event stream   │  └──────────────────────────────────────┘  │
│   └────────────────────────────┘                                            │
│                                                                             │
│   → noesis help                                                             │
╰─────────────────────────────────────────────────────────────────────────────╯
```

**Exit code**: `0` — home is a valid response
**No blocking**: No "Press Enter" interaction

---

## 2. Unified CommandSpec Registry (Single Source of Truth)

### The Problem with Two Dicts

Having `COMMANDS` and `COMMAND_META` as separate dicts creates drift. Commands get added but metadata isn't updated, or vice versa.

### The Solution: Unified CommandSpec

```python
# noesis/cli/registry.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import argparse


class Command(Protocol):
    """Protocol for CLI commands."""
    name: str
    help: str

    def add_arguments(self, parser: argparse.ArgumentParser) -> None: ...
    def run(self, args: argparse.Namespace, ctx, renderer) -> int: ...


CommandGroup = Literal["execute", "observe", "verify", "maintain"]


@dataclass(frozen=True)
class CommandMeta:
    """Presentation metadata for a command."""
    group: CommandGroup
    one_liner: str
    examples: tuple[str, ...] = ()
    show_on_home: bool = False


@dataclass(frozen=True)
class CommandSpec:
    """Unified command specification: logic + presentation."""
    cmd: Command
    meta: CommandMeta


# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED REGISTRY (single source of truth)
# ─────────────────────────────────────────────────────────────────────────────

from .commands.run import RUN_COMMAND
from .commands.solve import SOLVE_COMMAND
from .commands.ps import PS_COMMAND
from .commands.view import VIEW_COMMAND
from .commands.list import LIST_COMMAND
from .commands.show import SHOW_COMMAND
from .commands.events import EVENTS_COMMAND
from .commands.insight import INSIGHT_COMMAND
from .commands.artifacts import ARTIFACTS_COMMAND
from .commands.validate_ports import VALIDATE_PORTS_COMMAND
from .commands.diagnostics import DIAGNOSTICS_COMMAND
from .commands.migrate import MIGRATE_COMMAND
from .commands.version import VERSION_COMMAND
from .commands.new import NEW_COMMAND
from .commands.help import HELP_COMMAND


REGISTRY: dict[str, CommandSpec] = {
    # ── Execute ──────────────────────────────────────────────────────────────
    "run": CommandSpec(
        cmd=RUN_COMMAND,
        meta=CommandMeta(
            group="execute",
            one_liner="Run a baseline episode (no adapter)",
            examples=('noesis run "Summarize this repo"',),
            show_on_home=True,
        ),
    ),
    "solve": CommandSpec(
        cmd=SOLVE_COMMAND,
        meta=CommandMeta(
            group="execute",
            one_liner="Run an episode with an adapter/flow",
            examples=('noesis solve react "Weekly plan"',),
        ),
    ),

    # ── Observe ──────────────────────────────────────────────────────────────
    "ps": CommandSpec(
        cmd=PS_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="Compact table of recent episodes",
            examples=("noesis ps", "noesis ps --limit 10"),
            show_on_home=True,
        ),
    ),
    "view": CommandSpec(
        cmd=VIEW_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="Inspect timeline, metrics, and governance",
            examples=("noesis view <episode_id>",),
            show_on_home=True,
        ),
    ),
    "list": CommandSpec(
        cmd=LIST_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="List recent episodes",
            examples=("noesis list",),
        ),
    ),
    "show": CommandSpec(
        cmd=SHOW_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="Show a single episode summary",
            examples=("noesis show <episode_id>",),
        ),
    ),
    "events": CommandSpec(
        cmd=EVENTS_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="Print or stream episode events",
            examples=("noesis events <episode_id>",),
            show_on_home=True,
        ),
    ),
    "insight": CommandSpec(
        cmd=INSIGHT_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="Show computed insight metrics",
            examples=("noesis insight <episode_id>",),
        ),
    ),

    # ── Verify ───────────────────────────────────────────────────────────────
    "artifacts": CommandSpec(
        cmd=ARTIFACTS_COMMAND,
        meta=CommandMeta(
            group="verify",
            one_liner="Manifest utilities and verification",
            examples=("noesis artifacts verify <episode_id>",),
            show_on_home=True,
        ),
    ),
    "validate-ports": CommandSpec(
        cmd=VALIDATE_PORTS_COMMAND,
        meta=CommandMeta(
            group="verify",
            one_liner="Validate configured runtime ports",
            examples=("noesis validate-ports",),
        ),
    ),
    "diagnostics": CommandSpec(
        cmd=DIAGNOSTICS_COMMAND,
        meta=CommandMeta(
            group="verify",
            one_liner="Stability diagnostics and replay compare",
            examples=("noesis diagnostics replay <episode_id>",),
            show_on_home=True,
        ),
    ),

    # ── Maintain ─────────────────────────────────────────────────────────────
    "migrate": CommandSpec(
        cmd=MIGRATE_COMMAND,
        meta=CommandMeta(
            group="maintain",
            one_liner="Codemod deprecated shims to the modern API",
            examples=("noesis migrate --check",),
        ),
    ),
    "version": CommandSpec(
        cmd=VERSION_COMMAND,
        meta=CommandMeta(
            group="maintain",
            one_liner="Print CLI and core versions",
            examples=("noesis version",),
        ),
    ),
    "new": CommandSpec(
        cmd=NEW_COMMAND,
        meta=CommandMeta(
            group="maintain",
            one_liner="Scaffold a starter flow or policy",
            examples=("noesis new flow my_flow",),
        ),
    ),
    "help": CommandSpec(
        cmd=HELP_COMMAND,
        meta=CommandMeta(
            group="maintain",
            one_liner="Show help for commands",
            examples=("noesis help", "noesis help view"),
        ),
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# BACKWARDS COMPAT: expose COMMANDS dict for existing call sites
# ─────────────────────────────────────────────────────────────────────────────

COMMANDS: dict[str, Command] = {name: spec.cmd for name, spec in REGISTRY.items()}


# ─────────────────────────────────────────────────────────────────────────────
# QUERY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_specs_by_group(group: CommandGroup) -> list[CommandSpec]:
    """Get all command specs in a group, sorted by name."""
    return sorted(
        [spec for spec in REGISTRY.values() if spec.meta.group == group],
        key=lambda s: s.cmd.name,
    )


def get_home_specs() -> list[CommandSpec]:
    """Get commands flagged for home screen display."""
    return [spec for spec in REGISTRY.values() if spec.meta.show_on_home]


def get_all_groups() -> tuple[CommandGroup, ...]:
    """Get all group names in display order."""
    return ("execute", "observe", "verify", "maintain")
```

---

## 3. Content Builders (Derived from Registry)

### File: `noesis/cli/content/home.py`

```python
"""Home screen content, derived from registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..registry import REGISTRY, get_specs_by_group


@dataclass(frozen=True)
class QuickStartItem:
    command: str
    description: str


@dataclass(frozen=True)
class CommandPreview:
    name: str
    one_liner: str


@dataclass(frozen=True)
class RecentEpisode:
    """Recent episode for home screen (summary-only data)."""
    time_str: str        # HH:MM
    episode_short: str   # truncated ID (middle ellipsis)
    status: str          # success | vetoed | error
    task: str            # truncated task
    duration: str        # e.g., "0.8s"


@dataclass(frozen=True)
class HomeScreen:
    version: str
    tagline: str
    quick_start: tuple[QuickStartItem, ...]
    recent_episodes: tuple[RecentEpisode, ...]
    observe_commands: tuple[CommandPreview, ...]
    verify_commands: tuple[CommandPreview, ...]
    footer_hint: str


def build_home_screen(
    version: str,
    *,
    recent_episodes: Sequence[RecentEpisode] = (),
) -> HomeScreen:
    """Build home screen from registry metadata."""

    # Quick start: curated set
    quick_start_names = ["run", "ps", "view"]
    quick_start = tuple(
        QuickStartItem(
            command=REGISTRY[name].meta.examples[0] if REGISTRY[name].meta.examples else f"noesis {name}",
            description=REGISTRY[name].meta.one_liner,
        )
        for name in quick_start_names
        if name in REGISTRY
    )

    # Observe group (show_on_home only)
    observe = tuple(
        CommandPreview(name=spec.cmd.name, one_liner=spec.meta.one_liner)
        for spec in get_specs_by_group("observe")
        if spec.meta.show_on_home
    )

    # Verify group (show_on_home only)
    verify = tuple(
        CommandPreview(name=spec.cmd.name, one_liner=spec.meta.one_liner)
        for spec in get_specs_by_group("verify")
        if spec.meta.show_on_home
    )

    return HomeScreen(
        version=version,
        tagline="Observable episodes · Governance · Deterministic replay",
        quick_start=quick_start,
        recent_episodes=tuple(recent_episodes),
        observe_commands=observe,
        verify_commands=verify,
        footer_hint="noesis help",
    )
```

### File: `noesis/cli/content/help.py`

```python
"""Help screen content, derived from registry."""
from __future__ import annotations

from dataclasses import dataclass

from ..registry import REGISTRY, get_specs_by_group, get_all_groups, CommandGroup


@dataclass(frozen=True)
class CommandInfo:
    name: str
    one_liner: str


@dataclass(frozen=True)
class CommandGroupInfo:
    title: str
    commands: tuple[CommandInfo, ...]


@dataclass(frozen=True)
class HelpScreen:
    version: str
    tagline: str
    usage: str
    groups: tuple[CommandGroupInfo, ...]
    examples: tuple[str, ...]
    footer: str


_GROUP_TITLES: dict[CommandGroup, str] = {
    "execute": "Execute",
    "observe": "Observe",
    "verify": "Verify",
    "maintain": "Maintain",
}


def build_help_screen(version: str) -> HelpScreen:
    """Build help screen from registry metadata."""

    groups = tuple(
        CommandGroupInfo(
            title=_GROUP_TITLES[group],
            commands=tuple(
                CommandInfo(name=spec.cmd.name, one_liner=spec.meta.one_liner)
                for spec in get_specs_by_group(group)
            ),
        )
        for group in get_all_groups()
    )

    # Collect first example from each command (up to 5)
    examples: list[str] = []
    for spec in REGISTRY.values():
        if spec.meta.examples:
            examples.append(spec.meta.examples[0])
        if len(examples) >= 5:
            break

    return HelpScreen(
        version=version,
        tagline="Run, inspect, and govern cognitive episodes.",
        usage="noesis <command> [options]",
        groups=groups,
        examples=tuple(examples),
        footer="Tip: noesis help <command> or noesis <command> -h for details.",
    )
```

---

## 4. Theme Tokens + Layout Tiers

### File: `noesis/cli/theme.py`

```python
"""Theme tokens, layout constants, and breakpoints."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class Breakpoint(Enum):
    """Terminal width breakpoints."""
    COMPACT = "compact"    # < 60 cols
    STANDARD = "standard"  # 60-99 cols
    WIDE = "wide"          # >= 100 cols


COMPACT_MAX = 60
STANDARD_MAX = 100


def detect_breakpoint(width: int) -> Breakpoint:
    """Detect breakpoint from terminal width."""
    if width < COMPACT_MAX:
        return Breakpoint.COMPACT
    if width < STANDARD_MAX:
        return Breakpoint.STANDARD
    return Breakpoint.WIDE


@dataclass(frozen=True)
class ThemeLayout:
    """Layout constants for consistent spacing."""
    panel_padding: tuple[int, int] = (1, 2)
    panel_width: int = 88
    max_width: int = 100
    min_width: int = 40
    gutter: int = 2
    indent: int = 2
    command_col_width: int = 14
    description_col_width: int = 40


@dataclass(frozen=True)
class ThemeTokens:
    styles: Mapping[str, str]
    layout: ThemeLayout = ThemeLayout()


def build_theme_tokens() -> ThemeTokens:
    return ThemeTokens(
        styles={
            # Text
            "title": "bold bright_cyan",
            "accent": "bright_cyan",
            "muted": "grey66",
            "hint": "dim",
            "key": "bright_cyan",
            "val": "white",

            # Status
            "ok": "green",
            "warn": "yellow",
            "err": "bold red",

            # Structure
            "border": "grey42",
            "panel": "grey50",
            "header": "bold bright_cyan",

            # Badges
            "badge": "black on bright_cyan",
            "badge.success": "bold white on green",
            "badge.warn": "bold black on yellow",
            "badge.error": "bold white on red",

            # Navigation
            "nav.arrow": "bright_blue",
            "nav.command": "bold bright_cyan",

            # Groups
            "group.title": "bold bright_cyan",

            # Home
            "home.tagline": "italic grey74",

            # Phases (for timeline)
            "phase.start": "cyan",
            "phase.intuition": "magenta",
            "phase.observe": "bright_black",
            "phase.interpret": "bright_blue",
            "phase.plan": "bright_cyan",
            "phase.direction": "blue",
            "phase.insight": "green",
            "phase.act": "white",
            "phase.reflect": "green",
            "phase.learn": "cyan",
            "phase.terminate": "yellow",
            "phase.error": "bold red",
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# ENFORCED STYLE: One border style everywhere
# ─────────────────────────────────────────────────────────────────────────────

def get_box_style():
    """Return the single box style used across all Rich panels/tables."""
    try:
        from rich import box
        return box.ROUNDED
    except ImportError:
        return None
```

---

## 5. Renderer Updates

### Key Rules

1. **One box style**: Use `box.ROUNDED` for every Rich panel/table
2. **No blocking**: Remove all `console.input()` calls
3. **Help routing**: Command-specific help embeds argparse text in a styled panel

### File: `noesis/cli/render/richy.py` (Key Methods)

```python
from rich import box

# THE box style (enforced everywhere)
_BOX = box.ROUNDED


def print_home(self, screen: HomeScreen) -> None:
    if self.quiet:
        return

    bp = detect_breakpoint(self.console.size.width)
    border = _safe_style(self.console, "border", "grey42")

    # Header
    header_grid = Table.grid(expand=True)
    header_grid.add_column(ratio=1)
    header_grid.add_column(justify="right")
    header_grid.add_row(
        Text(f"Noēsis v{screen.version}", style="title"),
        Text("Cognitive Runtime CLI", style="muted"),
    )
    header_grid.add_row(Text(screen.tagline, style="home.tagline"))
    self.console.print(Panel(header_grid, box=_BOX, border_style=border))

    # Quick Start
    qs_body = "\n".join(
        f"[muted]$[/] [nav.command]{item.command}[/]  [muted]{item.description}[/]"
        for item in screen.quick_start
    )
    self.console.print(Panel(qs_body, title="[group.title]Quick Start[/]", box=_BOX, border_style=border))

    # Recent Episodes (if any)
    if screen.recent_episodes:
        ep_table = Table(box=None, show_header=False, expand=True, padding=(0, 1))
        ep_table.add_column("time", style="muted", width=5)
        ep_table.add_column("id", style="accent", width=12)
        ep_table.add_column("status", width=7)
        ep_table.add_column("task", style="val")
        ep_table.add_column("dur", style="muted", justify="right", width=5)

        for ep in screen.recent_episodes[:5]:
            ep_table.add_row(
                ep.time_str,
                ep.episode_short,
                Text(ep.status, style=_status_style(ep.status)),
                _truncate(ep.task, 35),
                ep.duration,
            )
        self.console.print(Panel(ep_table, title="[group.title]Recent Episodes[/]", box=_BOX, border_style=border))

    # Command groups
    observe_body = "\n".join(f"[accent]{c.name:<12}[/] [muted]{c.one_liner}[/]" for c in screen.observe_commands)
    verify_body = "\n".join(f"[accent]{c.name:<14}[/] [muted]{c.one_liner}[/]" for c in screen.verify_commands)

    observe_panel = Panel(observe_body, title="[group.title]Observe[/]", box=_BOX, border_style=border)
    verify_panel = Panel(verify_body, title="[group.title]Verify[/]", box=_BOX, border_style=border)

    if bp == Breakpoint.WIDE:
        from rich.columns import Columns
        self.console.print(Columns([observe_panel, verify_panel], expand=True))
    else:
        self.console.print(observe_panel)
        self.console.print(verify_panel)

    # Footer
    self.console.print(Text(f"→ {screen.footer_hint}", style="nav.arrow"))


def print_command_help(self, text: str, *, title: str | None = None) -> None:
    """Render command help (argparse text) in a styled panel."""
    if self.quiet:
        return
    border = _safe_style(self.console, "border", "grey42")
    # Embed argparse text as-is, but in a nice panel
    self.console.print(Panel(
        text.rstrip(),
        title=f"[title]{title}[/]" if title else None,
        box=_BOX,
        border_style=border,
    ))
```

---

## 6. Main Routing

### File: `noesis/cli/main.py`

```python
def main(argv: Optional[Sequence[str]] = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]

    # Early help detection
    help_target = _detect_help_target(raw_argv)
    if help_target is not None:
        options = _options_from_argv(raw_argv)
        ctx = build_context(options, port_specs=[])
        renderer = _select_renderer(ctx, options)
        _render_help(renderer, ctx, command_name=help_target)
        return 0

    formatter = _choose_formatter()
    parser, _ = build_parser(formatter)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code

    # ... options extraction ...

    ctx = build_context(options, port_specs)
    renderer = _select_renderer(ctx, options)
    command = getattr(args, "command_obj", None)

    # ── NO COMMAND PROVIDED ──────────────────────────────────────────────────
    if command is None:
        if options.json:
            return EXIT_USAGE  # exit 2, no output
        if options.quiet:
            return 0  # exit 0, no output

        # Build home screen with recent episodes (summary-only)
        recent = _fetch_recent_episodes(ctx, limit=5)
        home = build_home_screen(ctx.version, recent_episodes=recent)
        renderer.print_home(home)
        return 0  # exit 0

    # ── EXECUTE COMMAND ──────────────────────────────────────────────────────
    provider = ns.session_provider()
    try:
        with provider.use(ctx.session):
            return command.run(args, ctx, renderer)
    except ns.NoesisVeto as veto:
        print(veto.advice or "Vetoed by policy", file=sys.stderr)
        return EXIT_VETO
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return EXIT_USAGE
    except Exception as err:
        print(f"error: {err}", file=sys.stderr)
        return EXIT_ERROR


def _fetch_recent_episodes(ctx, limit: int = 5) -> list[RecentEpisode]:
    """
    Fetch recent episodes for home screen.

    HARD REQUIREMENT: Summary-only fast path.
    - Read only summary.json per episode
    - No events.jsonl, no schema parsing
    - If slow or fails, return empty list
    """
    try:
        from .content.home import RecentEpisode
        from pathlib import Path
        import json

        runs_dir = Path(ctx.config_snapshot.runs_dir)
        if not runs_dir.exists():
            return []

        # Find episode dirs, sort by mtime, limit
        episode_dirs = sorted(
            (d for d in runs_dir.iterdir() if d.is_dir() and (d / "summary.json").exists()),
            key=lambda d: (d / "summary.json").stat().st_mtime,
            reverse=True,
        )[:limit]

        results = []
        for ep_dir in episode_dirs:
            try:
                summary = json.loads((ep_dir / "summary.json").read_text())
                started = summary.get("started_at", "")[:5]  # HH:MM
                episode_id = summary.get("episode_id", ep_dir.name)
                # Truncate middle: ep_01JXYZ...1234
                if len(episode_id) > 12:
                    episode_short = episode_id[:7] + "…" + episode_id[-4:]
                else:
                    episode_short = episode_id
                status = summary.get("outcome", {}).get("status", "?")
                task = summary.get("task", "")[:35]
                duration = f"{summary.get('duration_sec', 0):.1f}s"

                results.append(RecentEpisode(
                    time_str=started,
                    episode_short=episode_short,
                    status=status,
                    task=task,
                    duration=duration,
                ))
            except Exception:
                continue

        return results
    except Exception:
        return []
```

---

## 7. Help Command

### File: `noesis/cli/commands/help.py`

```python
"""Help command: noesis help [command]"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

from ..context import CLIContext
from ..content.help import build_help_screen
from ..parser import build_command_parser
from ..registry import REGISTRY


@dataclass
class HelpCommand:
    name: str = "help"
    help: str = "Show help for commands"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("command", nargs="?", help="Command to get help for")

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer) -> int:
        command_name = getattr(args, "command", None)

        if command_name:
            spec = REGISTRY.get(command_name)
            if not spec:
                renderer.echo(f"Unknown command: {command_name}")
                renderer.print_help(build_help_screen(ctx.version))
                return 2

            # Get argparse help text and render it styled
            command_parser = build_command_parser(command_name, argparse.RawTextHelpFormatter)
            if command_parser:
                renderer.print_command_help(
                    command_parser.format_help(),
                    title=f"noesis {command_name}",
                )
            return 0

        # Full help screen
        renderer.print_help(build_help_screen(ctx.version))
        return 0


HELP_COMMAND = HelpCommand()
```

---

## 8. Tests

### Registry Invariants

```python
# tests/cli/test_registry.py

from noesis.cli.registry import REGISTRY, get_all_groups


def test_registry_groups_are_valid():
    """Every command has a valid group."""
    valid_groups = set(get_all_groups())
    for name, spec in REGISTRY.items():
        assert spec.meta.group in valid_groups, f"{name} has invalid group: {spec.meta.group}"


def test_home_commands_have_examples():
    """Commands shown on home must have at least one example."""
    for name, spec in REGISTRY.items():
        if spec.meta.show_on_home:
            assert spec.meta.examples, f"{name} is show_on_home but has no examples"


def test_command_name_matches_key():
    """Registry key must match command.name."""
    for name, spec in REGISTRY.items():
        assert spec.cmd.name == name, f"Key '{name}' != cmd.name '{spec.cmd.name}'"
```

### Home Screen Structure

```python
# tests/cli/test_home_help.py

from noesis import cli
from noesis.cli.registry import REGISTRY


class TestHomeScreen:
    def test_home_exits_zero(self):
        assert cli.main([]) == 0

    def test_home_has_quick_start(self, capsys):
        cli.main([])
        assert "Quick Start" in capsys.readouterr().out

    def test_home_has_observe_section(self, capsys):
        cli.main([])
        out = capsys.readouterr().out
        assert "Observe" in out or "ps" in out

    def test_home_has_verify_section(self, capsys):
        cli.main([])
        out = capsys.readouterr().out
        assert "Verify" in out or "artifacts" in out

    def test_home_has_help_hint(self, capsys):
        cli.main([])
        assert "noesis help" in capsys.readouterr().out

    def test_home_does_not_block(self, monkeypatch):
        import io
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        assert cli.main([]) == 0  # Does not hang

    def test_home_json_exits_usage_error(self):
        assert cli.main(["--json"]) == 2

    def test_home_quiet_no_output(self, capsys):
        cli.main(["--quiet"])
        assert capsys.readouterr().out.strip() == ""


class TestHelpScreen:
    def test_help_exits_zero(self):
        assert cli.main(["help"]) == 0

    def test_help_has_all_groups(self, capsys):
        cli.main(["help"])
        out = capsys.readouterr().out
        for group in ("Execute", "Observe", "Verify", "Maintain"):
            assert group in out

    def test_help_lists_all_commands(self, capsys):
        cli.main(["help"])
        out = capsys.readouterr().out
        for name in REGISTRY:
            assert name in out, f"Missing command: {name}"

    def test_help_command_shows_usage(self, capsys):
        cli.main(["help", "view"])
        out = capsys.readouterr().out
        assert "usage:" in out.lower()
        assert "view" in out
```

### Breakpoint Layout

```python
# tests/cli/test_breakpoints.py

import pytest
from noesis.cli.theme import detect_breakpoint, Breakpoint


@pytest.mark.parametrize("width,expected", [
    (40, Breakpoint.COMPACT),
    (59, Breakpoint.COMPACT),
    (60, Breakpoint.STANDARD),
    (80, Breakpoint.STANDARD),
    (99, Breakpoint.STANDARD),
    (100, Breakpoint.WIDE),
    (120, Breakpoint.WIDE),
    (200, Breakpoint.WIDE),
])
def test_breakpoint_detection(width, expected):
    assert detect_breakpoint(width) == expected
```

### Renderer Selection Matrix

```python
# tests/cli/test_renderer_selection.py

import pytest
from noesis.cli.main import _select_renderer
from noesis.cli.context import GlobalOptions
from noesis.cli.render.plain import PlainRenderer


class DummyCtx:
    isatty = True


class DummyCtxNoTTY:
    isatty = False


def test_no_color_forces_plain(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    r = _select_renderer(DummyCtx(), GlobalOptions())
    assert isinstance(r, PlainRenderer)


def test_json_forces_plain():
    r = _select_renderer(DummyCtx(), GlobalOptions(json=True))
    assert isinstance(r, PlainRenderer)


def test_quiet_forces_plain():
    r = _select_renderer(DummyCtx(), GlobalOptions(quiet=True))
    assert isinstance(r, PlainRenderer)


def test_non_tty_defaults_to_plain():
    r = _select_renderer(DummyCtxNoTTY(), GlobalOptions())
    assert isinstance(r, PlainRenderer)


def test_force_rich_overrides_non_tty(monkeypatch):
    pytest.importorskip("rich")
    from noesis.cli.main import _HAS_RICH
    if not _HAS_RICH:
        pytest.skip("rich not installed")

    from noesis.cli.render.richy import RichRenderer
    monkeypatch.delenv("NO_COLOR", raising=False)
    r = _select_renderer(DummyCtxNoTTY(), GlobalOptions(force_rich=True))
    assert isinstance(r, RichRenderer)
```

---

## 9. Task List (PR Checklist)

### Commit 1: Unified Registry
```
feat(cli): unify command registry with CommandSpec

- Add CommandSpec = Command + CommandMeta
- Create REGISTRY as single source of truth
- Add query helpers: get_specs_by_group, get_home_specs
- Maintain COMMANDS backward compat export

Files: noesis/cli/registry.py
Tests: test_registry_groups_are_valid, test_home_commands_have_examples, test_command_name_matches_key
```

### Commit 2: Theme Extensions
```
feat(cli): extend theme tokens and enforce box style

- Add layout constants (max_width, gutter, indent)
- Move Breakpoint + detect_breakpoint to theme.py
- Add get_box_style() returning box.ROUNDED

Files: noesis/cli/theme.py
Tests: test_breakpoint_detection
```

### Commit 3: Content Builders
```
feat(cli): add content module derived from registry

- Create noesis/cli/content/ with home.py, help.py
- HomeScreen includes RecentEpisode support
- Deprecate help_content.py

Files: noesis/cli/content/__init__.py, home.py, help.py
       noesis/cli/help_content.py (deprecation re-exports)
```

### Commit 4: Renderer Updates
```
feat(cli): update renderers for new home/help

- Use box.ROUNDED everywhere (panels + tables)
- Remove "Press Enter" blocking
- Add RecentEpisodes panel to home
- Command-specific help embeds argparse text

Files: noesis/cli/render/plain.py, richy.py
Tests: test_home_does_not_block
```

### Commit 5: Main Routing
```
feat(cli): route no-args to home with exit 0

- Home screen returns 0 (not EXIT_USAGE)
- --json with no command → exit 2, no output
- Add _fetch_recent_episodes (summary-only fast path)

Files: noesis/cli/main.py
Tests: test_home_exits_zero, test_home_json_exits_usage_error
```

### Commit 6: Help Command
```
feat(cli): add dedicated help command

- noesis help → full help screen
- noesis help <cmd> → argparse text in styled panel
- Register in unified REGISTRY

Files: noesis/cli/commands/help.py, noesis/cli/registry.py
Tests: test_help_exits_zero, test_help_lists_all_commands
```

### Commit 7: Tests
```
test(cli): add structural tests for home/help

- Registry invariants
- Home/help structure assertions
- Breakpoint detection
- Renderer selection matrix

Files: tests/cli/test_registry.py, test_home_help.py, test_breakpoints.py, test_renderer_selection.py
```

---

## 10. Definition of Done

### Functional
- [ ] `noesis` → home screen, exit 0
- [ ] `noesis help` → grouped help, exit 0
- [ ] `noesis help <cmd>` → argparse text styled, exit 0
- [ ] `noesis --json` (no cmd) → exit 2, no output
- [ ] No blocking interactions

### Structural
- [ ] Single `REGISTRY` is source of truth for commands + metadata
- [ ] Content builders derive from registry
- [ ] `box.ROUNDED` used across all Rich panels
- [ ] Recent episodes reads summary.json only (fast path)

### Quality
- [ ] All existing tests pass
- [ ] Registry invariant tests pass
- [ ] Breakpoint detection tests pass
- [ ] Renderer selection matrix tests pass
- [ ] `lint-imports` passes

### Documentation
- [ ] CHANGELOG entry for exit code change (home = 0)
