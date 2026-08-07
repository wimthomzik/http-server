import socket, json

HOST = "127.0.0.1"
PORT = 8000

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
        chunk = conn.recv(4096)
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

def send_response(conn, status, contet_type, body):
    """Write one HTTP response. `body` is bytes."""
    head = (
        f"HTTP/1.1 {status} {status_text[status]}\r\n"
        f"Content-Type: {contet_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode('ascii')
    conn.sendall(head + body)
    
    
def dispatch(request): # -> status, content_type, body
    if request["path"] not in ROUTES:
        return 404, "application/json", _json_body({"error_message": "Ressource Not Found"})
    
    if request["method"] not in ROUTES[request["path"]]:
        return 405, "application/json", _json_body({"error_message": "Method Not Allowed"})
    
    return ROUTES[request["path"]][request["method"]]()

def main():
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)     
    s.bind((HOST, PORT))   
    s.listen()
    
    print(f"Listening on http://{HOST}:{PORT}") 
    
    while True:
        
        conn, addr = s.accept()
        print(f"Connection from {addr[0]}:{addr[1]}")

        head, rest = read_head(conn)    
        if head is None:
            conn.close()
            continue
        
        request = parse_head(head)
        
        print(f"\n=== {request['method']} {request['path']} ===")
        print(f"query:  {request['query'] or '(none)'}")
        print(f"host:   {request['headers'].get('host')}")
        print(f"agent:  {request['headers'].get('user-agent')}")
        print(f"headers parsed: {len(request['headers'])}")
        
        status, content_type, body = dispatch(request)
        
        send_response(conn, status, content_type, body)
        conn.close()
        
        
    

if __name__ == "__main__":
    main()