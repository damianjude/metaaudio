from pathlib import Path


def _is_within_directory(path: Path, base_dir: Path) -> bool:
    """Return True if path is within base_dir after resolving.

    Uses Path.resolve to avoid traversal outside the target directory.
    """
    try:
        path.resolve().relative_to(base_dir.resolve())
        return True
    except (ValueError, OSError):
        return False
