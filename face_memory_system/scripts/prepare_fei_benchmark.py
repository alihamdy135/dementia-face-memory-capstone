#!/usr/bin/env python3
"""Create a fixed, private FEI open-set benchmark manifest from local images."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import random
import re


EXPECTED_IDENTITIES = set(range(1, 201))
POSES_PER_IDENTITY = set(range(1, 15))
PHASH_MAX_HAMMING = 2
DATASET = "FEI Face Database (original colour images)"
SOURCE_URL = "https://fei.edu.br/~cet/facedatabase.html"


def _read_images(
    image_dir: Path,
) -> tuple[dict[int, list[Path]], dict[str, str], dict[str, int]]:
    pattern = re.compile(r"^(\d{1,3})-(\d{2})\.jpg$", re.IGNORECASE)
    identities: dict[int, list[Path]] = defaultdict(list)
    exact_hashes: dict[str, str] = {}
    filenames_by_hash: dict[str, list[str]] = defaultdict(list)
    for path in sorted(image_dir.glob("*.jpg")):
        match = pattern.fullmatch(path.name)
        if not match:
            raise ValueError(f"Unexpected image filename: {path.name}")
        person_id, pose = int(match.group(1)), int(match.group(2))
        if person_id not in EXPECTED_IDENTITIES or pose not in POSES_PER_IDENTITY:
            raise ValueError(f"Identity/pose out of range in {path.name}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        exact_hashes[path.name] = digest
        filenames_by_hash[digest].append(path.name)
        identities[person_id].append(path)

    if set(identities) != EXPECTED_IDENTITIES:
        raise ValueError("Expected all 200 FEI identities (1 through 200)")
    for person_id, paths in identities.items():
        poses = [int(path.stem.rsplit("-", 1)[1]) for path in paths]
        if len(paths) != 14 or set(poses) != POSES_PER_IDENTITY:
            raise ValueError(f"Identity {person_id} must have exactly one image for poses 01–14")
        paths.sort(key=lambda path: int(path.stem.rsplit("-", 1)[1]))
    cross_identity_duplicates = []
    exact_duplicate_groups = []
    for filenames in filenames_by_hash.values():
        if len(filenames) > 1:
            pids = {int(Path(name).stem.split("-", 1)[0]) for name in filenames}
            exact_duplicate_groups.append(filenames)
            if len(pids) > 1:
                cross_identity_duplicates.append(filenames)
    if cross_identity_duplicates:
        raise ValueError("Exact duplicate pixels have conflicting identity labels; inspect the private source files")
    duplicate_summary = {
        "exact_duplicate_group_count": len(exact_duplicate_groups),
        "exact_duplicate_extra_image_count": sum(len(group) - 1 for group in exact_duplicate_groups),
    }
    return identities, exact_hashes, duplicate_summary


def _components(paths: list[Path], cv2: object, exact_hashes: dict[str, str]) -> tuple[list[list[Path]], int]:
    hashes: list[int] = []
    for path in paths:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"OpenCV could not decode {path.name}")
        value = cv2.img_hash.pHash(image).reshape(-1).tobytes()
        hashes.append(int.from_bytes(value, "big"))

    parent = list(range(len(paths)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    close_pairs = 0
    for left in range(len(paths)):
        for right in range(left + 1, len(paths)):
            exact = exact_hashes[paths[left].name] == exact_hashes[paths[right].name]
            distance = (hashes[left] ^ hashes[right]).bit_count()
            if exact or distance <= PHASH_MAX_HAMMING:
                union(left, right)
                if not exact:
                    close_pairs += 1

    grouped: dict[int, list[Path]] = defaultdict(list)
    for index, path in enumerate(paths):
        grouped[find(index)].append(path)
    return list(grouped.values()), close_pairs


def _allocate_known_images(
    components: list[list[Path]], seed: int
) -> dict[str, str]:
    """Keep each exact/near-duplicate component in one split, with exact 4/5/5 quotas."""
    rng = random.Random(seed)
    groups = [list(group) for group in components]
    rng.shuffle(groups)
    groups.sort(key=len, reverse=True)
    bins: list[list[Path]] = [[], [], []]
    remaining = [4, 5, 5]

    def assign(index: int) -> bool:
        if index == len(groups):
            return remaining == [0, 0, 0]
        group = groups[index]
        options = [0, 1, 2]
        rng.shuffle(options)
        seen_capacity: set[int] = set()
        for target in options:
            capacity = remaining[target]
            if capacity < len(group) or capacity in seen_capacity:
                continue
            seen_capacity.add(capacity)
            remaining[target] -= len(group)
            bins[target].extend(group)
            if assign(index + 1):
                return True
            del bins[target][-len(group):]
            remaining[target] += len(group)
        return False

    if not assign(0):
        raise ValueError("Near-duplicate groups cannot fit the required 4/5/5 known-image quotas")
    labels = ("gallery", "validation", "test")
    return {path.name: labels[index] for index, paths in enumerate(bins) for path in paths}


def prepare(image_dir: Path, output_dir: Path, seed: int) -> dict[str, object]:
    import cv2

    if not hasattr(cv2, "img_hash") or not hasattr(cv2.img_hash, "pHash"):
        raise RuntimeError("OpenCV contrib img_hash.pHash is required for near-duplicate screening")
    identities, exact_hashes, duplicate_summary = _read_images(image_dir)
    rng = random.Random(seed)
    identity_order = sorted(identities)
    rng.shuffle(identity_order)
    known_ids = identity_order[:100]
    validation_unknown_ids = identity_order[100:150]
    test_unknown_ids = identity_order[150:200]
    if set(known_ids) & set(validation_unknown_ids + test_unknown_ids):
        raise AssertionError("Known and unknown identity partitions overlap")
    if set(validation_unknown_ids) & set(test_unknown_ids):
        raise AssertionError("Validation and test unknown identities overlap")

    assignments: dict[str, str] = {}
    near_duplicate_pairs = 0
    duplicate_components = 0
    component_counts: Counter[int] = Counter()
    cross_split_components = 0
    for person_id in known_ids:
        groups, close_pairs = _components(identities[person_id], cv2, exact_hashes)
        near_duplicate_pairs += close_pairs
        duplicate_components += sum(len(group) > 1 for group in groups)
        component_counts.update(len(group) for group in groups)
        person_assignments = _allocate_known_images(groups, seed + person_id * 1009)
        cross_split_components += sum(
            len({person_assignments[path.name] for path in group}) != 1 for group in groups
        )
        assignments.update(person_assignments)
    if cross_split_components:
        raise AssertionError("A detected near-duplicate component crosses split boundaries")

    for person_id in validation_unknown_ids:
        assignments.update({path.name: "validation" for path in identities[person_id]})
    for person_id in test_unknown_ids:
        assignments.update({path.name: "test" for path in identities[person_id]})

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.csv"
    split_order = {"gallery": 0, "validation": 1, "test": 2}
    rows = []
    for person_id, paths in identities.items():
        for path in paths:
            rows.append((
                f"images/{path.name}",
                f"FEI-{person_id:03d}",
                assignments[path.name],
                "",  # The source does not document capture-session IDs.
            ))
    rows.sort(key=lambda row: (
        split_order[row[2]], int(row[1].split("-")[1]), int(Path(row[0]).stem.rsplit("-", 1)[1])
    ))
    with manifest_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["image_path", "person_id", "split", "session_id"])
        writer.writerows(rows)

    counts = Counter(row[2] for row in rows)
    per_identity_split: dict[str, Counter[str]] = defaultdict(Counter)
    for _, person_id, split, _ in rows:
        per_identity_split[person_id][split] += 1
    for person_id in known_ids:
        counts_for_person = per_identity_split[f"FEI-{person_id:03d}"]
        if (counts_for_person["gallery"], counts_for_person["validation"], counts_for_person["test"]) != (4, 5, 5):
            raise AssertionError(f"Wrong known-image quota for FEI-{person_id:03d}")
    if counts != {"gallery": 400, "validation": 1200, "test": 1200}:
        raise AssertionError(f"Unexpected split image counts: {counts}")

    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    audit: dict[str, object] = {
        "dataset": DATASET,
        "source_url": SOURCE_URL,
        "seed": seed,
        "manifest_sha256": manifest_sha,
        "identity_counts": {"known": 100, "validation_unknown": 50, "test_unknown": 50},
        "image_counts": dict(counts),
        "known_images_per_person": {"gallery": 4, "validation": 5, "test": 5},
        "unknown_images_per_person": 14,
        "capture_sessions": "not documented per image; session_id cells remain blank; this is an image-level benchmark",
        "duplicate_screen": {
            "exact_sha256_duplicate_groups_all_images": duplicate_summary["exact_duplicate_group_count"],
            "exact_sha256_duplicate_excess_images_all_images": duplicate_summary["exact_duplicate_extra_image_count"],
            "near_duplicate_method": f"OpenCV pHash on original image; within-person Hamming distance <= {PHASH_MAX_HAMMING}; each connected component kept in a single split",
            "near_duplicate_pairs_known_people": near_duplicate_pairs,
            "multi_image_components_known_people": duplicate_components,
            "near_duplicate_components_cross_split": cross_split_components,
            "component_size_counts_known_people": dict(sorted(component_counts.items())),
        },
        "known_person_ids_private": [f"FEI-{person_id:03d}" for person_id in sorted(known_ids)],
        "validation_unknown_ids_private": [f"FEI-{person_id:03d}" for person_id in sorted(validation_unknown_ids)],
        "test_unknown_ids_private": [f"FEI-{person_id:03d}" for person_id in sorted(test_unknown_ids)],
    }
    (output_dir / "split_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261108)
    args = parser.parse_args()
    audit = prepare(args.images_dir, args.output_dir, args.seed)
    print(json.dumps({key: value for key, value in audit.items() if not key.endswith("_ids_private")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
