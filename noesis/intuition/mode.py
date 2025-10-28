from enum import Enum

class IntuitionMode(str, Enum):
    ADVISORY = "advisory"        # hints only; must be side-effect free
    INTERVENTIVE = "interventive"  # may change inputs/controls; must log patches
    HYBRID = "hybrid"            # hints + selective interventions