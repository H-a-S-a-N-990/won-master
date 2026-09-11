from flask import Flask, request, render_template_string
import socket
import struct
import time
import threading

app = Flask(__name__)

# ============================================================
# WON2 MASTER SERVERS
# ============================================================

MASTERS = [
    "master.won2.steamlessproject.nl",
    "master2.won2.steamlessproject.nl",
    "master3.won2.steamlessproject.nl",
    "master4.won2.steamlessproject.nl",
]

MASTER_PORT = 27010

# ============================================================
# MASTER SERVER QUERY
# ============================================================

def query_master(host):
    result = {
        "host": host,
        "ip": None,
        "tx": "",
        "rx": "",
        "length": 0,
        "time": 0,
        "servers": [],
        "error": None
    }

    try:
        ip = socket.gethostbyname(host)
        result["ip"] = ip

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)

        # Standard Half-Life/WON master request
        #
        # 31             = '1' / server list request
        # FF             = world region
        # 30.30.30.30:0  = start address
        # 00             = separator
        # \gamedir\*     = all games
        # 00             = terminator
        #
        packet = (
            b"1"
            + b"\xff"
            + b"0.0.0.0:0"
            + b"\x00"
            + b"\\gamedir\\*"
            + b"\x00"
        )

        result["tx"] = packet.hex(" ")

        start = time.time()

        sock.sendto(packet, (ip, MASTER_PORT))

        data, addr = sock.recvfrom(65535)

        elapsed = (time.time() - start) * 1000

        result["time"] = round(elapsed, 2)
        result["rx"] = data.hex(" ")
        result["length"] = len(data)

        sock.close()

        result["servers"] = parse_master_response(data)

    except Exception as e:
        result["error"] = str(e)

    return result

# ============================================================
# PARSE WON2 / HALF-LIFE MASTER RESPONSE
# ============================================================

def parse_master_response(data):
    """
    Parse FF FF FF FF 66 0A master response.

    Standard records are:

        4 bytes IP (little-endian)
        2 bytes PORT (big-endian)

    The header is followed by a variable-length hash cursor.
    We determine the cursor length by scanning for the first
    valid server record.
    """

    if len(data) < 12:
        return []

    header = b"\xff\xff\xff\xff\x66\x0a"

    if not data.startswith(header):
        return []

    # Find the start of the first server record.
    # The hash cursor is an unsigned long (4 bytes) but may
    # be truncated if the value is small.
    # We scan from offset 6 and look for a valid IP/port pair.
    start_offset = None
    for offset in range(6, len(data) - 5):
        ip_bytes = data[offset:offset+4]
        port_bytes = data[offset+4:offset+6]
        port = int.from_bytes(port_bytes, "big")
        # Basic sanity check for a real server.
        if ip_bytes[0] != 0 and ip_bytes[0] < 224 and port > 1024:
            start_offset = offset
            break

    if start_offset is None:
        return []

    records = []
    pos = start_offset

    while pos + 6 <= len(data):
        ip_bytes = data[pos:pos+4]
        port_bytes = data[pos+4:pos+6]
        port = int.from_bytes(port_bytes, "big")
        ip = ".".join(str(x) for x in ip_bytes)

        # Stop on normal master terminator.
        if ip == "0.0.0.0" and port == 0:
            break

        # Reject obviously bad candidates.
        if ip_bytes[0] == 0 or ip_bytes[0] >= 224 or port < 1024:
            break

        records.append((ip, port))
        pos += 6

    # Remove duplicates.
    final = []
    seen = set()
    for ip, port in records:
        server = f"{ip}:{port}"
        if server not in seen:
            seen.add(server)
            final.append(server)

    return final

# ============================================================
# QUERY ALL MASTERS
# ============================================================

def query_all_masters():
    results = []

    threads = []
    lock = threading.Lock()

    def worker(host):
        result = query_master(host)
        with lock:
            results.append(result)

    for host in MASTERS:
        thread = threading.Thread(target=worker, args=(host,))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    # Keep the original master order.
    results.sort(key=lambda x: MASTERS.index(x["host"]))

    return results

# ============================================================
# HTML
# ============================================================

HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>WON2 Master Server Browser</title>
<style>
body { font-family: Arial, sans-serif; background: #111; color: #eee; margin: 0; padding: 20px; }
h1 { margin-top: 0; }
button { padding: 10px 18px; background: #333; color: white; border: 1px solid #666; cursor: pointer; border-radius: 5px; }
button:hover { background: #444; }
.master { background: #1b1b1b; border: 1px solid #444; border-radius: 8px; margin-top: 20px; padding: 18px; }
.ok { color: #6cff6c; }
.error { color: #ff6666; }
.info { color: #aaa; }
.server { background: #252525; border: 1px solid #444; padding: 8px; margin: 4px 0; border-radius: 4px; font-family: monospace; }
pre { background: #080808; border: 1px solid #333; padding: 12px; overflow-x: auto; white-space: pre-wrap; word-break: break-all; font-size: 12px; }
.summary { background: #191919; padding: 15px; border: 1px solid #333; border-radius: 8px; margin-top: 20px; }
</style>
</head>
<body>
<h1>WON2 Master Server Browser</h1>
<form method="get">
    <button type="submit">Query Masters Again</button>
</form>
{% if results %}
<div class="summary">
<b>Total unique servers:</b> {{ total_servers }}
</div>
{% for r in results %}
<div class="master">
<h2>{{ r.host }}:27010</h2>
{% if r.error %}
<div class="error">ERROR: {{ r.error }}</div>
{% else %}
<div class="ok">Server responded</div>
<p>
<b>Master IP:</b> {{ r.ip }}<br>
<b>RX length:</b> {{ r.length }} bytes<br>
<b>Query time:</b> {{ r.time }} ms<br>
<b>Servers parsed:</b> {{ r.servers|length }}
</p>
<h3>Servers</h3>
{% if r.servers %}
{% for server in r.servers %}
<div class="server">{{ server }}</div>
{% endfor %}
{% else %}
<div class="error">No valid server records found.</div>
{% endif %}
<h3>TX</h3>
<pre>{{ r.tx }}</pre>
<h3>RX</h3>
<pre>{{ r.rx }}</pre>
{% endif %}
</div>
{% endfor %}
{% endif %}
</body>
</html>
"""

# ============================================================
# ROUTES
# ============================================================

@app.route("/", methods=["GET", "POST"])
def index():
    results = query_all_masters()
    unique = set()
    for result in results:
        for server in result["servers"]:
            unique.add(server)
    return render_template_string(
        HTML,
        results=results,
        total_servers=len(unique)
    )

# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():
    return "OK"

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
