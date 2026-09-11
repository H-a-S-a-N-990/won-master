from flask import Flask
import socket
import struct
import time
import html

app = Flask(__name__)

# ============================================================
# CONFIG
# ============================================================

WON2_MASTERS = [
    ("master.won2.steamlessproject.nl", 27010),
    ("master2.won2.steamlessproject.nl", 27010),
    ("master3.won2.steamlessproject.nl", 27010),
    ("master4.won2.steamlessproject.nl", 27010),
]

MASTER_TIMEOUT = 3.0


# ============================================================
# QUERY MASTER
# ============================================================

def query_master(host, port):

    servers = []

    raw_info = {
        "tx": "",
        "rx": "",
        "rx_length": 0,
        "records": [],
        "error": "",
        "time_ms": 0
    }

    try:

        master_ip = socket.gethostbyname(host)

        # ====================================================
        # WON / WON2 MASTER QUERY
        #
        # 31 FF
        # 0.0.0.0:0
        # \gamedir\cstrike
        # ====================================================

        packet = (
            b"\x31"
            b"\xff"
            + b"0.0.0.0:0"
            + b"\x00"
            + b"\\gamedir\\cstrike"
            + b"\x00"
        )

        raw_info["tx"] = packet.hex(" ")

        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        sock.settimeout(MASTER_TIMEOUT)

        start_time = time.time()

        sock.sendto(
            packet,
            (master_ip, port)
        )

        data, address = sock.recvfrom(65535)

        elapsed = (
            time.time() - start_time
        ) * 1000

        sock.close()

        raw_info["rx"] = data.hex(" ")
        raw_info["rx_length"] = len(data)
        raw_info["time_ms"] = round(elapsed, 2)

        # ====================================================
        # CHECK RESPONSE
        #
        # FF FF FF FF 66 0A
        # ====================================================

        header = b"\xff\xff\xff\xff\x66\x0a"

        if not data.startswith(header):

            raw_info["error"] = (
                "Invalid master response header"
            )

            return servers, raw_info

        # ====================================================
        # PARSE SERVER RECORDS
        #
        # Each record:
        #
        # 4 bytes IP
        # 2 bytes PORT
        # ====================================================

        offset = 6

        while offset + 6 <= len(data):

            ip_bytes = data[
                offset:
                offset + 4
            ]

            port_bytes = data[
                offset + 4:
                offset + 6
            ]

            # ------------------------------------------------
            # IP
            # ------------------------------------------------

            ip = ".".join(
                str(x)
                for x in ip_bytes
            )

            # ------------------------------------------------
            # Port - BOTH endian versions
            # ------------------------------------------------

            port_be = struct.unpack(
                ">H",
                port_bytes
            )[0]

            port_le = struct.unpack(
                "<H",
                port_bytes
            )[0]

            # ------------------------------------------------
            # Save raw record for webpage
            # ------------------------------------------------

            record = {
                "offset": offset,
                "raw": (
                    ip_bytes.hex(" ")
                    + " "
                    + port_bytes.hex(" ")
                ),
                "ip": ip,
                "port_be": port_be,
                "port_le": port_le
            }

            raw_info["records"].append(record)

            # ------------------------------------------------
            # REAL END OF LIST
            #
            # Only 0.0.0.0:0
            # ------------------------------------------------

            if (
                ip == "0.0.0.0"
                and port_be == 0
            ):
                break

            # ------------------------------------------------
            # Current interpretation
            # ------------------------------------------------

            servers.append(
                f"{ip}:{port_be}"
            )

            offset += 6

        return servers, raw_info

    except Exception as e:

        raw_info["error"] = str(e)

        return servers, raw_info


# ============================================================
# QUERY ALL MASTERS
# ============================================================

