import socket
import json
import hmac
import hashlib

SERVER_IP = "127.0.0.1"
SERVER_PORT = 9999
WRONG_SECRET = b"wrong_secret"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(5.0)

request = {
    "type": "sync_request",
    "client_id": "malicious_client",
    "sequence": 1,
    "t1": 123456789.0
}

payload = json.dumps(request, sort_keys=True).encode()
request["hmac"] = hmac.new(WRONG_SECRET, payload, hashlib.sha256).hexdigest()

print(f"Sending request with WRONG secret to {SERVER_IP}:{SERVER_PORT}...")
sock.sendto(json.dumps(request).encode(), (SERVER_IP, SERVER_PORT))

try:
    data, addr = sock.recvfrom(4096)
    print("Received response (unexpected!):", data.decode())
except socket.timeout:
    print("Timeout (Expected behavior: server ignored request due to HMAC mismatch).")

sock.close()
