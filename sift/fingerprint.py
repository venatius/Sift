import hashlib

CHUNK = 1024 * 1024  # read 1 MiB at a time


def sha256_file(path, should_stop=None):
    """Return the file's SHA-256 as hex text, or None if asked to stop."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            if should_stop and should_stop():
                return None
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()