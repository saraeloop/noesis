"""Interactive episode browser TUI."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    Rule,
    Static,
)
from rich.text import Text

from ..theme import PHASE_SYMBOLS, outcome_badge, normalize_outcome


# ─────────────────────────────────────────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────────────────────────────────────────

BROWSE_CSS = """
Screen {
    background: $surface;
}

#main-container {
    height: 100%;
}

#episode-list {
    width: 45%;
    height: 100%;
    border: solid $primary;
    padding: 0 1;
}

#episode-list DataTable {
    height: 100%;
}

#details-panel {
    width: 55%;
    height: 100%;
    border: solid $secondary;
    padding: 1 2;
}

.section-title {
    text-style: bold;
    color: $text;
    margin-bottom: 1;
}

.status-success {
    color: $success;
}

.status-vetoed {
    color: $error;
}

.status-audit {
    color: $warning;
}

.outcome-ok {
    color: $success;
}

.outcome-warn {
    color: $warning;
}

.outcome-err {
    color: $error;
}

.outcome-muted {
    color: $text-muted;
}

.muted {
    color: $text-muted;
}

.detail-row {
    margin-bottom: 0;
}

.detail-key {
    color: $text-muted;
    width: 12;
}

.detail-value {
    color: $text;
}

#timeline-container {
    margin-top: 1;
    height: auto;
    max-height: 50%;
    overflow-y: auto;
}

.timeline-row {
    height: 1;
}

.phase-label {
    width: 12;
}

.empty-state {
    color: $text-muted;
    text-align: center;
    margin-top: 5;
}

