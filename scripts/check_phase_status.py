"""Check that phase status tables agree between guidance and roadmap."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
PHASE_ROW_PATTERN = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", re.MULTILINE)
STATUS_FILES = (ROOT / "AGENTS.md", ROOT / "docs" / "development" / "ROADMAP.md")


def read_statuses(path: Path) -> dict[int, str]:
    matches = PHASE_ROW_PATTERN.findall(path.read_text(encoding="utf-8"))
    statuses: dict[int, str] = {}
    for phase_text, status in matches:
        phase = int(phase_text)
        if phase in statuses:
            raise ValueError(f"Duplicate Phase {phase} row in {path.relative_to(ROOT)}")
        statuses[phase] = status.strip()
    if not statuses:
        raise ValueError(f"No phase status rows found in {path.relative_to(ROOT)}")
    return statuses


def main() -> int:
    try:
        statuses = [(path, read_statuses(path)) for path in STATUS_FILES]
    except (OSError, ValueError) as exc:
        print(f"Phase status check failed: {exc}", file=sys.stderr)
        return 1

    agents_path, agents_statuses = statuses[0]
    roadmap_path, roadmap_statuses = statuses[1]
    agents_phases = set(agents_statuses)
    roadmap_phases = set(roadmap_statuses)
    if agents_phases != roadmap_phases:
        detail = (
            f"{agents_path.relative_to(ROOT)} phases={sorted(agents_phases)}, "
            f"{roadmap_path.relative_to(ROOT)} phases={sorted(roadmap_phases)}"
        )
        print(f"Phase status check failed: phase sets differ: {detail}", file=sys.stderr)
        return 1

    differences = [
        (phase, agents_statuses[phase], roadmap_statuses[phase])
        for phase in sorted(agents_phases)
        if agents_statuses[phase] != roadmap_statuses[phase]
    ]
    if differences:
        detail = "; ".join(
            f"Phase {phase}: AGENTS.md={agents!r}, ROADMAP.md={roadmap!r}"
            for phase, agents, roadmap in differences
        )
        print(f"Phase status check failed: {detail}", file=sys.stderr)
        return 1

    summary = "; ".join(
        f"{phase}: {agents_statuses[phase]}" for phase in sorted(agents_phases)
    )
    print(f"Phase statuses synchronized: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
