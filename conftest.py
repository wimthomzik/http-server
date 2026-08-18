import socket, subprocess, sys, time, os
import pytest

HOST, PORT = "127.0.0.1", 8000

@pytest.fixture(scope="session")
def server():
    proc = subprocess.Popen([sys.executable, "server.py"])
    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                with socket.create_connection((HOST, PORT), timeout=0.1):
                    break
            except:
                if time.monotonic() > deadline:
                    raise RuntimeError("Server did not start in time")
                if proc.poll() is not None:
                    raise RuntimeError(f"Server died, exit code {proc.returncode}")
                time.sleep(0.05)
        yield HOST, PORT
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        