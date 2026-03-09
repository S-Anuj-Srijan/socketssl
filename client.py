import socket
import json
import time
import hmac
import hashlib
import argparse
import statistics
from typing import List, Optional

SERVER_IP = "127.0.0.1"
SERVER_PORT = 9999
BUFFER_SIZE = 4096
SHARED_SECRET = b"super_secret_key_change_this"

# Simulated local clock skew/drift
INITIAL_LOCAL_OFFSET = 2.5   # seconds ahead/behind real time
DRIFT_RATE = 0.0005          # seconds drift per real second

# Smoothing factors
OFFSET_ALPHA = 0.3
DRIFT_ALPHA = 0.2


class LogicalClock:
    def __init__(self, initial_offset: float, drift_rate: float):
        self.start_real = time.time()
        self.initial_offset = initial_offset
        self.drift_rate = drift_rate
        self.corrected_offset = 0.0
        self.estimated_drift = 0.0

    def local_time(self) -> float:
        elapsed = time.time() - self.start_real
        raw = time.time() + self.initial_offset + (elapsed * self.drift_rate)
        return raw

    def synchronized_time(self) -> float:
        elapsed = time.time() - self.start_real
        raw = self.local_time()
        drift_correction = elapsed * self.estimated_drift
        return raw + self.corrected_offset + drift_correction

    def apply_sync(self, measured_offset: float, previous_offset: Optional[float], dt: Optional[float]):
        # Offset correction using EWMA
        self.corrected_offset = (
            (1 - OFFSET_ALPHA) * self.corrected_offset + OFFSET_ALPHA * measured_offset
        )

        # Drift estimation based on change in offset over time
        if previous_offset is not None and dt is not None and dt > 0:
            measured_drift = (measured_offset - previous_offset) / dt
            self.estimated_drift = (
                (1 - DRIFT_ALPHA) * self.estimated_drift + DRIFT_ALPHA * measured_drift
            )


def sign_message(message: dict) -> str:
    temp = dict(message)
    temp.pop("hmac", None)
    payload = json.dumps(temp, sort_keys=True).encode()
    return hmac.new(SHARED_SECRET, payload, hashlib.sha256).hexdigest()


def verify_message(message: dict) -> bool:
    received_hmac = message.get("hmac", "")
    expected_hmac = sign_message(message)
    return hmac.compare_digest(received_hmac, expected_hmac)


def sync_once(sock: socket.socket, server_ip: str, server_port: int, client_id: str, sequence: int):
    t1 = time.time()

    request = {
        "type": "sync_request",
        "client_id": client_id,
        "sequence": sequence,
        "t1": t1
    }
    request["hmac"] = sign_message(request)

    sock.sendto(json.dumps(request).encode(), (server_ip, server_port))

    data, _ = sock.recvfrom(BUFFER_SIZE)
    t4 = time.time()

    response = json.loads(data.decode())

    if not verify_message(response):
        raise ValueError("Response HMAC verification failed.")

    t1 = response["t1"]
    t2 = response["t2"]
    t3 = response["t3"]

    # Standard NTP-style formulas
    offset = ((t2 - t1) + (t3 - t4)) / 2.0
    delay = (t4 - t1) - (t3 - t2)

    return {
        "offset": offset,
        "delay": delay,
        "t1": t1,
        "t2": t2,
        "t3": t3,
        "t4": t4
    }


def main():
    parser = argparse.ArgumentParser(description="UDP Distributed Clock Sync Client")
    parser.add_argument("--server-ip", default=SERVER_IP)
    parser.add_argument("--server-port", type=int, default=SERVER_PORT)
    parser.add_argument("--client-id", default="client1")
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()

    clock = LogicalClock(INITIAL_LOCAL_OFFSET, DRIFT_RATE)
    offsets: List[float] = []
    delays: List[float] = []
    errors_before: List[float] = []
    errors_after: List[float] = []

    prev_offset = None
    prev_time = None

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5.0)

    print(f"[CLIENT {args.client_id}] Starting sync with {args.server_ip}:{args.server_port}")
    print(f"[CLIENT {args.client_id}] Simulated initial local offset = {INITIAL_LOCAL_OFFSET}s")
    print(f"[CLIENT {args.client_id}] Simulated drift rate = {DRIFT_RATE} s/s\n")

    for seq in range(1, args.rounds + 1):
        try:
            real_now = time.time()
            local_before = clock.local_time()
            synced_before = clock.synchronized_time()

            error_before = local_before - real_now
            errors_before.append(error_before)

            result = sync_once(sock, args.server_ip, args.server_port, args.client_id, seq)

            measured_offset = result["offset"]
            measured_delay = result["delay"]

            current_real = time.time()
            dt = None if prev_time is None else (current_real - prev_time)

            clock.apply_sync(measured_offset, prev_offset, dt)

            synced_after = clock.synchronized_time()
            error_after = synced_after - time.time()
            errors_after.append(error_after)

            offsets.append(measured_offset)
            delays.append(measured_delay)

            print(f"--- Round {seq} ---")
            print(f"Measured Offset : {measured_offset:.6f} s")
            print(f"Measured Delay  : {measured_delay:.6f} s")
            print(f"Raw Clock Error : {error_before:.6f} s")
            print(f"Corrected Error : {error_after:.6f} s")
            print(f"Estimated Drift : {clock.estimated_drift:.8f} s/s")
            print(f"Applied Offset  : {clock.corrected_offset:.6f} s\n")

            prev_offset = measured_offset
            prev_time = current_real

            time.sleep(args.interval)

        except socket.timeout:
            print(f"[CLIENT {args.client_id}] Timeout waiting for server response.")
        except Exception as e:
            print(f"[CLIENT {args.client_id}] Error: {e}")

    sock.close()

    print("\n========== Accuracy Evaluation ==========")
    if offsets:
        print(f"Average Measured Offset     : {statistics.mean(offsets):.6f} s")
        print(f"Average Network Delay       : {statistics.mean(delays):.6f} s")
        print(f"Max Network Delay           : {max(delays):.6f} s")
        print(f"Average Raw Clock Error     : {statistics.mean(errors_before):.6f} s")
        print(f"Average Corrected Clock Err : {statistics.mean(errors_after):.6f} s")
        print(f"Std Dev of Corrected Error  : {statistics.pstdev(errors_after):.6f} s")
    else:
        print("No successful synchronization samples collected.")


if __name__ == "__main__":
    main()