import socket

SERVER_IP = "127.0.0.1"
SERVER_PORT = 9999

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
print("Sending malformed (non-JSON) data to server...")
sock.sendto(b"I am not JSON!", (SERVER_IP, SERVER_PORT))
sock.close()
