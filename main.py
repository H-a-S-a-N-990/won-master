from flask import Flask, Response
import socket
import struct

app = Flask(__name__)

WON2_MASTERS = [
    ("master.won2.steamlessproject.nl", 27010),
    ("master2.won2.steamlessproject.nl", 27010),
    ("master3.won2.steamlessproject.nl", 27010),
    ("master4.won2.steamlessproject.nl", 27010),
]


def query_master(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)

    servers = set()
    start = b"0.0.0.0:0"

    try:
        while True:
            packet = (
                b"\x31"          # master query
                + b"\xff"        # world
                + start          # ASCII IP:port
                + b"\x00"        # end of address
            )

            sock.sendto(packet, (host, port))

            data, addr = sock.recvfrom(8192)

            # Master response:
            # FF FF FF FF 66 0A
            if not data.startswith(b"\xff\xff\xff\xff\x66\x0a"):
                print("Bad master response:", data.hex(" "))
                break

            payload = data[6:]

            # Every server is:
            # 4 bytes IP + 2 bytes PORT
            if len(payload) < 6:
                break

            old_start = start

            for i in range(0, len(payload) - 5, 6):
                ip = socket.inet_ntoa(payload[i:i + 4])
                server_port = struct.unpack(">H", payload[i + 4:i + 6])[0]

                # Ignore invalid terminator
                if ip == "0.0.0.0" and server_port == 0:
                    continue

                servers.add(f"{ip}:{server_port}")

                # Continue from the last returned server
                start = (
                    ip.encode("ascii")
                    + b":"
                    + str(server_port).encode("ascii")
                )

            if start == old_start:
                break

    except socket.timeout:
        print(host, "timed out")

    finally:
        sock.close()

    return servers


@app.route("/masters")
def masters():
    all_servers = []
    seen = set()

    for host, port in WON2_MASTERS:
        servers = get_master_servers(host, port)

        for server in servers:
            if server not in seen:
                seen.add(server)
                all_servers.append(server)

    # RAW TEXT
    output = "\n".join(all_servers)

    return Response(
        output,
        mimetype="text/plain"
    )


@app.route("/")
def index():
    return """
    <h1>WON2 Master Servers</h1>
    <p><a href="/masters">Show raw IP:PORT list</a></p>
    """


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