Footer {
    background: $surface-darken-1;
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class EpisodeRow:
    """Episode row for display."""
    episode_id: str
    started_at: str
    status: str
    outcome: str | None
    task: str
    duration: str

    @property
    def short_id(self) -> str:
        return self.episode_id[:12] if len(self.episode_id) > 12 else self.episode_id

    @property
    def status_symbol(self) -> str:
        return ""

    @property
    def status_label(self) -> str:
        badge = outcome_badge(self.outcome)
        return badge.label

    @property
    def status_style(self) -> str:
        badge = outcome_badge(self.outcome)
        return badge.style

    @property
    def time_str(self) -> str:
        try:
            dt = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
            return dt.strftime("%H:%M")
        except (ValueError, AttributeError):
            return self.started_at[:5] if self.started_at else "--:--"


@dataclass
class TimelineEvent:
    """Timeline event for display."""
    phase: str
    status: str | None
    summary: str | None
    delta_ms: int

    @property
    def phase_symbol(self) -> str:
        return PHASE_SYMBOLS.get(self.phase.lower(), "○")


# ─────────────────────────────────────────────────────────────────────────────
# WIDGETS
# ─────────────────────────────────────────────────────────────────────────────


class EpisodeDetails(Static):
    """Widget showing episode details."""

    episode: reactive[EpisodeRow | None] = reactive(None)
    events: reactive[list[TimelineEvent]] = reactive(list)
    governance: reactive[dict[str, Any] | None] = reactive(None)

    def compose(self) -> ComposeResult:
        yield Label("Episode Details", classes="section-title")
        yield Container(id="details-content")

    def watch_episode(self, episode: EpisodeRow | None) -> None:
        """React to episode changes."""
        self._refresh_details()

    def watch_events(self, events: list[TimelineEvent]) -> None:
        """React to events changes."""
        self._refresh_details()

    def _refresh_details(self) -> None:
        """Refresh the details display."""
        container = self.query_one("#details-content", Container)
        container.remove_children()

        if self.episode is None:
            container.mount(Label("Select an episode to view details", classes="empty-state"))
            return

        ep = self.episode

        # Status line with symbol
        status_class = f"outcome-{ep.status_style}"
        container.mount(Label(f"{ep.status_label}", classes=status_class))
        container.mount(Rule())

        # Episode info
        container.mount(self._detail_row("Episode", ep.episode_id))
        container.mount(self._detail_row("Started", ep.started_at))
        container.mount(self._detail_row("Duration", ep.duration))
        container.mount(self._detail_row("Task", ep.task[:60] + "..." if len(ep.task) > 60 else ep.task))

        # Governance info
        if self.governance:
            container.mount(Rule())
            container.mount(Label("Governance", classes="section-title"))
            gov = self.governance
            container.mount(self._detail_row("Decision", gov.get("decision", "—")))
            if gov.get("rule_id"):
                container.mount(self._detail_row("Rule", gov["rule_id"]))
            if gov.get("score") is not None:
                container.mount(self._detail_row("Score", f"{gov['score']:.2f}"))

        # Timeline
        if self.events:
            container.mount(Rule())
            container.mount(Label("Timeline", classes="section-title"))
            for event in self.events[:15]:  # Limit to 15 events
                sym = event.phase_symbol
                status_str = f"({event.status})" if event.status else ""
                summary = event.summary[:40] + "..." if event.summary and len(event.summary) > 40 else (event.summary or "")
                container.mount(
                    Label(f"  {sym} {event.phase:<10} {status_str:<12} {summary}", classes="timeline-row")
                )

    def _detail_row(self, key: str, value: str) -> Horizontal:
        """Create a detail row."""
        return Horizontal(
            Label(f"{key}:", classes="detail-key"),
            Label(value, classes="detail-value"),
            classes="detail-row",
        )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────


class BrowseApp(App):
    """Interactive episode browser."""

    TITLE = "Noesis Episode Browser"
    CSS = BROWSE_CSS

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("enter", "view_episode", "View"),
        Binding("e", "view_events", "Events"),
        Binding("?", "help", "Help"),
    ]

    def __init__(
        self,
        episodes: list[dict[str, Any]] | None = None,
        runs_dir: Path | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._raw_episodes = episodes or []
        self._runs_dir = runs_dir
        self._episodes: list[EpisodeRow] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            with Vertical(id="episode-list"):
                yield Label("Recent Episodes", classes="section-title")
                yield DataTable(id="episodes-table", cursor_type="row")
            with Vertical(id="details-panel"):
                yield EpisodeDetails()
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the episode list."""
        self._load_episodes()
        self._populate_table()

    def _load_episodes(self) -> None:
        """Convert raw episode data to EpisodeRow objects."""
        self._episodes = []
        for row in self._raw_episodes:
            if not isinstance(row, dict):
                continue
            try:
                duration_sec = row.get("duration_sec", 0)
                duration_str = f"{duration_sec:.2f}s" if duration_sec else "—"

                # Derive status from multiple fields
                status = row.get("status")
                if not status:
                    # Fallback: derive from success/veto_count
                    if row.get("veto_count", 0) > 0:
                        status = "VETOED"
                    elif row.get("success"):
                        status = "SUCCESS"
                    else:
                        status = "UNKNOWN"
                else:
                    status = status.upper()

                outcome = normalize_outcome(
                    row.get("outcome"),
                    status=status,
                    success=row.get("success"),
                )

                self._episodes.append(EpisodeRow(
                    episode_id=row.get("episode_id", "unknown"),
                    started_at=row.get("started_at", ""),
                    status=status,
                    outcome=outcome,
                    task=row.get("task", "(no task)"),
                    duration=duration_str,
                ))
            except Exception:  # noqa: BLE001
                continue

    def _populate_table(self) -> None:
        """Populate the episodes table."""
        table = self.query_one("#episodes-table", DataTable)
        table.clear(columns=True)

        table.add_columns("Time", "Status", "Episode", "Task")

        if not self._episodes:
            table.add_row("—", "—", "No episodes found", "—")
            return

        style_map = {
            "ok": "green",
            "warn": "yellow",
            "err": "red",
            "muted": "grey50",
        }
        for ep in self._episodes:
            color = style_map.get(ep.status_style, "white")
            status_display = Text(f"{ep.status_label}", style=color)
            task_display = ep.task[:30] + "..." if len(ep.task) > 30 else ep.task
            table.add_row(ep.time_str, status_display, ep.short_id, task_display)

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        if event.row_key is None or not self._episodes:
            return

        try:
            row_index = event.cursor_row
            if 0 <= row_index < len(self._episodes):
                episode = self._episodes[row_index]
                self._show_episode_details(episode)
        except (IndexError, AttributeError):
            pass

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight (cursor movement)."""
        if event.row_key is None or not self._episodes:
            return

        try:
            row_index = event.cursor_row
            if 0 <= row_index < len(self._episodes):
                episode = self._episodes[row_index]
                self._show_episode_details(episode)
        except (IndexError, AttributeError):
            pass

    def _show_episode_details(self, episode: EpisodeRow) -> None:
        """Show details for the selected episode."""
        details = self.query_one(EpisodeDetails)
        details.episode = episode

        # Load events and governance from disk if available
        events, governance = self._load_episode_artifacts(episode.episode_id)
        details.events = events
        details.governance = governance

    def _load_episode_artifacts(
        self, episode_id: str
    ) -> tuple[list[TimelineEvent], dict[str, Any] | None]:
        """Load events and governance from episode artifacts."""
        events: list[TimelineEvent] = []
        governance: dict[str, Any] | None = None

        if not self._runs_dir:
            return events, governance

        ep_dir = self._runs_dir / episode_id
        if not ep_dir.exists():
            return events, governance

        # Load events
        events_file = ep_dir / "events.jsonl"
        if events_file.exists():
            import json
            try:
                with open(events_file) as f:
                    for line in f:
                        if not line.strip():
                            continue
                        event = json.loads(line)
                        phase = event.get("phase", "")
                        payload = event.get("payload", {}) or {}

                        # Extract governance decision
                        if phase == "governance" and payload.get("decision"):
                            governance = {
                                "decision": payload.get("decision", "").upper(),
                                "rule_id": payload.get("rule_id"),
                                "score": payload.get("score"),
                                "enforced": payload.get("enforced", False),
                            }

                        events.append(TimelineEvent(
                            phase=phase,
                            status=payload.get("status"),
                            summary=payload.get("reason") or payload.get("message"),
                            delta_ms=0,
                        ))
            except Exception:  # noqa: BLE001
                pass

        return events, governance

    def action_refresh(self) -> None:
        """Refresh the episode list."""
        self._populate_table()
        self.notify("Refreshed episode list")

    def action_view_episode(self) -> None:
        """View the selected episode in detail."""
        table = self.query_one("#episodes-table", DataTable)
        row_index = table.cursor_row
        if 0 <= row_index < len(self._episodes):
            episode = self._episodes[row_index]
            self.notify(f"View: noesis view {episode.episode_id}")

    def action_view_events(self) -> None:
        """View events for the selected episode."""
        table = self.query_one("#episodes-table", DataTable)
        row_index = table.cursor_row
        if 0 <= row_index < len(self._episodes):
            episode = self._episodes[row_index]
            self.notify(f"Events: noesis events {episode.episode_id}")

    def action_help(self) -> None:
        """Show help."""
        self.notify("↑↓ Navigate | Enter View | e Events | r Refresh | q Quit")


def run_browse(episodes: list[dict[str, Any]], runs_dir: Path | None = None) -> None:
    """Run the browse TUI."""
    app = BrowseApp(episodes=episodes, runs_dir=runs_dir)
    app.run()
