// Noesis TUI - A beautiful terminal interface for the Noesis cognitive framework.
//
// This TUI consumes the CLI contracts defined in ADR-011 and ADR-012 by shelling
// out to the Python `noesis` CLI and parsing its JSON output.
package main

import (
	"fmt"
	"os"

	"noesis.dev/tui/internal/model"

	tea "github.com/charmbracelet/bubbletea"
)

func main() {
	app := model.NewApp()

	p := tea.NewProgram(
		app,
		tea.WithAltScreen(),
		tea.WithMouseCellMotion(),
	)

	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}
