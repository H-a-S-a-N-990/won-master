from flask import Flask, Response
import socket
import struct
import os

app = Flask(__name__)

# WON2 master servers
MASTERS = [
    ("master.won2.steamlessproject.nl", 27010),
]


def query_master(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)

    servers = set()

    # First request starts at 0.0.0.0:0
    start = "0.0.0.0:0"

    try:
        while True:

            # WON/WON2 master query
            packet = (
                b"\x31" +
                b"\xff" +
                start.encode("ascii") +
                b"\x00"
            )

            print(
                "TX",
                host,
                port,
                packet.hex(" ")
            )

            sock.sendto(packet, (host, port))

            data, address = sock.recvfrom(8192)

            print(
                "RX",
                host,
                port,
                len(data),
                "bytes"
            )

            print(data.hex(" "))

            # Expected master response:
            # FF FF FF FF 66 0A
            if not data.startswith(
                b"\xff\xff\xff\xff\x66\x0a"
            ):
                print(
                    "Unexpected response from",
                    host,
                    port
                )
                break

            payload = data[6:]

            # Every server entry:
            #
            # 4 bytes IPv4
            # 2 bytes port
            #
            # Total = 6 bytes
            if len(payload) < 6:
                break

            previous_start = start
            last_server = None

            for i in range(0, len(payload) - 5, 6):

                ip_bytes = payload[i:i + 4]
                port_bytes = payload[i + 4:i + 6]

                try:
                    ip = socket.inet_ntoa(ip_bytes)
                except Exception:
                    continue

                # WON/WON2 port
                # LITTLE-ENDIAN
                server_port = struct.unpack(
                    "<H",
                    port_bytes
                )[0]

                # Ignore empty entry
                if ip == "0.0.0.0" and server_port == 0:
                    continue

                server = "{}:{}".format(
                    ip,
                    server_port
                )

                print(
                    "FOUND:",
                    server
                )

                servers.add(server)

                last_server = server

            # Nothing new
            if last_server is None:
                break

            # Continue from last server returned
            start = last_server

            # Prevent infinite loop
            if start == previous_start:
                break

    except socket.timeout:
        print(
            "TIMEOUT:",
            host,
            port
        )

    except Exception as e:
        print(
            "ERROR:",
            host,
            port,
            repr(e)
        )

    finally:
        sock.close()

    return servers


@app.route("/")
def index():

    all_servers = set()
    master_results = []

    for master_host, master_port in MASTERS:

        found = query_master(
            master_host,
            master_port
        )

        all_servers.update(found)

        master_results.append(
            "{}:{} -> {} servers".format(
                master_host,
                master_port,
                len(found)
            )
        )

    lines = []

    lines.append(
        "WON2 MASTER SERVER BROWSER"
    )

    lines.append(
        "========================================"
    )

    lines.append("")

    lines.append(
        "Servers found: {}".format(
            len(all_servers)
        )
    )

    lines.append("")

    # Master statistics
    lines.append(
        "MASTER RESULTS"
    )

    lines.append(
        "----------------------------------------"
    )

    for result in master_results:
        lines.append(result)

    lines.append("")

    lines.append(
        "SERVERS"
    )

    lines.append(
        "----------------------------------------"
    )

    # Raw IP:PORT
    for server in sorted(
        all_servers,
        key=lambda x: (
            x.split(":")[0],
            int(x.split(":")[1])
        )
    ):
        lines.append(server)

    return Response(
        "\n".join(lines),
        mimetype="text/plain"
    )


@app.route("/health")
def health():
    return "OK"


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "5000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
