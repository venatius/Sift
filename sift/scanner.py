import os
import stat
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass
class ScanItem:
    path: str
    size: int | None
    modified: float | None
    status: str  # "ok", "skipped", or "failed"
    error: str | None = None
    modified_ns: int | None = None


def _reason(e: OSError) -> str:
    return e.strerror or str(e)


def _is_link(path: str) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    attrs = getattr(info, "st_file_attributes", 0)
    return stat.S_ISLNK(info.st_mode) or bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def scan_folder(root: str) -> Iterator[ScanItem]:
    if _is_link(root):
        yield ScanItem(root, None, None, "skipped", "Selected folder is a link; not followed")
        return
    stack = [root]
    while stack:
        folder = stack.pop()
        try:
            entries = os.scandir(folder)
        except OSError as e:
            yield ScanItem(folder, None, None, "failed", f"Cannot open folder: {_reason(e)}")
            continue

        with entries:
            while True:
                try:
                    entry = next(entries)
                except StopIteration:
                    break
                except OSError as e:
                    yield ScanItem(folder, None, None, "failed", f"Error reading folder: {_reason(e)}")
                    break

                try:
                    info = entry.stat(follow_symlinks=False)
                    is_dir = entry.is_dir(follow_symlinks=False)
                    attrs = getattr(info, "st_file_attributes", 0)
                    is_reparse = bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)

                    if entry.is_symlink() or (is_dir and is_reparse):
                        yield ScanItem(entry.path, None, None, "skipped", "Link not followed")
                    elif is_dir:
                        stack.append(entry.path)
                    else:
                        yield ScanItem(entry.path, info.st_size, info.st_mtime, "ok",
                                       modified_ns=info.st_mtime_ns)
                except OSError as e:
                    yield ScanItem(entry.path, None, None, "failed", f"Cannot read: {_reason(e)}")


if __name__ == "__main__":
    import sys

    for item in scan_folder(sys.argv[1]):
        print(item.status, item.path, item.size, item.error or "")
