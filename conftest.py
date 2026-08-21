import os, socket, subprocess, sys, tempfile, time
from contextlib import ExitStack, contextmanager
from pathlib import Path

import pytest

from server import ServerConfig

SERVER_PY = Path(__file__).parent / "server.py"
STARTUP_TIMEOUT = 5
SHUTDOWN_TIMEOUT = 5


def free_port(host="127.0.0.1"):
    """Ask the kernel for an unused port, release it, and hand back the number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def _wait_until_listening(proc, config, log):
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while True:
        if proc.poll() is not None:
            raise RuntimeError(
                f"Server died, exit code {proc.returncode}\n--- server output ---\n{log.read_text()}"
            )
        try:
            with socket.create_connection((config.host, config.port), timeout=0.1):
                return
        except OSError:
            if time.monotonic() > deadline:
                raise RuntimeError(
                    f"Server did not start in time on {config.host}:{config.port}\n"
                    f"--- server output ---\n{log.read_text()}"
                ) from None
            time.sleep(0.05)


def _stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=SHUTDOWN_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@contextmanager
def running_server(config):
    """Run one server process on `config`, yielding once it accepts connections."""
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "server.log"
        # The child writes through `sink`; we read through `log` so our seeks
        # never move the offset it is appending at.
        with log.open("w") as sink:
            proc = subprocess.Popen(
                [sys.executable, "-u", str(SERVER_PY)],
                env={**os.environ, **config.to_env()},
                cwd=SERVER_PY.parent,
                stdout=sink,
                stderr=subprocess.STDOUT,
            )
            try:
                _wait_until_listening(proc, config, log)
                yield config
            finally:
                _stop(proc)


@pytest.fixture(scope="session")
def server():
    """One server for the whole run, on a port nothing else is using."""
    with running_server(ServerConfig(port=free_port())) as config:
        yield config


@pytest.fixture
def server_factory():
    """Start as many independently configured servers as a test needs."""
    with ExitStack() as stack:

        def start(**overrides):
            overrides.setdefault("port", free_port())
            return stack.enter_context(running_server(ServerConfig(**overrides)))

        yield start
