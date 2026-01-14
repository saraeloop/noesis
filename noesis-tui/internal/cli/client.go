package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// Client wraps shell-out calls to the Python Noesis CLI.
type Client struct {
	// Timeout for CLI commands
	Timeout time.Duration
	// NoesisBin is the path to the noesis binary (default: "noesis")
	NoesisBin string
	// RunsDir is the path to the runs directory (auto-detected or from env)
	RunsDir string
}

// NewClient creates a new CLI client with default settings.
// It auto-detects the runs directory by looking in parent directories.
func NewClient() *Client {
	runsDir := os.Getenv("NOESIS_RUNS_DIR")
	if runsDir == "" {
		runsDir = detectRunsDir()
	}

	return &Client{
		Timeout:   30 * time.Second,
		NoesisBin: "noesis",
		RunsDir:   runsDir,
	}
}

// detectRunsDir looks for a runs/ directory containing episodes in parent directories.
func detectRunsDir() string {
	cwd, err := os.Getwd()
	if err != nil {
		return ""
	}

	dir := cwd
	for {
		runsPath := filepath.Join(dir, "runs")
		if isNoesisRunsDir(runsPath) {
			return runsPath
		}

		parent := filepath.Dir(dir)
		if parent == dir {
			break // reached root
		}
		dir = parent
	}

	return ""
}

// isNoesisRunsDir checks if a directory looks like a noesis runs directory.
func isNoesisRunsDir(path string) bool {
	info, err := os.Stat(path)
	if err != nil || !info.IsDir() {
		return false
	}

	// Check if it contains episode directories (ep_* pattern)
	entries, err := os.ReadDir(path)
	if err != nil {
		return false
	}

	for _, entry := range entries {
		if entry.IsDir() && strings.HasPrefix(entry.Name(), "ep_") {
			// Check if it has a summary.json
			summaryPath := filepath.Join(path, entry.Name(), "summary.json")
			if _, err := os.Stat(summaryPath); err == nil {
				return true
			}
		}
	}

	return false
}

// ListEpisodes calls `noesis ps --json` and returns the result.
func (c *Client) ListEpisodes(ctx context.Context, limit int) (*PsResult, error) {
	args := []string{"ps", "--json"}
	if limit > 0 {
		args = append(args, "--limit", fmt.Sprint(limit))
	}
	return runJSONGeneric[PsResult](ctx, c.NoesisBin, args, c.Timeout, c.RunsDir)
}

// ViewEpisode calls `noesis view <id> --json` and returns the result.
func (c *Client) ViewEpisode(ctx context.Context, episodeID string) (*ViewResult, error) {
	args := []string{"view", episodeID, "--json"}
	return runJSONGeneric[ViewResult](ctx, c.NoesisBin, args, c.Timeout, c.RunsDir)
}

// GetEvents calls `noesis events <id> --envelope` and returns the result.
func (c *Client) GetEvents(ctx context.Context, episodeID string, phase *string) (*EventsResult, error) {
	args := []string{"events", episodeID, "--envelope"}
	if phase != nil && *phase != "" {
		args = append(args, "--phase", *phase)
	}
	return runJSONGeneric[EventsResult](ctx, c.NoesisBin, args, c.Timeout, c.RunsDir)
}

// RunEpisode calls `noesis run "task" --json` and returns the result.
func (c *Client) RunEpisode(ctx context.Context, task string, opts ...RunOption) (*RunResult, error) {
	args := []string{"run", task, "--json"}
	for _, opt := range opts {
		args = opt.Apply(args)
	}
	return runJSONGeneric[RunResult](ctx, c.NoesisBin, args, c.Timeout, c.RunsDir)
}

// RunOption modifies the arguments passed to `noesis run`.
type RunOption interface {
	Apply(args []string) []string
}

// WithWorkspace sets the workspace directory for the run.
type WithWorkspace string

func (w WithWorkspace) Apply(args []string) []string {
	return append(args, "--workspace", string(w))
}

// WithVerify sets the verify flag for the run.
type WithVerify string

func (v WithVerify) Apply(args []string) []string {
	return append(args, "--verify", string(v))
}

// CLIError represents an error from the CLI with exit code information.
type CLIError struct {
	ExitCode int
	Stderr   string
	Err      error
}

func (e *CLIError) Error() string {
	if e.Stderr != "" {
		return fmt.Sprintf("noesis exit %d: %s", e.ExitCode, e.Stderr)
	}
	return fmt.Sprintf("noesis exit %d: %v", e.ExitCode, e.Err)
}

func (e *CLIError) Unwrap() error {
	return e.Err
}

// runJSONGeneric executes a CLI command and parses JSON output into type T.
func runJSONGeneric[T any](ctx context.Context, bin string, args []string, timeout time.Duration, runsDir string) (*T, error) {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, bin, args...)

	// Set NOESIS_RUNS_DIR if we have a runs directory
	if runsDir != "" {
		cmd.Env = append(os.Environ(), "NOESIS_RUNS_DIR="+runsDir)
	}

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		exitCode := 1
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		}
		return nil, &CLIError{
			ExitCode: exitCode,
			Stderr:   stderr.String(),
			Err:      err,
		}
	}

	var result T
	if err := json.Unmarshal(stdout.Bytes(), &result); err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w (output: %s)", err, stdout.String())
	}

	return &result, nil
}
