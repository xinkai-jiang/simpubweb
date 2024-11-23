from flask import Blueprint, jsonify, render_template
import socket
import zmq
import json


main = Blueprint("main", __name__)


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/scan", methods=["GET"])
def scan_network():
    _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _socket.bind(("0.0.0.0", 7720))
    _socket.settimeout(5)
    print("Listening on 0.0.0.0:7720 for broadcast messages...")
    while True:
        try:
            # 接收数据
            data, addr = _socket.recvfrom(4096)  # 接收最多 4096 字节
            print(f"Received message from {addr}")
            break
        except socket.timeout:
            print(f"No messages received within 5 seconds. Continuing to listen...")
        except KeyboardInterrupt:
            print("Stopping listener...")
            break
        except Exception as e:
            print(f"Error: {e}")
    server_info = json.loads(data.decode().split(":", 2)[2])
    zmq_context = zmq.Context()
    zmq_socket = zmq_context.socket(zmq.REQ)
    ip_addr = server_info["ip"]
    service_port = server_info["servicePort"]
    zmq_socket.connect(f"tcp://{ip_addr}:{service_port}")
    zmq_socket.send_string("GetClientInfo:")
    client_into = zmq_socket.recv()
    client_into = json.loads(client_into.decode())
    msg_dict = {"server": server_info, "clients": client_into}
    print(f"Server info: {msg_dict}")
    return jsonify(msg_dict)
