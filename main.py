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

        all_servers = []
        seen_servers = set()
        seen_cursors = set()

        # ----------------------------------------------------
        # First request starts at 0.0.0.0:0
        # ----------------------------------------------------

        cursor = "0.0.0.0:0"

        first_tx = ""
        first_rx = ""
        first_length = 0

        total_start = time.time()

        # ----------------------------------------------------
        # Continue requesting pages
        # ----------------------------------------------------

        for page in range(20):

            packet = (
                b"1"
                + b"\xff"
                + cursor.encode("ascii")
                + b"\x00"
                + b"\\gamedir\\*"
                + b"\x00"
            )

            # Save first request for diagnostics
            if page == 0:
                first_tx = packet.hex(" ")

            page_start = time.time()

            sock.sendto(
                packet,
                (ip, MASTER_PORT)
            )

            data, addr = sock.recvfrom(65535)

            page_time = (time.time() - page_start) * 1000

            # Save first response for diagnostics
            if page == 0:
                first_rx = data.hex(" ")
                first_length = len(data)
                result["time"] = round(page_time, 2)

            # ------------------------------------------------
            # Parse this page
            # ------------------------------------------------

            servers, finished = parse_master_response(data)

            if not servers:
                break

            new_servers = 0

            # ------------------------------------------------
            # Add new servers
            # ------------------------------------------------

            for server in servers:

                if server not in seen_servers:

                    seen_servers.add(server)
                    all_servers.append(server)

                    new_servers += 1

            # ------------------------------------------------
            # Normal end marker
            # ------------------------------------------------

            if finished:
                break

            # ------------------------------------------------
            # Last server becomes next cursor
            # ------------------------------------------------

            last_server = servers[-1]

            # Prevent endless loops
            if last_server == cursor:
                break

            if last_server in seen_cursors:
                break

            seen_cursors.add(last_server)

            cursor = last_server

            # If the master gave us nothing new, stop
            if new_servers == 0:
                break

        sock.close()

        # ----------------------------------------------------
        # Final result
        # ----------------------------------------------------

        result["servers"] = all_servers

        result["tx"] = first_tx
        result["rx"] = first_rx
        result["length"] = first_length

        result["time"] = round(
            (time.time() - total_start) * 1000,
            2
        )

    except Exception as e:

        result["error"] = str(e)

    return result


# ============================================================
# PARSE WON2 / HALF-LIFE MASTER RESPONSE
# ============================================================

def parse_master_response(data):
    """
    Parse a WON/WON2 master response.

    Normal response header:

        FF FF FF FF 66 0A

    The currently observed WON2 response contains:

        FF FF FF FF 66 0A 00 00

    so server records begin at offset 8.

    Each server record:

        4 bytes IP
        2 bytes PORT

    IP is represented directly as four bytes.

    Port is BIG-ENDIAN / network byte order.

    Example:

        31 e8 dd e5 51 4a

    becomes:

        49.232.221.229:20810

    A 0.0.0.0:0 record is treated as the end marker.
    """

    if len(data) < 12:
        return [], False

    header = b"\xff\xff\xff\xff\x66\x0a"

    if not data.startswith(header):
        return [], False

    # --------------------------------------------------------
    # WON2 observed format has 00 00 after the header
    # --------------------------------------------------------

    if len(data) >= 8 and data[6:8] == b"\x00\x00":

        offset = 8

    else:

        offset = 6

    servers = []
    finished = False

    # --------------------------------------------------------
    # Read 6-byte server records
    # --------------------------------------------------------

    while offset + 6 <= len(data):

        ip_bytes = data[offset:offset + 4]

        port_bytes = data[offset + 4:offset + 6]

        # ----------------------------------------------------
        # IP
        # ----------------------------------------------------

        ip = ".".join(
            str(x)
            for x in ip_bytes
        )

        # ----------------------------------------------------
        # Port
        # ----------------------------------------------------

        port = int.from_bytes(
            port_bytes,
            "big"
        )

        # ----------------------------------------------------
        # End marker
        # ----------------------------------------------------

        if ip == "0.0.0.0" and port == 0:

            finished = True
            break

        # ----------------------------------------------------
        # Ignore FF FF FF FF : 65535
        # ----------------------------------------------------

        if (
            ip_bytes == b"\xff\xff\xff\xff"
            and port == 65535
        ):

            offset += 6
            continue

        # ----------------------------------------------------
        # Add server
        # ----------------------------------------------------

        servers.append(
            f"{ip}:{port}"
        )

        offset += 6

    return servers, finished


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

    # --------------------------------------------------------
    # Query all masters simultaneously
    # --------------------------------------------------------

    for host in MASTERS:

        thread = threading.Thread(
            target=worker,
            args=(host,)
        )

        thread.start()

        threads.append(thread)

    # --------------------------------------------------------
    # Wait for all masters
    # --------------------------------------------------------

    for thread in threads:

        thread.join()

    # --------------------------------------------------------
    # Keep original master order
    # --------------------------------------------------------

    results.sort(
        key=lambda x: MASTERS.index(
            x["host"]
        )
    )

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

body {
    font-family: Arial, sans-serif;
    background: #111;
    color: #eee;
    margin: 0;
    padding: 20px;
}

h1 {
    margin-top: 0;
}

button {
    padding: 10px 18px;
    background: #333;
    color: white;
    border: 1px solid #666;
    cursor: pointer;
    border-radius: 5px;
}

button:hover {
    background: #444;
}

.master {
    background: #1b1b1b;
    border: 1px solid #444;
    border-radius: 8px;
    margin-top: 20px;
    padding: 18px;
}

.ok {
    color: #6cff6c;
}

.error {
    color: #ff6666;
}

.info {
    color: #aaa;
}

.server {
    background: #252525;
    border: 1px solid #444;
    padding: 8px;
    margin: 4px 0;
    border-radius: 4px;
    font-family: monospace;
}

pre {
    background: #080808;
    border: 1px solid #333;
    padding: 12px;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
    font-size: 12px;
}

.summary {
    background: #191919;
    padding: 15px;
    border: 1px solid #333;
    border-radius: 8px;
    margin-top: 20px;
}

</style>

</head>

<body>

<h1>WON2 Master Server Browser</h1>

<form method="get">

    <button type="submit">
        Query Masters Again
    </button>

</form>

{% if results %}

<div class="summary">

<b>Total unique servers:</b>
{{ total_servers }}

</div>

{% for r in results %}

<div class="master">

<h2>{{ r.host }}:27010</h2>

{% if r.error %}

<div class="error">

    ERROR: {{ r.error }}

</div>

{% else %}

<div class="ok">

    Server responded

</div>

<p>

<b>Master IP:</b>
{{ r.ip }}

<br>

<b>RX length:</b>
{{ r.length }}
bytes

<br>

<b>Query time:</b>
{{ r.time }}
ms

<br>

<b>Servers parsed:</b>
{{ r.servers|length }}

</p>

<h3>Servers</h3>

{% if r.servers %}

{% for server in r.servers %}

<div class="server">

    {{ server }}

</div>

{% endfor %}

{% else %}

<div class="error">

    No valid server records found.

</div>

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

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
        )
