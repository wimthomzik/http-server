import socket

HOST = "127.0.0.1"
PORT = 8000


def read_head(conn):
    """Read from conn until the blank line. Returns (head, leftover) bytes."""
    buffer = b''
    while b"\r\n\r\n" not in buffer:
        chunk = conn.recv(4096)
        if not chunk:
            return None, b''
        buffer += chunk
                
    header, _, rest = buffer.decode("latin-1").partition("\r\n\r\n")
    return header, rest

def parse_head(head):
    """Parse head bytes into (method, path, query, headers)."""
    lines = head.split("\r\n")
    
    method, target, version = lines[0].split(" ")
    
    path, _, query = target.partition("?")
    
    headers = {}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()
        
    return method, path, query, headers
        

def main():
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  
    s.bind((HOST, PORT))
    s.listen()
    
    print(f"Listening on http://{HOST}:{PORT}") 
    
    while True:
        
        conn, addr = s.accept()
        print(f"Connection from {addr[0]}:{addr[1]}")
            
        head, tail = read_head(conn)
        if head is None:
            conn.close()
            continue
        
        method, path, query, headers = parse_head(head)
        print(f"\n=== {method} {path} ===")
        print(f"query:  {query or '(none)'}")
        print(f"host:   {headers.get('host')}")
        print(f"agent:  {headers.get('user-agent')}")
        print(f"headers parsed: {len(headers)}")
        
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Length: 3\r\n"
            b"Connection: close\r\n"
            b"\r\n"
            b"hi"
        )
        
        conn.sendall(response)
        conn.close()
    

if __name__ == "__main__":
    main()