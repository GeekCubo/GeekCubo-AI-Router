"""Command-line entry point: ``geekcubo-connector`` (and ``python -m``).

Two commands:

``enroll --server URL --code CODE [--name NAME]``
    Redeem a one-time dashboard code and store the machine credential.

``run [--server URL] [--adapter NAME ...]``
    Connect and serve models until interrupted (Ctrl-C).

The config file is found via ``GEEKCUBO_CONNECTOR_CONFIG`` or the platform
default; see :mod:`geekcubo_connector.config`.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from . import __version__
from .client import Connector, _TerminalClose
from .config import ConnectorConfig, config_path, load_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geekcubo-connector",
        description="Serve local AI models to a GeekCubo instance over an outbound WebSocket.",
    )
    parser.add_argument("--version", action="version", version=f"geekcubo-connector {__version__}")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="enable debug logging"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    enroll = sub.add_parser("enroll", help="redeem an enrollment code and store the credential")
    enroll.add_argument("--server", required=True, help="your GeekCubo base URL, e.g. https://example.com")
    enroll.add_argument("--code", required=True, help="one-time enrollment code from the dashboard")
    enroll.add_argument("--name", default=None, help="display name for this machine")

    run = sub.add_parser("run", help="connect and serve local models")
    run.add_argument("--server", default=None, help="GeekCubo base URL (overrides stored config)")
    run.add_argument(
        "--adapter",
        action="append",
        choices=["ollama", "lmstudio", "vllm", "llamacpp", "custom"],
        help="restrict to specific adapters (repeatable); default probes all",
    )
    run.add_argument(
        "--url",
        action="append",
        default=[],
        metavar="ADAPTER=URL",
        help="override an adapter base URL, e.g. --url ollama=http://127.0.0.1:11434",
    )
    run.add_argument("--api-key", default=None, help="bearer token for a custom OpenAI-compatible endpoint")

    status = sub.add_parser("status", help="show the stored configuration (credential redacted)")
    status.add_argument("--json", action="store_true", help="print raw JSON with the credential masked")

    sub.add_parser("logout", help="delete the stored credential")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        if args.command == "enroll":
            return _cmd_enroll(args)
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "status":
            return _cmd_status(args)
        if args.command == "logout":
            return _cmd_logout()
    except _TerminalClose as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    return 1


def _cmd_enroll(args: argparse.Namespace) -> int:
    config = load_config() or ConnectorConfig(server=args.server)
    config.server = args.server.rstrip("/")
    if args.name:
        config.display_name = args.name
    config.enrollment_code = args.code
    # Clear any stale credential so we take the enrollment branch, not a
    # reconnect with an expired secret.
    config.credential = None

    connector = Connector(config)
    print(f"Enrolling with {config.server} ...")
    asyncio.run(connector.enroll())
    target = config_path()
    print(f"Enrolled. Credential stored at {target}")
    if not config.machine_id:
        print("Note: the server did not report a machine id; run `geekcubo-connector status` to inspect.")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    config = load_config()
    if config is None and not args.server:
        print(
            "error: no configuration found; run `geekcubo-connector enroll` first "
            "or pass --server",
            file=sys.stderr,
        )
        return 2
    config = config or ConnectorConfig(server=args.server)
    if args.server:
        config.server = args.server.rstrip("/")
    if not config.credential:
        print(
            "error: no credential stored; run `geekcubo-connector enroll` first",
            file=sys.stderr,
        )
        return 2
    if args.adapter:
        config.adapters = list(args.adapter)
    for override in args.url:
        name, _, url = override.partition("=")
        if not name or not url:
            print(f"error: --url expects ADAPTER=URL, got {override!r}", file=sys.stderr)
            return 2
        config.adapter_urls[name] = url
    if args.api_key:
        config.adapter_api_key = args.api_key

    connector = Connector(config)
    print(f"Connecting to {config.server} as machine {config.machine_id or '(pending)'} ...")
    try:
        asyncio.run(_run_until_stopped(connector))
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130
    return 0


async def _run_until_stopped(connector: Connector) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, connector.stop)
        except (NotImplementedError, RuntimeError):
            # Windows and some embedded loops do not support add_signal_handler;
            # Ctrl-C still raises KeyboardInterrupt around asyncio.run.
            pass
    await connector.run()


def _cmd_status(args: argparse.Namespace) -> int:
    config = load_config()
    if config is None:
        print(f"No configuration at {config_path()}")
        return 1
    credential = config.credential or ""
    masked = f"{credential[:6]}...{credential[-4:]}" if len(credential) > 12 else "(set)" if credential else "(none)"
    if args.json:
        import json

        data = config.to_dict()
        data["credential"] = masked
        data["config_path"] = str(config_path())
        print(json.dumps(data, indent=2))
        return 0
    print(f"Config:    {config_path()}")
    print(f"Server:    {config.server}")
    print(f"Machine:   {config.machine_id or '(pending approval)'}")
    print(f"Name:      {config.display_name or '(default)'}")
    print(f"Credential:{masked}")
    print(f"Adapters:  {', '.join(config.adapters) or '(auto-detect all)'}")
    return 0


def _cmd_logout() -> int:
    from .config import clear_config

    clear_config()
    print(f"Removed {config_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
