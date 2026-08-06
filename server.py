import socket, json

HOST = "127.0.0.1"
PORT = 8000

status_text = {
    200: "OK",
    400: "Bad Request",
    404: "Not Found",
    405: "Method Not Allowed",
    500: "Internal Server Error",
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
        
    return method, path, query, headers, version

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
        
        method, path, query, headers, version = parse_head(head)
        
        print(f"\n=== {method} {path} ===")
        print(f"query:  {query or '(none)'}")
        print(f"host:   {headers.get('host')}")
        print(f"agent:  {headers.get('user-agent')}")
        print(f"headers parsed: {len(headers)}")
        
        body = json.dumps(
            {'method': method, 'path': path, 'query': query}
        ).encode('utf-8') + b"\n"
        
        send_response(conn, 200, 'application/json', body)
        conn.close()
        
        
    

if __name__ == "__main__":
    main()