def get_all_servers():

    all_servers = []

    master_results = []

    for host, port in WON2_MASTERS:

        servers, raw_info = query_master(
            host,
            port
        )

        master_results.append({
            "host": host,
            "port": port,
            "servers": servers,
            "raw": raw_info
        })

        all_servers.extend(servers)

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

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

    page = """
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1">

<title>WON2 Master Server Browser</title>

<style>

* {
    box-sizing: border-box;
}

body {

    margin: 0;

    padding: 20px;

    background: #111;

    color: #eee;

    font-family:
        Arial,
        Helvetica,
        sans-serif;
}

.container {

    max-width: 1100px;

    margin: auto;
}

h1 {

    margin-bottom: 5px;
}

h2 {

    margin-top: 30px;

    border-bottom:
        1px solid #333;

    padding-bottom: 8px;
}

h3 {

    margin-top: 0;

    color: #6db3ff;
}

h4 {

    margin-bottom: 8px;
}

.subtitle {

    color: #aaa;

    margin-bottom: 25px;
}

.stats {

    background: #1d1d1d;

    border:
        1px solid #333;

    border-radius: 6px;

    padding: 15px;

    margin-bottom: 20px;

    line-height: 1.8;
}

.stats strong {

    color: #6db3ff;
}

.master {

    background: #191919;

    border:
        1px solid #333;

    border-radius: 6px;

    padding: 15px;

    margin-bottom: 20px;
}

.master-count {

    color: #7bd88f;

    margin-bottom: 15px;
}

.server-list {

    background: #080808;

    border:
        1px solid #292929;

    border-radius: 6px;

    padding: 15px;

    font-family: monospace;
}

.server {

    padding: 6px 0;

    border-bottom:
        1px solid #222;
}

.server:last-child {

    border-bottom: none;
}

.number {

    display: inline-block;

    width: 50px;

    color: #777;
}

.ip {

    color: #6db3ff;
}

.raw {

    background: #050505;

    border:
        1px solid #333;

    border-radius: 5px;

    padding: 15px;

    overflow-x: auto;

    white-space: pre-wrap;

    word-break: break-all;

    font-family: monospace;

    font-size: 12px;

    line-height: 1.6;

    color: #ddd;
}

.record {

    background: #0b0b0b;

    border:
        1px solid #292929;

    border-radius: 5px;

    padding: 12px;

    margin:
        8px 0;

    font-family: monospace;

    font-size: 13px;

    line-height: 1.7;
}

.record-title {

    color: #aaa;

    margin-bottom: 5px;
}

.record code {

    color: #7bd88f;
}

.error {

    background: #351818;

    border:
        1px solid #713333;

    color: #ff7777;

    padding: 10px;

    border-radius: 5px;

    margin-bottom: 10px;
}

.info {

    background: #171f29;

    border:
        1px solid #30465c;

    color: #aaa;

    padding: 10px;

    border-radius: 5px;

    margin-bottom: 15px;
}

.refresh {

    display: inline-block;

    margin-top: 20px;

    padding:
        10px 18px;

    background: #2b6cb0;

    color: white;

    text-decoration: none;

    border-radius: 5px;
}

.refresh:hover {

    background: #357dcc;
}

.small {

    color: #888;

    font-size: 12px;
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

    # ========================================================
    # STATISTICS
    # ========================================================

    page += f"""

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

    # ========================================================
    # MASTER RESULTS
    # ========================================================

    page += """

<h2>Master Results</h2>

"""

    for result in master_results:

        host = html.escape(
            result["host"]
        )

        page += f"""

<div class="master">

<h3>
{host}:{result["port"]}
</h3>

<div class="master-count">
{len(result["servers"])} servers
</div>

"""

        raw = result["raw"]

        if raw.get("error"):

            error = html.escape(
                raw["error"]
            )

            page += f"""

<div class="error">
{error}
</div>

"""

        page += f"""

<div class="info">

RX length:
<strong>
{raw.get("rx_length", 0)}
bytes
</strong>

&nbsp;&nbsp;

Query time:
<strong>
{raw.get("time_ms", 0)}
ms
</strong>

</div>

</div>
"""

    # ========================================================
    # SERVER LIST
    # ========================================================

    page += """

<h2>Servers</h2>

<div class="server-list">

"""

    if not servers:

        page += """

<div>
No servers found.
</div>

"""

    else:

        for i, server in enumerate(
            servers,
            1
        ):

            safe_server = html.escape(
                server
            )

            page += f"""

<div class="server">

<span class="number">
{i}.
</span>

<span class="ip">
{safe_server}
</span>

</div>

"""

    page += """

</div>
"""

    # ========================================================
    # RAW PACKETS
    # ========================================================

    page += """

<h2>Raw Master Packets</h2>

<div class="info">

This section shows the exact UDP packets received
from each WON2 master. Each parsed record is also
shown as raw bytes with both port byte-order
interpretations.

</div>

"""

    for result in master_results:

        host = html.escape(
            result["host"]
        )

        raw = result["raw"]

        page += f"""

<div class="master">

<h3>
{host}:{result["port"]}
</h3>

<h4>TX Packet</h4>

<pre class="raw">{html.escape(
    raw.get("tx", "")
)}</pre>

<h4>RX Packet</h4>

<pre class="raw">{html.escape(
    raw.get("rx", "")
)}</pre>

<h4>Parsed 6-byte Records</h4>

"""

        records = raw.get(
            "records",
            []
        )

        if not records:

            page += """

<div class="small">
No records parsed.
</div>

"""

        else:

            for record in records:

                record_raw = html.escape(
                    record["raw"]
                )

                ip = html.escape(
                    record["ip"]
                )

                page += f"""

<div class="record">

<div class="record-title">
Offset {record["offset"]}
</div>

RAW:

<code>
{record_raw}
</code>

<br>

IP:

<code>
{ip}
</code>

<br>

BIG-ENDIAN:

<code>
{ip}:{record["port_be"]}
</code>

<br>

LITTLE-ENDIAN:

<code>
{ip}:{record["port_le"]}
</code>

</div>

"""

        page += """

</div>

"""

    # ========================================================
    # FOOTER
    # ========================================================

    page += """

<a class="refresh"
   href="/">
Refresh Master List
</a>

</div>

</body>

</html>
"""

    return page


# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():

    return {
        "status": "ok"
    }


# ============================================================
# LOCAL RUN
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=10000,
        debug=False
            )
