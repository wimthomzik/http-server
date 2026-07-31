import socket

def main():
    
    Host, Port = "127.0.0.1", 8000
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  
    s.bind((Host, Port))
    
    s.listen()
    print(f"Listening on http://{Host}:{Port}") 
    
    while True:
        conn, addr = s.accept()
        print(f"Connection from {addr[0]}:{addr[1]}")
        request = conn.recv(4096)
        header, _, rest = request.decode("latin-1").partition("\r\n\r\n")
        
        print("\n")
        print(f"Received {len(request)} bytes")
        print("-------------- HEADER --------------")
        for line in header.split("\r\n"):
            print(line)
        print("-------------- BODY --------------")
        print(rest)
        print("\n")
        
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