from flask import Flask
import socket
import struct
import time

app = Flask(__name__)

# ============================================================
# WON2 MASTER SERVERS
# ============================================================

WON2_MASTERS = [
    ("master.won2.steamlessproject.nl", 27010),
    ("master2.won2.steamlessproject.nl", 27010),
    ("master3.won2.steamlessproject.nl", 27010),
    ("master4.won2.steamlessproject.nl", 27010),
]

MASTER_TIMEOUT = 3.0


# ============================================================
# QUERY ONE MASTER
# ============================================================

def query_master(host, port):
    servers = []

    try:
        # Resolve master hostname
        master_ip = socket.gethostbyname(host)

        # Half-Life/WON master query
        #
        # 31       = server list request
        # FF       = region / all regions
        # 0.0.0.0:0
        # \gamedir\cstrike
        #
        packet = (
            b"\x31"
            b"\xff"
            + b"0.0.0.0:0"
            + b"\x00"
            + b"\\gamedir\\cstrike"
            + b"\x00"
        )

        print()
        print("MASTER:", host, port)
        print("TX:", packet.hex(" "))

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(MASTER_TIMEOUT)

        start_time = time.time()

        sock.sendto(packet, (master_ip, port))

        data, address = sock.recvfrom(65535)

        elapsed = (time.time() - start_time) * 1000

        sock.close()

        print("RX:", len(data), "bytes")
        print(data.hex(" "))
        print("Ping:", round(elapsed, 2), "ms")

        # ----------------------------------------------------
        # Check WON/GoldSrc master response header
        # FF FF FF FF 66 0A
        # ----------------------------------------------------

        if not data.startswith(
            b"\xff\xff\xff\xff\x66\x0a"
        ):
            print("INVALID MASTER RESPONSE HEADER")
            return servers

        # Server records begin immediately after:
        #
        # FF FF FF FF 66 0A
        #
        # Each server:
        #
        # 4 bytes IP
        # 2 bytes PORT
        #
        offset = 6

        while offset + 6 <= len(data):

            ip_bytes = data[offset:offset + 4]
            port_bytes = data[offset + 4:offset + 6]

            # IP
            ip = ".".join(str(x) for x in ip_bytes)

            # IMPORTANT:
            # WON master server ports are NETWORK ORDER / BIG ENDIAN
            port_number = struct.unpack(
                ">H",
                port_bytes
            )[0]

            # ------------------------------------------------
            # REAL END OF LIST
            #
            # Only 0.0.0.0:0 is the terminator.
            #
            # 0.0.0.0:<nonzero port> is NOT a terminator.
            # ------------------------------------------------

            if ip == "0.0.0.0" and port_number == 0:
                print("END OF MASTER LIST")
                break

            server = f"{ip}:{port_number}"

            servers.append(server)

            print(
                "FOUND:",
                server,
                "| RAW:",
                ip_bytes.hex(" "),
                port_bytes.hex(" ")
            )

            offset += 6

        return servers

    except socket.timeout:
        print("TIMEOUT:", host)
        return servers

    except Exception as e:
        print("ERROR:", host, str(e))
        return servers


# ============================================================
# QUERY ALL MASTERS
# ============================================================

def get_all_servers():

    all_servers = []
    master_results = []

    for host, port in WON2_MASTERS:

        servers = query_master(host, port)

        master_results.append({
            "host": host,
            "port": port,
            "servers": servers
        })

        all_servers.extend(servers)

    # --------------------------------------------------------
    # Remove duplicates while keeping order
    # --------------------------------------------------------

    unique_servers = []

    seen = set()

    for server in all_servers:

        if server not in seen:
            seen.add(server)
            unique_servers.append(server)

    return unique_servers, master_results


# ============================================================
# WEB PAGE
# ============================================================

@app.route("/")
def index():

    servers, master_results = get_all_servers()

    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport"
          content="width=device-width, initial-scale=1">

    <title>WON2 Master Server Browser</title>

    <style>

        body {
            font-family: Arial, sans-serif;
            background: #111;
            color: #eee;
            margin: 0;
            padding: 20px;
        }

        .container {
            max-width: 1000px;
            margin: auto;
        }

        h1 {
            margin-bottom: 5px;
        }

        .subtitle {
            color: #aaa;
            margin-bottom: 25px;
        }

        .stats {
            background: #1d1d1d;
            border: 1px solid #333;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 6px;
        }

        .stats strong {
            color: #6db3ff;
        }

        .master {
            background: #1a1a1a;
            border: 1px solid #333;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 6px;
        }

        .master-title {
            font-weight: bold;
            margin-bottom: 10px;
        }

        .master-count {
            color: #7bd88f;
        }

        .servers {
            background: #080808;
            border: 1px solid #292929;
            padding: 15px;
            border-radius: 6px;
            font-family: monospace;
            white-space: pre-wrap;
            word-break: break-all;
        }

        .server {
            padding: 5px 0;
            border-bottom: 1px solid #222;
        }

        .server:last-child {
            border-bottom: none;
        }

        .number {
            color: #777;
            display: inline-block;
            width: 45px;
        }

        .ip {
            color: #6db3ff;
        }

        .refresh {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 16px;
            background: #2b6cb0;
            color: white;
            text-decoration: none;
            border-radius: 5px;
        }

        .refresh:hover {
            background: #357dcc;
        }

    </style>
</head>

<body>

<div class="container">

    <h1>WON2 Master Server Browser</h1>

    <div class="subtitle">
        Direct Half-Life / WON2 master server query
    </div>
"""

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    html += f"""
    <div class="stats">
        <div>
            <strong>Servers found:</strong>
            {len(servers)}
        </div>

        <div>
            <strong>Masters queried:</strong>
            {len(master_results)}
        </div>
    </div>
"""

    # --------------------------------------------------------
    # Master results
    # --------------------------------------------------------

    html += """
    <h2>Master Results</h2>
"""

    for result in master_results:

        html += f"""
    <div class="master">

        <div class="master-title">
            {result["host"]}:{result["port"]}
        </div>

        <div class="master-count">
            {len(result["servers"])} servers
        </div>

    </div>
"""

    # --------------------------------------------------------
    # Server list
    # --------------------------------------------------------

    html += """
    <h2>Servers</h2>

    <div class="servers">
"""

    if not servers:

        html += """
        No servers found.
"""

    else:

        for i, server in enumerate(servers, 1):

            html += f"""
        <div class="server">
            <span class="number">{i}.</span>
            <span class="ip">{server}</span>
        </div>
"""

    html += """
    </div>

    <a class="refresh" href="/">
        Refresh
    </a>

</div>

</body>
</html>
"""

    return html


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return {
        "status": "ok"
    }


# ============================================================
# RUN LOCALLY
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=10000,
        debug=False
    )
