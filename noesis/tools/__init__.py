"""
Tool adapters live here (search, calculator, summarize, etc.).

Each tool should expose a simple, typed function and be tagged by capability
(e.g., "search", "math", "text", "code"). Tools represent the bridge between
reasoning and real-world action in Noēsis.

The Intuition Layer interacts with this namespace to:
    • Predict which tool might fail or give low-quality output.
    • Forecast risk ("I sense the calculator’s input is malformed").
    • Provide soft guidance ("Perhaps summarize before searching").

This design allows agents to reason not only *with* tools but also *about* them —
enabling Noēsis to model uncertainty, foresight, and adaptive decision-making.
"""