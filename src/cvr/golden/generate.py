"""Write every Candidate through every registered Layout to ``fixtures/generated/``.

    uv run python -m cvr.golden.generate [--out DIR]

Each pair shares a stem: ``<candidate-id>__<layout-name>.docx`` and
``<candidate-id>__<layout-name>.manifest.json``. Output is byte-stable, so
rerunning over an unchanged Candidate and Layout rewrites identical files.
"""

import argparse
from pathlib import Path

from cvr.golden.candidate import Candidate
from cvr.golden.layouts import LAYOUTS
from cvr.golden.loader import CANDIDATES_DIR, load_candidates

__all__ = ["GENERATED_DIR", "generate_all", "main"]

GENERATED_DIR = CANDIDATES_DIR.parent / "generated"


def generate_all(
    candidates: list[Candidate] | None = None, out_dir: Path = GENERATED_DIR
) -> list[Path]:
    """Render every Candidate through every registered Layout; return the paths
    written."""
    if candidates is None:
        candidates = load_candidates()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for candidate in candidates:
        for layout in LAYOUTS:
            generated = layout.generate(candidate)
            base = out_dir / layout.stem(candidate)
            document = base.with_suffix(".docx")
            manifest = base.with_suffix(".manifest.json")
            document.write_bytes(generated.document)
            manifest.write_text(
                generated.manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
            written += [document, manifest]
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=GENERATED_DIR)
    args = parser.parse_args(argv)
    written = generate_all(out_dir=args.out)
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
