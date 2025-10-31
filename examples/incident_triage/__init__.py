"""
Incident triage demo featuring a Gradio control room powered by Noēsis.

The package contains:
    • prod_guard – safety-first intuition policy for production incidents
    • app_incident_triage – lightweight callable graph simulating an incident workflow
    • gradio_app / streamlit_app – interactive dashboards rendering Noēsis artifacts
"""

from .app_incident_triage import incident_graph  # noqa: F401
from .prod_guard import ProdGuardPolicy  # noqa: F401

__all__ = ["incident_graph", "ProdGuardPolicy"]
