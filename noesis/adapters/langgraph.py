"""
LangGraph Adapter
-----------------
This module provides a thin integration layer between LangGraph workflows
and Noēsis' Intuition Layer.

It enables developers to:
    • Inject intuition hints into LangGraph nodes at runtime.
    • Trace reasoning phases without modifying the core LangGraph graph.
    • Export execution events compatible with Noēsis schemas.

Noēsis remains agnostic to LangGraph versions or node definitions — this
adapter simply normalizes events and state transitions.

Example (future):
    from noesis.adapters.langgraph import inject_intuition

    graph = inject_intuition(existing_graph, intuition_layer)
"""