import socket, time

def _read_head(s) -> bytes:
    r = b""
    while b'\r\n\r\n' not in r:
        chunk = s.recv(4096)
        if not chunk:
            break
        r += chunk
    return r

def send_request(server, raw: bytes):
    host, port = server
    with socket.create_connection((host, port), timeout=2) as s:
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
    host, port = server
    with socket.create_connection((host, port), timeout=2) as s:
        s.sendall(b"GET / HTTP")
        time.sleep(0.1)
        s.sendall(b"/1.1\r\n\r\n")
        r = _read_head(s)
        assert status_line(r) == b"HTTP/1.1 200 OK"