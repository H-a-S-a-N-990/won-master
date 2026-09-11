from flask import Flask, Response
import socket
import struct
import os

app = Flask(__name__)

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
    start = "0.0.0.0:0"

    try:
        while True:
            # WON/GoldSrc master query
            packet = (
                b"\x31"
                + b"\xff"
                + start.encode("ascii")
                + b"\x00"
            )

            sock.sendto(packet, (host, port))

            data, addr = sock.recvfrom(8192)

            print(
                "MASTER",
                host,
                "RX",
                len(data),
                "bytes:",
                data.hex(" ")
            )

            if not data.startswith(b"\xff\xff\xff\xff\x66\x0a"):
                print("Unexpected master response")
                break

            payload = data[6:]

            if len(payload) < 6:
                break

            previous_start = start
            last_server = None

            # EXACTLY 6 bytes per server:
            # 4-byte IPv4 + 2-byte big-endian port
            for i in range(0, len(payload) - 5, 6):
                ip_bytes = payload[i:i + 4]
                port_bytes = payload[i + 4:i + 6]

                ip = socket.inet_ntoa(ip_bytes)
                server_port = struct.unpack(">H", port_bytes)[0]

                # End marker
                if ip == "0.0.0.0" and server_port == 0:
                    continue

                address = "{}:{}".format(ip, server_port)

                servers.add(address)
                last_server = address

            if last_server is None:
                break

            start = last_server

            if start == previous_start:
                break

    except Exception as e:
        print(
            "MASTER ERROR {}:{} -> {}".format(
                host, port, repr(e)
            )
        )

    finally:
        sock.close()

    return servers


@app.route("/")
def index():
    all_servers = set()
    errors = []

    for host, port in MASTERS:
        try:
            found = query_master(host, port)
            all_servers.update(found)
        except Exception as e:
            errors.append(
                "{}:{} -> {}".format(host, port, repr(e))
            )

    lines = []

    lines.append("WON2 MASTER SERVER BROWSER")
    lines.append("=" * 40)
    lines.append("")
    lines.append("Servers found: {}".format(len(all_servers)))
    lines.append("")

    for server in sorted(all_servers):
        lines.append(server)

    if errors:
        lines.append("")
        lines.append("=" * 40)
        lines.append("ERRORS")
        lines.append("=" * 40)

        for error in errors:
            lines.append(error)

    return Response(
        "\n".join(lines),
        mimetype="text/plain"
    )


@app.route("/health")
def health():
    return "OK"


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
