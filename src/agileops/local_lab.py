"""Start the interactive lab in an isolated local workspace."""

import argparse
import os
import secrets
import shutil
import webbrowser
from importlib import import_module
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from urllib.parse import quote

import uvicorn


def _operator_token(path: Path) -> str:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as token_file:
            token = secrets.token_urlsafe(32)
            token_file.write(token + "\n")
            return token
    except FileExistsError:
        token = path.read_text(encoding="utf-8").strip()
        if not token:
            raise ValueError(f"The operator token file is empty. See {path}.")
        return token


def _open_when_ready(server: uvicorn.Server, url: str, token: str) -> None:
    deadline = monotonic() + 20
    while not server.started and monotonic() < deadline:
        sleep(0.1)
    if server.started:
        webbrowser.open(f"{url}#operator={quote(token, safe='')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("tmp/local-lab"))
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not shutil.which("git"):
        parser.error("Install Git to enable the controlled reporting repair.")
    try:
        import_module("langgraph.checkpoint.sqlite")
    except ImportError:
        parser.error(
            'Install the lab dependencies with python -m pip install -e ".[lab]".'
        )

    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    token_path = workspace / "operator-token.txt"
    token = _operator_token(token_path)
    os.environ["AGILEOPS_DB_PATH"] = str(workspace / "agileops.db")
    os.environ["AGILEOPS_LAB_DB"] = str(workspace / "reporting.db")
    os.environ["AGILEOPS_WORKFLOW_DIR"] = str(workspace / "workflows")
    os.environ.setdefault("AGILEOPS_KNOWLEDGE_DB", str(workspace / "knowledge.db"))
    os.environ["AGILEOPS_APPROVAL_TOKEN"] = token
    url = f"http://127.0.0.1:{args.port}/"
    print(f"AgileOps Lab is available at {url}", flush=True)
    print(f"Operator token file: {token_path}", flush=True)
    server = uvicorn.Server(
        uvicorn.Config("agileops.main:app", host="127.0.0.1", port=args.port)
    )
    if args.open_browser:
        Thread(target=_open_when_ready, args=(server, url, token), daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
