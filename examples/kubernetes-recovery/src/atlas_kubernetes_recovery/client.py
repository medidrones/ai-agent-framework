"""Small standard-library client used by the isolated certification runner."""

from __future__ import annotations

import argparse
import sys
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def _validate_base_url(value: str) -> None:
    parsed = urlsplit(value)
    hostname = parsed.hostname or ""
    trusted_host = hostname in {"127.0.0.1", "localhost"} or hostname.endswith(
        ".svc.cluster.local"
    )
    if (
        parsed.scheme != "http"
        or not trusted_host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("A URL base deve apontar para o serviço local do cluster.")


def main() -> None:
    """Invoke one technical endpoint and preserve its JSON response."""
    parser = argparse.ArgumentParser()
    parser.add_argument("method", choices=("GET", "POST"))
    parser.add_argument("path")
    parser.add_argument(
        "--base-url",
        default="http://atlas-worker.atlas-ds013.svc.cluster.local:8080",
    )
    parser.add_argument(
        "--json-stdin",
        action="store_true",
        help="Lê um corpo JSON do stdin sem expor credenciais na linha de comando.",
    )
    arguments = parser.parse_args()
    _validate_base_url(arguments.base_url)
    if not arguments.path.startswith("/") or "\n" in arguments.path:
        parser.error("O caminho deve ser absoluto e não pode conter quebras de linha.")
    if arguments.json_stdin and arguments.method != "POST":
        parser.error("--json-stdin exige o método POST.")
    body = sys.stdin.buffer.read(16_385) if arguments.json_stdin else b""
    if len(body) > 16_384:
        parser.error("O corpo JSON excede 16 KiB.")
    request = Request(  # noqa: S310 - fixed cluster-local URL and validated path
        f"{arguments.base_url}{arguments.path}",
        method=arguments.method,
        data=body if arguments.method == "POST" else None,
        headers={"Content-Type": "application/json"} if body else {},
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310  # nosec B310
            sys.stdout.buffer.write(response.read())
    except HTTPError as error:
        sys.stdout.buffer.write(error.read())
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
