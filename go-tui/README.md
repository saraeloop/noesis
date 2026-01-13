# Noesis TUI

A beautiful terminal user interface for the Noesis cognitive framework, built with [Bubbletea](https://github.com/charmbracelet/bubbletea), [Bubbles](https://github.com/charmbracelet/bubbles), and [Lipgloss](https://github.com/charmbracelet/lipgloss).

## Features

- **Episode Browser**: List and filter recent episodes with status badges
- **Dashboard View**: Execution map, verification results, KPIs, and timeline
- **Events Viewer**: Scrollable event stream with phase filtering
- **Run Launcher**: Start new episodes directly from the TUI

## Prerequisites

- Go 1.22 or later
- Noesis Python CLI installed and in your PATH (`noesis` command available)

## Installation

```bash
# From the go-tui directory
go install .

# Or build locally
make build
```

## Usage

```bash
# Run the TUI
./noesis-tui

# Or if installed
noesis-tui
```

### Keyboard Shortcuts

#### Home Screen (Episode List)
- `enter` - View episode details
- `e` - View episode events
- `n` - Launch new episode
- `r` - Refresh list
- `/` - Filter episodes
- `q` - Quit

#### Detail Screen (Dashboard)
- `e` - View events
- `↑/↓` - Scroll
- `esc` - Go back

#### Events Screen
- `←/→` or `h/l` - Switch phase filter
- `tab` - Cycle filters
- `↑/↓` - Scroll
- `esc` - Go back

#### Run Screen
- `enter` - Start run (input mode) / View details (after completion)
- `n` - Start new run (after completion)
- `esc` - Go back

## Architecture

The TUI consumes CLI contracts defined in ADR-011 and ADR-012:

- `noesis ps --json` → Episode list (PsResult envelope)
- `noesis view <id> --json` → Episode dashboard (ViewResult envelope)
- `noesis events <id> --envelope` → Event stream (EventsResult envelope)
- `noesis run "task" --json` → Run episode (RunResult envelope)

### Directory Structure

```
go-tui/
├── main.go                    # Entry point
├── internal/
│   ├── cli/                   # CLI client and types
│   │   ├── client.go          # Shell-out to Python CLI
│   │   ├── envelope.go        # CLI version block
│   │   ├── ps.go              # PsResult types
│   │   ├── view.go            # ViewResult + Dashboard types
│   │   ├── events.go          # EventsResult types
│   │   └── run.go             # RunResult types
│   ├── model/                 # Bubbletea models
│   │   ├── app.go             # Root model (screen router)
│   │   ├── home.go            # Episode list screen
│   │   ├── detail.go          # Dashboard detail screen
│   │   ├── events.go          # Events viewer screen
│   │   └── run.go             # Run launcher screen
│   ├── style/                 # Lipgloss styling
│   │   ├── theme.go           # Colors (matches Python CLI)
│   │   ├── symbols.go         # Status/phase symbols
│   │   └── layout.go          # Breakpoints, dimensions
│   └── msg/                   # Bubbletea messages
│       ├── navigation.go      # Screen transitions
│       └── data.go            # Data fetch results
└── Makefile
```

## Development

```bash
# Install dependencies
go mod tidy

# Build
make build

# Run in development
make dev

# Clean
make clean
```

## Related

- [Noesis](https://github.com/noesis-ai/noesis) - The Python cognitive framework
- [ADR-011](../internals/adr/ADR-011-cli-run-contract.md) - CLI Run Boundary Contract
- [ADR-012](../internals/adr/ADR-012-cli-observe-contract.md) - CLI Observe Boundary Contract
