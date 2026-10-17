def human_size(bytes_val: int) -> str:
    if not bytes_val:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} TB"

def human_eta(seconds: int) -> str:
    if not seconds or seconds < 0:
        return "-"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"

def parse_size(text: str) -> int:
    text = text.strip().upper()
    if text.endswith("/S"): text = text[:-2]
    if text.endswith("B"): text = text[:-1]
    units = {"K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}
    factor = units.get(text[-1:])
    value = float(text[:-1] if factor else text) * (factor or units["M"])  # bare numbers are MB
    if value < 1:
        raise ValueError(text)
    return int(value)
