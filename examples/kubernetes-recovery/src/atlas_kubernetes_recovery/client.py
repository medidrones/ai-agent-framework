"""Small standard-library client used by the isolated certification runner."""

from __future__ import annotations

import argparse
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main() -> None:
    """Invoke one technical endpoint and preserve its JSON response."""
    parser = argparse.ArgumentParser()
    parser.add_argument("method", choices=("GET", "POST"))
    parser.add_argument("path")
    parser.add_argument(
        "--base-url",
        default="http://atlas-worker.atlas-ds013.svc.cluster.local:8080",
    )
    arguments = parser.parse_args()
    if not arguments.path.startswith("/") or "\n" in arguments.path:
        parser.error("O caminho deve ser absoluto e não pode conter quebras de linha.")
    request = Request(  # noqa: S310 - fixed cluster-local URL and validated path
        f"{arguments.base_url}{arguments.path}",
        method=arguments.method,
        data=b"" if arguments.method == "POST" else None,
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310
            sys.stdout.buffer.write(response.read())
    except HTTPError as error:
        sys.stdout.buffer.write(error.read())
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
