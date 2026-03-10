"""
Parser module: loads and normalises supported configuration file types.
Supported: .yml / .yaml, .tf, .env
"""

import os
import yaml
from pathlib import Path
from typing import Any


def _load_yaml(filepath: str) -> dict | None:
    """Load a YAML file and return parsed content, or None on failure."""
    with open(filepath, "r", encoding="utf-8") as fh:
        try:
            return yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            print(f"  [WARN] Failed to parse YAML {filepath}: {exc}")
            return None


def _load_text(filepath: str) -> str:
    """Load a plain-text file and return its contents."""
    with open(filepath, "r", encoding="utf-8") as fh:
        return fh.read()


def detect_file_type(filepath: str) -> str | None:
    """
    Detect the configuration file type based on extension and content hints.
    Returns one of: 'docker-compose', 'kubernetes', 'terraform', 'env', or None.
    """
    path = Path(filepath)
    ext = path.suffix.lower()

    if ext in (".yml", ".yaml"):
        # Distinguish docker-compose vs Kubernetes manifests
        try:
            data = _load_yaml(filepath)
            if isinstance(data, dict):
                if "services" in data and ("version" in data or "networks" in data or "volumes" in data):
                    return "docker-compose"
                if "kind" in data and "apiVersion" in data:
                    return "kubernetes"
                # Fallback: if 'services' key present, assume compose
                if "services" in data:
                    return "docker-compose"
        except Exception:
            pass
        return None

    if ext == ".tf":
        return "terraform"

    if ext == ".env" or path.name.startswith(".env"):
        return "env"

    return None


class ParsedFile:
    """Container for a parsed configuration file."""

    def __init__(self, filepath: str, file_type: str, data: Any, raw: str):
        self.filepath = filepath
        self.file_type = file_type
        self.data = data      # parsed structure (dict/list) or None for text-only types
        self.raw = raw        # raw text content


def load_directory(scan_path: str) -> list[ParsedFile]:
    """
    Walk the given directory and load every supported configuration file.
    Returns a list of ParsedFile objects.
    """
    supported_extensions = {".yml", ".yaml", ".tf", ".env"}
    parsed_files: list[ParsedFile] = []

    scan_root = Path(scan_path)
    if not scan_root.exists():
        raise FileNotFoundError(f"Scan path does not exist: {scan_path}")

    candidates = []
    if scan_root.is_file():
        candidates = [scan_root]
    else:
        for root, dirs, files in os.walk(scan_root):
            # Skip hidden directories and common non-config dirs
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__")]
            for fname in files:
                fpath = Path(root) / fname
                if fpath.suffix.lower() in supported_extensions or fpath.name.startswith(".env"):
                    candidates.append(fpath)

    for fpath in sorted(candidates):
        filepath_str = str(fpath)
        file_type = detect_file_type(filepath_str)
        if file_type is None:
            continue

        try:
            raw = _load_text(filepath_str)
            if file_type in ("docker-compose", "kubernetes"):
                data = _load_yaml(filepath_str)
            else:
                data = None

            parsed_files.append(ParsedFile(
                filepath=filepath_str,
                file_type=file_type,
                data=data,
                raw=raw,
            ))
            print(f"  [+] Loaded [{file_type}]: {fpath.name}")
        except Exception as exc:
            print(f"  [WARN] Could not read {filepath_str}: {exc}")

    return parsed_files
