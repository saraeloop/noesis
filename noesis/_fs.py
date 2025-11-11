from __future__ import annotations

from pathlib import Path
import os


def fsync_dir(path: Path) -> None:
    """
    Attempt to fsync the containing directory to ensure rename durability.

    On filesystems that do not support directory handles (e.g., some network mounts
    or Windows without admin privileges) this silently no-ops.
    """
    try:
        dir_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


__all__ = ["fsync_dir"]
