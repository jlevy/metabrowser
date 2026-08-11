"""Small source fixture for manual syntax-highlighting checks."""

from __future__ import annotations


def summarize(values: list[int]) -> dict[str, int]:
    """Return a compact summary of sample integer values."""
    return {"count": len(values), "total": sum(values)}


if __name__ == "__main__":
    print(summarize([1, 2, 3]))
