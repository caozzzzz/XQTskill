import hashlib
import json
from datetime import datetime
from pathlib import Path


MANIFEST_FILE = "index_manifest.json"


def records_fingerprint(records):
    normalized = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def write_manifest(index_dir, records, indexes, build_config=None):
    index_dir = Path(index_dir)
    portable_indexes = {
        key: _portable_path(index_dir, value)
        for key, value in indexes.items()
    }
    manifest = {
        "version": 2,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "records_fingerprint": records_fingerprint(records),
        "rule_count": len(records.get("rules", [])),
        "workflow_count": len(records.get("workflows", [])),
        "scene_overview_count": len(records.get("scene_overviews", [])),
        "indexes": portable_indexes,
        "build_config": build_config or {},
    }
    path = index_dir / MANIFEST_FILE
    with path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
    return manifest


def read_manifest(index_dir):
    path = Path(index_dir) / MANIFEST_FILE
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def check_freshness(records, index_dir, build_config=None):
    manifest = read_manifest(index_dir)
    current = records_fingerprint(records)
    if not manifest:
        return {
            "fresh": False,
            "reason": "missing_manifest",
            "current_records_fingerprint": current,
        }

    recorded = manifest.get("records_fingerprint", "")
    if recorded != current:
        return {
            "fresh": False,
            "reason": "records_changed",
            "manifest_records_fingerprint": recorded,
            "current_records_fingerprint": current,
            "manifest": manifest,
        }

    if build_config is not None and manifest.get("build_config", {}) != build_config:
        return {
            "fresh": False,
            "reason": "build_config_changed",
            "manifest_records_fingerprint": recorded,
            "current_records_fingerprint": current,
            "manifest": manifest,
        }

    missing = _missing_index_files(index_dir, manifest.get("indexes", {}))
    if missing:
        return {
            "fresh": False,
            "reason": "missing_index_files",
            "missing_files": missing,
            "manifest_records_fingerprint": recorded,
            "current_records_fingerprint": current,
            "manifest": manifest,
        }

    return {
        "fresh": True,
        "reason": "ok",
        "manifest_records_fingerprint": recorded,
        "current_records_fingerprint": current,
        "manifest": manifest,
    }


def resolve_index_path(index_dir, value):
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str(Path(index_dir) / path)


def _portable_path(index_dir, value):
    if not isinstance(value, str) or not value:
        return value
    path = Path(value)
    try:
        return str(path.relative_to(index_dir))
    except ValueError:
        return str(path)


def _missing_index_files(index_dir, indexes):
    required = ["embedding", "bm25"]
    if indexes.get("faiss") or indexes.get("faiss_metadata"):
        required.extend(["faiss", "faiss_metadata"])
    missing = []
    for key in required:
        value = indexes.get(key)
        if not value or not Path(resolve_index_path(index_dir, value)).is_file():
            missing.append(key)
    return missing
