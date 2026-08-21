import re, socket, time
import pytest

from server import ServerConfig, send_response

def _read_head(s) -> bytes:
    r = b""
    while b'\r\n\r\n' not in r:
        chunk = s.recv(4096)
        if not chunk:
            break
        r += chunk
    return r

def send_request(config, raw: bytes):
    with socket.create_connection((config.host, config.port), timeout=2) as s:
        s.sendall(raw)
        return _read_head(s)
    
def status_line(response):
    return response.split(b"\r\n")[0]

def test_unknown_path(server):
    r = send_request(server, b"GET /invalid_path HTTP/1.1\r\n\r\n")
    assert status_line(r) == b"HTTP/1.1 404 Not Found"
    
def test_known_path(server):
    r = send_request(server, b"GET / HTTP/1.1\r\n\r\n") 
    assert status_line(r) == b"HTTP/1.1 200 OK"
        
def test_invalid_method(server):
    r = send_request(server, b"POST /hello HTTP/1.1\r\n\r\n") 
    assert status_line(r) == b"HTTP/1.1 405 Method Not Allowed"
    
def test_malformed_request_line(server):
    r = send_request(server, b"GARBAGE\r\nHost: x\r\n\r\n")
    assert status_line(r) == b"HTTP/1.1 400 Bad Request"
    
def test_request_sent_in_two_fragments(server):
    with socket.create_connection((server.host, server.port), timeout=2) as s:
        s.sendall(b"GET / HTTP")
        time.sleep(0.1)
        s.sendall(b"/1.1\r\n\r\n")
        r = _read_head(s)
        assert status_line(r) == b"HTTP/1.1 200 OK"

def test_config_survives_a_round_trip_through_the_environment():
    config = ServerConfig(host="127.0.0.1", port=9999)
    assert ServerConfig.from_env(config.to_env()) == config

def test_two_instances_run_side_by_side(server_factory):
    """The payoff of a configurable server: two of them, no source edits."""
    a, b = server_factory(), server_factory()
    assert a.port != b.port
    for config in (a, b):
        r = send_request(config, b"GET / HTTP/1.1\r\n\r\n")
        assert status_line(r) == b"HTTP/1.1 200 OK"

class _FakeConn:
    """Stands in for a socket: keeps whatever send_response writes."""
    def __init__(self):
        self.sent = b""

    def sendall(self, data):
        self.sent += data

BODY = b'{"ok": true}\n'

def _write(status):
    """Run one response through send_response, return the bytes it wrote."""
    conn = _FakeConn()
    send_response(conn, status, "application/json", BODY)
    return conn.sent

@pytest.mark.parametrize("status, expected", [
    (200, b"HTTP/1.1 200 OK"),                              # mapped
    (404, b"HTTP/1.1 404 Not Found"),                       # mapped
    (201, b"HTTP/1.1 201 "),                                # in range, no text: empty phrase is legal
    (100, b"HTTP/1.1 100 "),                                # lower bound, still passed through
    (599, b"HTTP/1.1 599 "),                                # upper bound, still passed through
    (99, b"HTTP/1.1 500 Internal Server Error"),            # just below the range
    (600, b"HTTP/1.1 500 Internal Server Error"),           # just above the range
    (999, b"HTTP/1.1 500 Internal Server Error"),           # nowhere near the range
    (200.0, b"HTTP/1.1 500 Internal Server Error"),         # == 200, so a range check alone lets it through
    (None, b"HTTP/1.1 500 Internal Server Error"),          # handler forgot to return a status
])
def test_status_line_for_status(status, expected):
    assert status_line(_write(status)) == expected

@pytest.mark.parametrize("status", [
    0, -1, 1000, 2.5, 200.0, True, False, None, "200", b"200", [200], {}, object(),
])
def test_any_status_still_yields_a_complete_response(status):
    head, sep, body = _write(status).partition(b"\r\n\r\n")
    assert sep, "response head was never terminated"
    assert re.fullmatch(rb"HTTP/1\.1 \d{3} .*", head.split(b"\r\n")[0])
    assert body == BODY