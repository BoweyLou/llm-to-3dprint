import re


def parse_scope(value: str):
    if not value:
        return []
    parts = re.split(r"[,\n]", value)
    return [part.strip().strip("/") for part in parts if part.strip().strip("/")]


def normalize_scope_path(path: str):
    value = path.strip().replace("\\", "/").strip("/")
    if value.startswith("./"):
        value = value[2:]
    return value


def paths_overlap(left: str, right: str):
    a = normalize_scope_path(left)
    b = normalize_scope_path(right)
    if not a or not b:
        return False
    return a == b or a.startswith(f"{b.rstrip('/')}/") or b.startswith(f"{a.rstrip('/')}/")
