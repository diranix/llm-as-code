import os


class JailError(Exception):
    pass


def resolve(root, path):
    jail = os.path.realpath(root)
    target = os.path.realpath(os.path.join(jail, path))
    if target != jail and not target.startswith(jail + os.sep):
        raise JailError("refused - outside " + root + ": " + path)
    return target


def write_text(root, path, text, append=False):
    target = resolve(root, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    mode = "a" if append else "w"
    with open(target, mode, encoding="utf-8") as f:
        f.write(text)
    return target
