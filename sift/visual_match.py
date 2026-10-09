"""Explainable candidate ranking over saved features, with bounded result memory."""

from bisect import insort

from . import image_store
from .image_analysis import checkpoint

MAX_DISTANCE = 8
MAX_COLOUR_DELTA = 32
MAX_ASPECT_DELTA = 0.10
MAX_RESULTS = 100


def find_matches(conn, file_id, root_id=None, cancel=lambda: False):
    """Compare one selected image against a streaming saved-library snapshot.

    Queries do not access media files. Rescan and prepare to refresh missing or
    changed sources. Distances are heuristic evidence, not confidence scores.
    """
    checkpoint(cancel)
    # Both the selected item and candidates must be read in the same snapshot.
    conn.execute("BEGIN")
    try:
        reference = next(iter(image_store.visual_rows(conn, root_id, file_id)), None)
        if reference is None:
            raise ValueError(
                "Selected image needs preparation or has too little visual detail to compare"
            )
        reference_hash = int(reference["dhash"], 16)
        reference_aspect = reference["width"] / reference["height"]
        matches = []
        examined = 0
        matched = 0
        previous_path = None
        for candidate in image_store.visual_rows(conn, root_id):
            checkpoint(cancel)
            if candidate["path"] == previous_path:
                continue
            previous_path = candidate["path"]
            if candidate["path"] == reference["path"] or candidate["sha256"] == reference["sha256"]:
                continue
            examined += 1
            distance = (reference_hash ^ int(candidate["dhash"], 16)).bit_count()
            if distance > MAX_DISTANCE:
                continue
            colour = max(
                abs(reference[channel] - candidate[channel]) for channel in ("red", "green", "blue")
            )
            aspect = candidate["width"] / candidate["height"]
            if colour > MAX_COLOUR_DELTA or abs(aspect / reference_aspect - 1) > MAX_ASPECT_DELTA:
                continue
            matched += 1
            row = dict(candidate)
            row.update(distance=distance, colour_delta=colour)
            insort(
                matches, row, key=lambda item: (item["distance"], item["colour_delta"], item["id"])
            )
            if len(matches) > MAX_RESULTS:
                matches.pop()
        # Retrieve thumbnails only for the bounded result set, not all candidates.
        for row in matches:
            checkpoint(cancel)
            row["thumbnail"] = conn.execute(
                "SELECT thumbnail FROM image_features WHERE file_id = ?", (row["id"],)
            ).fetchone()[0]
        return {
            "reference": dict(reference),
            "matches": matches,
            "examined": examined,
            "matched": matched,
            "truncated": matched > MAX_RESULTS,
        }
    finally:
        conn.rollback()
