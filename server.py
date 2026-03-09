import socket
import json
import time
import hmac
import hashlib
import threading
from typing import Dict, Tuple

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 9999
BUFFER_SIZE = 4096
SHARED_SECRET = b"super_secret_key_change_this"

# Optional artificial server clock drift/offset simulation
SERVER_TIME_OFFSET = 0.0  # seconds

# Track clients for demonstration
clients: Dict[Tuple[str, int], float] = {}
clients_lock = threading.Lock()


def current_server_time() -> float:
    return time.time() + SERVER_TIME_OFFSET


def sign_message(message: dict) -> str:
    temp = dict(message)
    temp.pop("hmac", None)
    payload = json.dumps(temp, sort_keys=True).encode()
    return hmac.new(SHARED_SECRET, payload, hashlib.sha256).hexdigest()


def verify_message(message: dict) -> bool:
    received_hmac = message.get("hmac", "")
    expected_hmac = sign_message(message)
    return hmac.compare_digest(received_hmac, expected_hmac)


def make_response(request: dict, client_addr: Tuple[str, int]) -> dict:
    # t2 = server receive time
    t2 = current_server_time()

    response = {
        "type": "sync_response",
        "client_id": request["client_id"],
        "sequence": request["sequence"],
        "t1": request["t1"],   # client send time
        "t2": t2,              # server receive time
        "t3": current_server_time(),  # server send time
        "server_note": "authenticated_response"
    }
    response["hmac"] = sign_message(response)
    return response


def server_loop():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((SERVER_HOST, SERVER_PORT))

    print(f"[SERVER] UDP Clock Sync Server listening on {SERVER_HOST}:{SERVER_PORT}")

    while True:
        try:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            raw_receive_time = current_server_time()

            try:
                request = json.loads(data.decode())
            except json.JSONDecodeError:
                print(f"[SERVER] Invalid JSON from {addr}")
                continue

            if not verify_message(request):
                print(f"[SERVER] HMAC verification failed for {addr}")
                continue

            if request.get("type") != "sync_request":
                print(f"[SERVER] Unknown message type from {addr}: {request.get('type')}")
                continue

            with clients_lock:
                clients[addr] = raw_receive_time

            response = make_response(request, addr)
            sock.sendto(json.dumps(response).encode(), addr)

            print(
                f"[SERVER] Replied to client={request['client_id']} "
                f"seq={request['sequence']} addr={addr}"
            )

        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down.")
            break
        except Exception as e:
            print(f"[SERVER] Error: {e}")

    sock.close()


if __name__ == "__main__":
    server_loop()