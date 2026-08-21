import socket, json, traceback, os
from dataclasses import dataclass

READ_BUFF_SIZE = 4096

@dataclass(frozen=True)
class ServerConfig:

    host: str = "127.0.0.1"
    port: int = 8000
    
    def __post_init__(self):
        if not isinstance(self.host, str) or not self.host:
            raise ValueError(f"host must be a non-empty string, got {self.host}")
        if type(self.port) is not int:
                    raise ValueError(f"port must be an int, got {self.port}")
        if not 0 <= self.port <= 65535:
            raise ValueError(f"port must be between 0 and 65535, got {self.port}")

    @classmethod
    def from_env(cls, env=os.environ):
        overrides = {}
        if 'HTTP_SERVER_HOST' in env:
            overrides['host'] = env['HTTP_SERVER_HOST']
        if 'HTTP_SERVER_PORT' in env:
            raw = env['HTTP_SERVER_PORT']
            try:
                overrides['port'] = int(raw)
            except ValueError:
                raise ValueError(f"HTTP_SERVER_PORT must be an integer, got {raw}") from None
        return cls(**overrides)

    def to_env(self):
        """Inverse of from_env: the environment a fresh process needs to rebuild this config."""
        return {
            'HTTP_SERVER_HOST': self.host,
            'HTTP_SERVER_PORT': str(self.port),
        }

def _json_body(content):
    return json.dumps(content).encode('utf-8') + b"\n"

status_text = {
    200: "OK",
    400: "Bad Request",
    404: "Not Found",
    405: "Method Not Allowed",
    500: "Internal Server Error",
}

def index():
    return 200, "application/json", _json_body({"path": "/", "method": "GET"})

def hello():
    return 200, "application/json", _json_body({"path": "/hello", "method": "GET"})

ROUTES = {
    "/": {"GET":index},
    "/hello": {"GET": hello},
}

def read_head(conn):
    """Read from conn until the blank line. Returns (head, leftover) bytes."""
    buf = b''
    while b'\r\n\r\n' not in buf:
        chunk = conn.recv(READ_BUFF_SIZE)
        if not chunk:
            return None, b''
        buf += chunk
    header, _, rest = buf.partition(b'\r\n\r\n')
    return header, rest

def parse_head(head):
    """Parse head bytes into (method, path, query, headers)."""
    lines = head.decode('ascii').split('\r\n')
    
    method, target, version = lines[0].split(' ')
    path, _, query = target.partition('?')
    
    headers = {}
    for line in lines[1:]:
        name, _, value = line.partition(':')
        headers[name.lower().strip()] = value.strip()
        
    return {'method': method, 'path':path, 'query': query,'headers': headers, 'version': version}

def _get_status(status):
    text = ""
    if not isinstance(status, int) or status not in range(100, 600):
        status = 500
    
    if status in status_text:
        text = status_text[status]
        
    return status, text

def send_response(conn, status, content_type, body):
    """Write one HTTP response. `body` is bytes."""
    status, text = _get_status(status)
    head = (
        f"HTTP/1.1 {status} {text}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode('ascii')
    conn.sendall(head + body)
    
    
def dispatch(request):
    if request["path"] not in ROUTES:
        return 404, "application/json", _json_body({"error_message": "Ressource Not Found"})
    
    if request["method"] not in ROUTES[request["path"]]:
        return 405, "application/json", _json_body({"error_message": "Method Not Allowed"})
    
    return ROUTES[request["path"]][request["method"]]()

def handle(conn):
    head, rest = read_head(conn) 
    if head is None:
        print("Client Disconnected")
        return
    
    try:
        request = parse_head(head)
    except ValueError:
        send_response(conn, 400, "application/json", _json_body({"error_message": "Bad Request"}))
        return
    
    try:
        status, content_type, body = dispatch(request)
        send_response(conn, status, content_type, body)
    except Exception:
        traceback.print_exc()
        send_response(conn, 500, "application/json", _json_body({"error_message": "Internal Server Error"}))
        return

def serve(config):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)     
        s.bind((config.host, config.port))   
        s.listen()
        
        while True:
            conn, _ = s.accept()
            
            try:
                handle(conn)
            except (ConnectionResetError, ConnectionError):
                print("Client closed the connection unexpectedly")
            except Exception:
                traceback.print_exc()
            finally:
                conn.close()
        
def main():
    config = ServerConfig.from_env()
    try:
        serve(config)
    except KeyboardInterrupt:
            print("Shutting down server...")

if __name__ == "__main__":
    main()