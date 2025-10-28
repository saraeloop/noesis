"""
City comparison example for Noēsis.

Demonstrates intuition-guided reasoning vs. baseline execution.

- Baseline: intuition=False  → no advisory events
- Intuition-guided: intuition=CityIntuition()  → pre-run hint events
"""

from __future__ import annotations
import csv
from pathlib import Path
import noesis as ns
from .city import CityIntuition


# Data Loading

def load_city_data():
    """Load example city data from examples/data/cities.csv"""
    data_path = Path(__file__).parent / "data" / "cities.csv"
    with data_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        for r in rows:
            r["population"] = int(r["population"])
            r["gdp_per_capita"] = int(r["gdp_per_capita"])
        return rows


def city_facts(name, data):
    """Retrieve row matching a given city name."""
    return next((r for r in data if r["city"].lower() == name.lower()), None)


def format_task(a, b, data):
    """Create a natural-language comparison task between two cities."""
    ca, cb = city_facts(a, data), city_facts(b, data)
    return (
        f"Compare {a} and {b} based on population, GDP per capita, and culture.\n\n"
        f"{a}: population {ca['population']}, GDP ${ca['gdp_per_capita']}, "
        f"known for {ca['notable_trait']}.\n"
        f"{b}: population {cb['population']}, GDP ${cb['gdp_per_capita']}, "
        f"known for {cb['notable_trait']}."
    )


# Experiment

if __name__ == "__main__":
    ns.set(intuition_mode="advisory")

    data = load_city_data()
    task = format_task("Tokyo", "Kyoto", data)

    # Baseline (no intuition)
    ep_base = ns.solve(task, using="react", intuition=False)
    s_base = ns.summary(ep_base)

    # Intuition-guided (with CityIntuition)
    ep_intu = ns.solve(task, using="react", intuition=CityIntuition())
    s_intu = ns.summary(ep_intu)

    print("Baseline:", ep_base)
print("Intuition-guided:", ep_intu)
print(f"Δ Steps: {s_base['metrics']['steps']} → {s_intu['metrics']['steps']}")
print(f"Δ Intuition Events: {s_intu['metrics']['intuition_events']}")
print("Flags:", s_intu["flags"])   
print("Using:", ns.summary(ep_intu)["flags"]["using"], "| Mode:", ns.summary(ep_intu)["flags"]["mode"])
print("\nTip: Inspect advisory events with:")
print("   uv run python - <<'PY'\n"
      "   import noesis as ns, json; ep = ns.last()\n"
      "   ints = [e for e in ns.events(ep) if e['phase']=='intuition']\n"
      "   print(json.dumps(ints[-1]['payload'], indent=2) if ints else '—')\n"
      "   PY")