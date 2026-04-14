"""Conservative parallelism helpers for local model stages."""

import os


def resolve_parallelism(parallelism="auto", hard_limit=3, stable_limit=2):
    if isinstance(parallelism, str) and parallelism.strip().lower() == "auto":
        return auto_parallelism(hard_limit=hard_limit, stable_limit=stable_limit)

    value = int(parallelism)
    return max(1, min(value, hard_limit))


def auto_parallelism(hard_limit=3, stable_limit=2):
    cpu_count = os.cpu_count() or 1
    ceiling = max(1, min(hard_limit, stable_limit))
    if cpu_count <= 2:
        return 1

    try:
        one_minute_load = os.getloadavg()[0]
    except (AttributeError, OSError):
        return 1

    load_ratio = one_minute_load / cpu_count
    if load_ratio >= 0.65:
        return 1
    if load_ratio >= 0.35:
        return min(2, ceiling)
    return min(max(1, cpu_count // 4), ceiling)
