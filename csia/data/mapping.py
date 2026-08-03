"""Post-acquisition analysis of the dataset's mapping.json.

The structure is NOT assumed. The file has never been read in this
environment (huggingface.co is proxy-blocked), so the analyzer detects the
shape it actually finds, reports which heuristic identified the log
reference and the label, and sets `structure_confidently_parsed` so a
downstream claim can never rest on a guess.

It reports what it found; it never repairs, fills, or infers missing labels.
"""

import json
import os
import re

#: candidate keys holding a log-file reference, most specific first
FILE_KEYS = ("file", "filename", "file_name", "log", "log_file", "logfile",
             "path", "ulg", "ulog", "log_name", "name")
#: candidate keys holding the annotation
LABEL_KEYS = ("label", "labels", "anomaly", "anomaly_type", "anomaly_class",
              "class", "category", "fault", "fault_type", "type", "status",
              "condition", "annotation")
#: label values meaning "no anomaly"
NORMAL_VALUES = {"normal", "nominal", "none", "no_anomaly", "healthy", "ok",
                 "clean", "0", "false"}

ULG_RE = re.compile(r"\.ulg$", re.IGNORECASE)


def _looks_like_log(value) -> bool:
    return isinstance(value, str) and bool(ULG_RE.search(value.strip()))


def _first_key(d: dict, candidates):
    lowered = {str(k).lower(): k for k in d}
    for c in candidates:
        if c in lowered:
            return lowered[c]
    return None


def _extract(key, value):
    """Return (log_reference, label, how) for one mapping entry."""
    if isinstance(value, dict):
        fk = _first_key(value, FILE_KEYS)
        lk = _first_key(value, LABEL_KEYS)
        ref = value.get(fk) if fk else None
        if ref is None and (_looks_like_log(key) or isinstance(key, str)):
            ref, fk = key, "<mapping key>"
        return ref, (value.get(lk) if lk else None), f"key={fk} label={lk}"
    if isinstance(value, list):
        return key, value, "key=<mapping key> label=<list value>"
    return key, value, "key=<mapping key> label=<scalar value>"


def _norm_label(label):
    if label is None:
        return None
    if isinstance(label, (list, tuple, set)):
        return [str(x).strip() for x in label]
    return str(label).strip()


def _is_normal(label) -> bool:
    if label is None:
        return False
    if isinstance(label, list):
        return not label or all(str(x).strip().lower() in NORMAL_VALUES
                                for x in label)
    return str(label).strip().lower() in NORMAL_VALUES


def analyze_mapping(mapping_path: str, ulg_root: str | None = None,
                    expected_annotated: int | None = 1396,
                    expected_raw: int | None = 3196) -> dict:
    """Inventory mapping.json against the acquired .ulg files."""
    with open(mapping_path) as fh:
        doc = json.load(fh)

    if isinstance(doc, dict):
        # a wrapper such as {"mappings": {...}} or {"data": [...]}
        inner = None
        for k in ("mapping", "mappings", "data", "entries", "flights",
                  "logs"):
            v = doc.get(k)
            if isinstance(v, (dict, list)) and v:
                inner, shape = v, f"dict wrapper under {k!r}"
                break
        if inner is None:
            inner, shape = doc, "top-level dict keyed by entry"
    elif isinstance(doc, list):
        inner, shape = doc, "top-level list of entries"
    else:
        return {"error": f"unsupported mapping root: {type(doc).__name__}",
                "structure_confidently_parsed": False}

    items = (list(inner.items()) if isinstance(inner, dict)
             else list(enumerate(inner)))

    refs, labels, hows = [], {}, set()
    for key, value in items:
        ref, label, how = _extract(key, value)
        hows.add(how)
        if ref is None:
            continue
        ref = str(ref).strip()
        refs.append(ref)
        labels[ref] = _norm_label(label)

    seen, duplicates = set(), []
    for r in refs:
        (duplicates.append(r) if r in seen else seen.add(r))

    annotated = {r: l for r, l in labels.items() if l not in (None, "", [])}
    normal = {r for r, l in annotated.items() if _is_normal(l)}
    categories = {}
    for r, l in annotated.items():
        for one in (l if isinstance(l, list) else [l]):
            token = str(one).strip()
            if token and token.lower() not in NORMAL_VALUES:
                categories[token] = categories.get(token, 0) + 1

    on_disk = set()
    if ulg_root and os.path.isdir(ulg_root):
        for dirpath, _, filenames in os.walk(ulg_root):
            for fn in filenames:
                if ULG_RE.search(fn):
                    on_disk.add(fn)

    def base(p):
        return os.path.basename(str(p).strip())

    mapped_bases = {base(r) for r in refs}
    missing_referenced = sorted(mapped_bases - on_disk) if on_disk else []
    unreferenced_present = sorted(on_disk - mapped_bases) if on_disk else []

    n_annotated = len(annotated)
    result = {
        "mapping_path": mapping_path,
        "detected_structure": shape,
        "extraction_heuristics": sorted(hows),
        "structure_confidently_parsed": bool(refs) and len(hows) <= 2,
        "total_mapped_entries": len(items),
        "resolved_log_references": len(refs),
        "unique_log_references": len(set(refs)),
        "annotated_entries": n_annotated,
        "normal_flights": len(normal),
        "anomaly_categories": dict(sorted(categories.items())),
        "anomaly_category_count": len(categories),
        "duplicate_mappings": sorted(set(duplicates)),
        "duplicate_mapping_count": len(set(duplicates)),
        "ulg_files_on_disk": len(on_disk),
        "missing_referenced_files": missing_referenced,
        "missing_referenced_count": len(missing_referenced),
        "present_but_unreferenced": unreferenced_present,
        "present_but_unreferenced_count": len(unreferenced_present),
        "unmapped_raw_files": len(unreferenced_present),
        "expected_annotated": expected_annotated,
        "expected_raw": expected_raw,
    }
    result["annotated_count_matches_claim"] = (
        expected_annotated is not None and n_annotated == expected_annotated)
    result["raw_count_matches_claim"] = (
        expected_raw is not None and len(on_disk) == expected_raw
        if on_disk else None)
    if not result["annotated_count_matches_claim"]:
        result["claim_discrepancy"] = (
            f"dataset card claims {expected_annotated} annotated flights; "
            f"this mapping yields {n_annotated}. Reported as measured — the "
            f"discrepancy is the finding, not something to reconcile away.")
    return result
