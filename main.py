from flask import Flask, request, render_template_string
import socket
import struct
import time
import threading

app = Flask(__name__)

MASTERS = [
    "master.won2.steamlessproject.nl",
    "master2.won2.steamlessproject.nl",
    "master3.won2.steamlessproject.nl",
    "master4.won2.steamlessproject.nl",
]

MASTER_PORT = 27010
GAME_FILTER = b"\\gamedir\\*\\0"


def parse_master_response(data):
    """
    Parse WON2 master response.

    Header: FF FF FF FF 66 0A
    Then: variable-length hash cursor
    Then: 6-byte records (4 IP + 2 port big-endian)
    """
    if len(data) < 8:
        return [], 0

    if data[:5] != b"\xff\xff\xff\xff\x66":
        return [], 0

    # Find start of first valid server record.
    # Rule: first 6-byte window where IP != 0.0.0.0 and port > 1024.
    start = None
    for offset in range(6, min(len(data) - 5, 20)):
        ip_bytes = data[offset:offset + 4]
        port_bytes = data[offset + 4:offset + 6]
        port = int.from_bytes(port_bytes, "big")
        if ip_bytes[0] != 0 and port > 1024:
            start = offset
            break

    if start is None:
        return [], 0

    # Extract hash cursor (bytes between header and first record).
    cursor_bytes = data[6:start]
    cursor = int.from_bytes(cursor_bytes, "little") if cursor_bytes else 0

    servers = []
    pos = start

    while pos + 6 <= len(data):
        ip_bytes = data[pos:pos + 4]
        port_bytes = data[pos + 4:pos + 6]
        port = int.from_bytes(port_bytes, "big")
        ip = ".".join(str(b) for b in ip_bytes)

        # Terminator
        if ip == "0.0.0.0" and port == 0:
            break

        # Sanity
        if ip_bytes[0] == 0 or ip_bytes[0] >= 224 or port < 1024:
            break

        servers.append((ip, port))
        pos += 6

    return servers, cursor


def query_master(host, max_pages=10):
    result = {
        "host": host,
        "ip": None,
        "tx": [],
        "rx": [],
        "servers": [],
        "error": None,
        "pages": 0,
    }

    try:
        ip = socket.gethostbyname(host)
        result["ip"] = ip

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)

        cursor = None

        for page in range(max_pages):
            # Build request
            if cursor is None:
                # Initial: string cursor 0.0.0.0:0
                packet = b"1\xff" + b"0.0.0.0:0\x00" + GAME_FILTER
            else:
                # Subsequent: 4-byte hash cursor
                packet = b"1\xff" + struct.pack("<I", cursor) + b"\x00" + GAME_FILTER

            result["tx"].append(packet.hex(" "))

            sock.sendto(packet, (ip, MASTER_PORT))
            data, _ = sock.recvfrom(65535)

            result["rx"].append(data.hex(" "))

            servers, next_cursor = parse_master_response(data)

            if not servers:
                break

            result["servers"].extend(servers)
            result["pages"] += 1

            # If cursor is 0 or unchanged, stop
            if next_cursor == 0 or next_cursor == cursor:
                break

            cursor = next_cursor
            time.sleep(0.1)

        sock.close()

        # Deduplicate
        seen = set()
        unique = []
        for ip_str, port in result["servers"]:
            key = f"{ip_str}:{port}"
            if key not in seen:
                seen.add(key)
                unique.append((ip_str, port))
        result["servers"] = unique

    except Exception as e:
        result["error"] = str(e)

    return result


def query_all_masters():
    results = []
    threads = []
    lock = threading.Lock()

    def worker(h):
        r = query_master(h)
        with lock:
            results.append(r)

    for h in MASTERS:
        t = threading.Thread(target=worker, args=(h,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    results.sort(key=lambda x: MASTERS.index(x["host"]))
    return results


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
.server { background: #252525; border: 1px solid #444; padding: 8px; margin: 4px 0; border-radius: 4px; font-family: monospace; }
pre { background: #080808; border: 1px solid #333; padding: 12px; overflow-x: auto; white-space: pre-wrap; word-break: break-all; font-size: 11px; }
.summary { background: #191919; padding: 15px; border: 1px solid #333; border-radius: 8px; margin-top: 20px; }
</style>
</head>
<body>
<h1>WON2 Master Server Browser</h1>
<form method="get"><button type="submit">Query Masters Again</button></form>

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
<div class="ok">Responded — {{ r.pages }} page(s), {{ r.servers|length }} unique servers</div>
<p><b>Master IP:</b> {{ r.ip }}</p>

<h3>Servers</h3>
{% for ip, port in r.servers %}
<div class="server">{{ ip }}:{{ port }}</div>
{% endfor %}

<h3>TX (requests)</h3>
{% for tx in r.tx %}
<pre>{{ tx }}</pre>
{% endfor %}

<h3>RX (responses)</h3>
{% for rx in r.rx %}
<pre>{{ rx }}</pre>
{% endfor %}
{% endif %}
</div>
{% endfor %}
{% endif %}
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    results = query_all_masters()
    unique = set()
    for r in results:
        for ip, port in r["servers"]:
            unique.add(f"{ip}:{port}")
    return render_template_string(
        HTML,
        results=results,
        total_servers=len(unique),
    )


@app.route("/health")
def health():
    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
