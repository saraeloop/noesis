# Noesis TUI

A terminal user interface for the Noesis cognitive framework, built with [Bubbletea](https://github.com/charmbracelet/bubbletea), [Bubbles](https://github.com/charmbracelet/bubbles), and [Lipgloss](https://github.com/charmbracelet/lipgloss).

## Features

- **Episode Browser**: List and filter recent episodes with status badges
- **Dashboard View**: Execution map, verification results, KPIs, and timeline
- **Events Viewer**: Scrollable event stream with phase filtering
- **Proof / changes**: Inspection screens for run evidence
- **Run Launcher**: Start new episodes directly from the TUI

## Prerequisites

- Go 1.22 or later
- Noesis Python CLI installed and on your `PATH` (`noesis` command available)

## Installation

```bash
cd noesis-tui
go install .

# Or build locally
make build
```

The TUI auto-detects `.noesis/episodes` (or `NOESIS_RUNS_DIR`) by walking parent directories. Episode bundles are flat `ep_<ULID>/` directories.

## Usage

```bash
# From this directory after `make build`
./noesis-tui

# Or if installed
noesis-tui
```

The Python CLI also exposes an in-process browser: `noesis browse`.

### Keyboard shortcuts

Help text on the home screen: `1/2: tabs  enter: view  b: browse  p: proof  e: events  n: run  r: refresh  /: filter  q: quit`.

#### Home screen (episode list)

- `enter` — View episode details
- `e` — View episode events
- `b` — Open browse
- `p` — Open proof
- `d` — Open changes
- `n` — Launch new episode
- `r` — Refresh list
- `f` — Cycle status filter
- `/` — Filter episodes
- `tab` / `1` / `2` — Switch runs vs agents tabs
- `q` — Quit

#### Detail screen (dashboard)

- `e` — View events
- `p` — Open proof
- `↑/↓` — Scroll (viewport)
- `esc` — Go back

#### Events screen

- `←/→` or `h/l` — Switch phase filter
- `tab` — Cycle filters
- `↑/↓` — Scroll
- `esc` — Go back

#### Run screen

- `enter` — Start run (input mode) / View details (after completion)
- `n` — Start new run (after completion)
- `esc` — Go back

## Architecture

The TUI shells out to the Python CLI (`noesis-tui/internal/cli/client.go`):

- `noesis ps --json` → Episode list
- `noesis view <id> --json` → Episode dashboard
- `noesis events <id> --envelope` → Event stream
- `noesis run "task" --json` → Run episode

### Directory structure

```
noesis-tui/
├── main.go
├── Makefile
└── internal/
    ├── cli/          # Shell-out client and JSON envelopes
    ├── model/        # Bubbletea screens (home, detail, events, run, browse, proof, changes)
    ├── ui/           # Dashboard + proof rendering
    ├── style/        # Lipgloss theme (aligned with Python CLI)
    └── msg/          # Navigation and data messages
```

## Development

```bash
cd noesis-tui
go mod tidy
make build
make dev
make clean
```

## Related

- [Noesis](https://github.com/saraeloop/noesis) — Python runtime
- CLI contracts: `noesis ps`, `noesis view`, `noesis events --envelope`, `noesis run --json` (see `docs/reference/cli.mdx`)
