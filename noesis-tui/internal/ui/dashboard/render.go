package dashboard

import (
	"fmt"
	"strings"

	"noesis.dev/tui/internal/cli"
	"noesis.dev/tui/internal/style"

	"github.com/charmbracelet/lipgloss"
)

// RenderDashboard renders a full episode dashboard view.
func RenderDashboard(dashboard *cli.Dashboard) string {
	if dashboard == nil {
		return ""
	}

	sections := []string{
		renderExecutionMap(dashboard),
		"",
		renderVerification(dashboard),
		"",
		renderKPIs(dashboard),
		"",
		renderPhaseBreakdown(dashboard),
		"",
		renderTimeline(dashboard),
	}

	return lipgloss.JoinVertical(lipgloss.Left, sections...)
}

func renderExecutionMap(dashboard *cli.Dashboard) string {
	em := dashboard.ExecutionMap
	phases := []cli.ExecutionPhase{em.Observe, em.Act, em.Verify, em.Outcome}

	var parts []string
	for i, phase := range phases {
		symbol := style.StatusSymbol(phase.Status)
		var symbolStyle lipgloss.Style
		switch phase.Status {
		case "OK", "PASSED":
			symbolStyle = style.StatusSuccess
		case "ERROR", "FAILED", "VETOED":
			symbolStyle = style.StatusVetoed
		case "SKIPPED":
			symbolStyle = style.StatusSkipped
		default:
			symbolStyle = style.StatusPending
		}

		part := lipgloss.JoinVertical(lipgloss.Center,
			style.Subtitle.Render(phase.Phase),
			symbolStyle.Render(symbol),
			style.DimText.Render(phase.Status),
		)
		parts = append(parts, part)

		if i < len(phases)-1 {
			arrow := style.MutedText.Render(" → ")
			parts = append(parts, arrow)
		}
	}

	title := style.Title.Render("Execution Map")
	map_ := lipgloss.JoinHorizontal(lipgloss.Center, parts...)

	return lipgloss.JoinVertical(lipgloss.Left, title, "", map_)
}

func renderVerification(dashboard *cli.Dashboard) string {
	v := dashboard.Verification
	title := style.Title.Render("Verification")

	var lines []string

	if v.AdapterResult != nil {
		lines = append(lines, fmt.Sprintf("  Adapter: %s", *v.AdapterResult))
	}
	if v.Outcome.Status != nil {
		lines = append(lines, fmt.Sprintf("  Outcome: %s", *v.Outcome.Status))
	}
	if v.Outcome.Summary != nil {
		lines = append(lines, fmt.Sprintf("  Summary: %s", *v.Outcome.Summary))
	}
	if v.Provided != nil {
		lines = append(lines, fmt.Sprintf("  Provided: %v", *v.Provided))
	}
	if v.Passed != nil {
		symbol := style.Check
		st := style.SuccessText
		if !*v.Passed {
			symbol = style.Cross
			st = style.ErrorText
		}
		lines = append(lines, fmt.Sprintf("  Passed: %s %v", st.Render(symbol), *v.Passed))
	}
	if v.Error != nil {
		lines = append(lines, style.ErrorText.Render(fmt.Sprintf("  Error: %s", *v.Error)))
	}
	if len(v.Assertions) > 0 {
		lines = append(lines, "  Assertions:")
		for _, a := range v.Assertions {
			symbol := style.Check
			st := style.SuccessText
			if !a.Passed {
				symbol = style.Cross
				st = style.ErrorText
			}
			lines = append(lines, fmt.Sprintf("    %s %s", st.Render(symbol), a.Name))
		}
	}

	content := strings.Join(lines, "\n")
	return lipgloss.JoinVertical(lipgloss.Left, title, content)
}

func renderKPIs(dashboard *cli.Dashboard) string {
	k := dashboard.KPIs
	title := style.Title.Render("KPIs")

	var lines []string
	if k.SuccessPct != nil {
		lines = append(lines, fmt.Sprintf("  Success: %.0f%%", *k.SuccessPct))
	}
	if k.PlanAdherence != nil {
		lines = append(lines, fmt.Sprintf("  Plan Adherence: %.0f%%", *k.PlanAdherence*100))
	}
	if k.VetoCount != nil {
		lines = append(lines, fmt.Sprintf("  Veto Count: %d", *k.VetoCount))
	}
	if k.ToolCoverage != nil {
		lines = append(lines, fmt.Sprintf("  Tool Coverage: %.0f%%", *k.ToolCoverage*100))
	}
	if k.FirstAction != nil {
		lines = append(lines, fmt.Sprintf("  First Action: %s", *k.FirstAction))
	}

	if len(lines) == 0 {
		lines = append(lines, style.DimText.Render("  No KPI data"))
	}

	content := strings.Join(lines, "\n")
	return lipgloss.JoinVertical(lipgloss.Left, title, content)
}

func renderPhaseBreakdown(dashboard *cli.Dashboard) string {
	if len(dashboard.PhaseBreakdown) == 0 {
		return ""
	}

	title := style.Title.Render("Phase Timing")

	var lines []string
	for _, p := range dashboard.PhaseBreakdown {
		lines = append(lines, fmt.Sprintf("  %s: %dms", p.Phase, p.Ms))
	}

	content := strings.Join(lines, "\n")
	return lipgloss.JoinVertical(lipgloss.Left, title, content)
}

func renderTimeline(dashboard *cli.Dashboard) string {
	if len(dashboard.TimelineRows) == 0 {
		return ""
	}

	title := style.Title.Render("Timeline")

	var lines []string
	for _, row := range dashboard.TimelineRows {
		symbol := style.PhaseSymbol(row.Phase)
		phaseStyle := style.PhaseStyle(row.Phase)

		line := fmt.Sprintf("  %s %s %s %s",
			style.DimText.Render(row.DtStr),
			phaseStyle.Render(symbol+" "+row.Phase),
			style.MutedText.Render(row.Agent),
			row.Summary,
		)
		lines = append(lines, line)
	}

	content := strings.Join(lines, "\n")
	return lipgloss.JoinVertical(lipgloss.Left, title, content)
}
