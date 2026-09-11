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


def get_master_servers(master_host, master_port):
    servers = []
    seen = set()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)

    try:
        last_ip = "0.0.0.0"
        last_port = 0

        while True:
            # Master server query
            packet = (
                b"\x31"
                + b"\xff"
                + socket.inet_aton(last_ip)
                + struct.pack(">H", last_port)
                + b"\x00"
            )

            sock.sendto(packet, (master_host, master_port))

            data, addr = sock.recvfrom(65535)

            # Master response header
            if not data.startswith(b"\xff\xff\xff\xff\x66\x0a"):
                break

            payload = data[6:]

            if len(payload) < 6:
                break

            old_last = (last_ip, last_port)

            for i in range(0, len(payload) - 5, 6):
                ip = socket.inet_ntoa(payload[i:i + 4])
                port = struct.unpack(">H", payload[i + 4:i + 6])[0]

                address = "%s:%d" % (ip, port)

                if address not in seen:
                    seen.add(address)
                    servers.append(address)

                last_ip = ip
                last_port = port

            # End of master list
            if (last_ip, last_port) == old_last:
                break

    except socket.timeout:
        pass

    except Exception as e:
        print("Master error:", master_host, e)

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
