import threading


class Metrics:
    """Small in-process counters. Enough to show a /metrics endpoint without extra services."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {}

    def inc(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counts[name] = self._counts.get(name, 0) + amount

    def render(self) -> str:
        with self._lock:
            items = sorted(self._counts.items())
        lines: list[str] = []
        for name, value in items:
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        return ("\n".join(lines) + "\n") if lines else ""


metrics = Metrics()
