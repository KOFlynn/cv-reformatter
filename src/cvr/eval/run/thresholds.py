"""The soft gates, read from ``eval/thresholds.yaml``: the placement minimum,
the appendix maximum, and whether punctuation fidelity is hard. The hard
gates are not configurable and are not in the file."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from cvr.golden.generate import GENERATED_DIR

__all__ = ["EVAL_DIR", "THRESHOLDS_FILE", "Thresholds", "load_thresholds"]

# The repository root's eval/: config and generated reports, never code.
EVAL_DIR = GENERATED_DIR.parents[1] / "eval"
THRESHOLDS_FILE = EVAL_DIR / "thresholds.yaml"


@dataclass(frozen=True)
class Thresholds:
    """Percentages, 0 to 100.

    ``placement_min`` holds tunable-leaf precision and recall each, never
    their F1; ``appendix_max`` holds the token-weighted appendix rate. Both
    apply to the run's totals. ``punctuation_hard`` makes any punctuation
    finding fail the run.
    """

    placement_min: float = 0.0
    appendix_max: float = 100.0
    punctuation_hard: bool = False


def load_thresholds(path: Path = THRESHOLDS_FILE) -> Thresholds:
    """Read the file, insisting on exactly the three settings so a typo is
    an error rather than a gate silently left at its default."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    expected = {
        "placement_accuracy": {"min"},
        "appendix_rate": {"max"},
        "punctuation_fidelity": {"hard"},
    }
    shape = {key: set(value) for key, value in (data or {}).items()}
    if shape != expected:
        raise ValueError(f"{path}: expected exactly {expected}, found {shape}")
    punctuation_hard = data["punctuation_fidelity"]["hard"]
    if not isinstance(punctuation_hard, bool):
        raise TypeError(f"{path}: punctuation_fidelity.hard must be true or false")
    return Thresholds(
        placement_min=float(data["placement_accuracy"]["min"]),
        appendix_max=float(data["appendix_rate"]["max"]),
        punctuation_hard=punctuation_hard,
    )
