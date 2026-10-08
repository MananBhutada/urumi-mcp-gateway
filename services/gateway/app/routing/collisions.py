SEP = "__"

def namespace(server: str, tool: str) -> str:
    return f"{server}{SEP}{tool}"

def split(name: str) -> tuple[str, str]:
    if SEP not in name:
        raise ValueError(f"tool name must be '<server>{SEP}<tool>': {name}")
    s, t = name.split(SEP, 1)
    return s, t
