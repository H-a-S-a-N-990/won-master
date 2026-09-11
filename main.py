import socket
import struct
import time
from flask import Flask, request, render_template_string

app = Flask(__name__)

# --- Constants ---
MASTER_SERVERS = [
    "master.won2.steamlessproject.nl",
    "master2.won2.steamlessproject.nl",
    "master3.won2.steamlessproject.nl",
    "master4.won2.steamlessproject.nl",
]
MASTER_PORT = 27010
REQUEST_HEADER = b"\x31\xff"  # From your request: 31 ff
# The request likely contains a game filter, e.g., \game\*\0
# Your example: 31 ff 30 2e 30 2e 30 2e 30 3a 30 00 5c 67 61 6d 65 64 69 72 5c 2a 00
# This is "1.0.0.0:0\gamedir\*"
GAME_FILTER = b"\\gamedir\\*\\0"

# --- Protocol Parsing ---

def parse_master_response(data):
    """
    Parses a WON2 master server response (header 0x66).
    Returns: (list_of_servers, next_hash_cursor)
    """
    if len(data) < 6 or data[:4] != b"\xff\xff\xff\xff" or data[4] != 0x66:
        return [], 0

    # The next hash cursor is stored after the header (0x0A).
    # The length is variable, but typically 4 bytes.
    # We'll assume a 4-byte little-endian integer for the cursor.
    # The zero bytes after 66 0A are part of this cursor.
    if len(data) < 10:
        return [], 0
    next_hash = struct.unpack_from("<I", data, 6)[0]

    servers = []
    offset = 10  # Start of records after header (4 header + 1 type + 4 hash + 1? = 10)
    # Actually, from your evidence: 66 0a 00 00 00 00 -> 6 bytes header, then records start at offset 6.
    # Let's use offset 6 as the start of the first record.
    offset = 6
    while offset + 6 <= len(data):
        # IP: 4 bytes, little-endian
        ip_int = struct.unpack_from("<I", data, offset)[0]
        # Port: 2 bytes, BIG-ENDIAN (network order)
        port = struct.unpack_from(">H", data, offset + 4)[0]
        # Basic sanity check: port must be > 0 and < 65536
        if port > 0:
            ip_str = socket.inet_ntoa(struct.pack("<I", ip_int))
            servers.append((ip_str, port))
        offset += 6

    return servers, next_hash

def query_master(master_host, max_pages=10):
    """
    Queries a single master server, handling pagination via hash cursor.
    Returns a list of (ip, port) tuples.
    """
    all_servers = []
    current_hash = 0  # Initial cursor

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5.0)

    for page in range(max_pages):
        # Build the request. The request format from your example:
        # 31 ff 30 2e 30 2e 30 2e 30 3a 30 00 5c 67 61 6d 65 64 69 72 5c 2a 00
        # This is "1.0.0.0:0\gamedir\*"
        # For pagination, we likely need to send the hash cursor instead of "1.0.0.0:0".
        # The format for the cursor is unknown, but it's likely a 4-byte value.
        # We'll try sending the 4-byte hash after the 0x31 0xff header.
        request = REQUEST_HEADER + struct.pack("<I", current_hash) + GAME_FILTER
        # In the initial request, current_hash is 0, so this matches your example if GAME_FILTER is correct.

        try:
            sock.sendto(request, (master_host, MASTER_PORT))
            data, _ = sock.recvfrom(8192)
        except socket.timeout:
            break  # No response, stop pagination

        servers, next_hash = parse_master_response(data)
        if not servers:
            break

        all_servers.extend(servers)

        # If the next_hash is 0, we've reached the end.
        if next_hash == 0:
            break
        current_hash = next_hash
        # Small delay to avoid flooding the master server
        time.sleep(0.1)

    sock.close()
    # Deduplicate
    return list(set(all_servers))

# --- Flask App ---

HTML = """
<!DOCTYPE html>
<html>
<head><title>WON2 Master Server Browser</title></head>
<body>
    <h1>WON2 Master Server Browser</h1>
    <p>Querying all master servers. This may take a few seconds...</p>
    <hr>
    <h2>Results ({{ servers|length }} servers)</h2>
    <table border="1">
        <tr><th>IP Address</th><th>Port</th></tr>
        {% for ip, port in servers %}
        <tr><td>{{ ip }}</td><td>{{ port }}</td></tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route("/")
def index():
    all_servers = []
    for master in MASTER_SERVERS:
        try:
            servers = query_master(master)
            all_servers.extend(servers)
            print(f"Master {master} returned {len(servers)} servers.")
        except Exception as e:
            print(f"Error querying {master}: {e}")

    # Final deduplication
    unique_servers = sorted(list(set(all_servers)))
    return render_template_string(HTML, servers=unique_servers)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
