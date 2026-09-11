from flask import Flask, Response
import socket
import struct
import os

app = Flask(__name__)

# WON2 master server
MASTERS = [
    ("master.won2.steamlessproject.nl", 27010),
    ("master2.won2.steamlessproject.nl", 27010),
    ("master3.won2.steamlessproject.nl", 27010),
    ("master4.won2.steamlessproject.nl", 27010),
]


def query_master(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)

    servers = set()

    # Start from beginning of master list
    start = "0.0.0.0:0"

    try:
        while True:

            # Half-Life / WON master query
            #
            # 31          = master query
            # FF          = region
            # 0.0.0.0:0   = starting address
            # \gamedir\cstrike = CS filter
            #
            packet = (
                b"\x31"
                b"\xff"
                + start.encode("ascii")
                + b"\x00"
                + b"\\gamedir\\cstrike"
                + b"\x00"
            )

            print(
                "TX:",
                packet.hex(" ")
            )

            sock.sendto(
                packet,
                (host, port)
            )

            data, address = sock.recvfrom(8192)

            print(
                "RX:",
                len(data),
                "bytes"
            )

            print(
                data.hex(" ")
            )

            # Master response header
            if not data.startswith(
                b"\xff\xff\xff\xff\x66\x0a"
            ):
                print(
                    "Invalid master response"
                )
                break

            # Skip FF FF FF FF 66 0A
            payload = data[6:]

            if len(payload) < 6:
                break

            previous_start = start
            last_server = None

            # Every server entry is exactly:
            #
            # 4 bytes IP
            # 2 bytes PORT
            #
            # Port is NETWORK ORDER / BIG-ENDIAN
            for offset in range(
                0,
                len(payload) - 5,
                6
            ):

                ip_bytes = payload[
                    offset:offset + 4
                ]

                port_bytes = payload[
                    offset + 4:offset + 6
                ]

                # End-of-list marker
                if ip_bytes == b"\x00\x00\x00\x00":
                    break

                try:
                    ip = socket.inet_ntoa(
                        ip_bytes
                    )
                except Exception:
                    continue

                # IMPORTANT:
                # Master-server ports are network ordered.
                #
                # Example:
                # 69 87 = 27015
                server_port = struct.unpack(
                    ">H",
                    port_bytes
                )[0]

                # Ignore invalid port
                if server_port == 0:
                    break

                server = "{}:{}".format(
                    ip,
                    server_port
                )

                print(
                    "FOUND:",
                    server,
                    "| RAW:",
                    ip_bytes.hex(" "),
                    port_bytes.hex(" ")
                )

                servers.add(server)

                last_server = server

            # No usable server returned
            if last_server is None:
                break

            # Continue from the last server
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
