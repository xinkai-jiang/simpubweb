import socket
from flask import Blueprint, jsonify, render_template
import asyncio
import time

main = Blueprint("main", __name__)

@main.route("/")
def index():
    return render_template("index.html")

async def scan_socket_broadcast(ip: str, port: int = 7720):
    print(f"Scanning IP: {ip}, {time.time()}")
    try:
        _, writer = await asyncio.open_connection(ip, port)
        writer.close()  # 关闭连接
        await writer.wait_closed()
        return {"ip": ip, "status": "success", "message": "Connected successfully!"}
    except Exception:
        print(f"Scanned IP: {ip}, {time.time()}")
        return {"ip": ip, "status": "error", "message": "Failed to connect"}


@main.route("/scan", methods=["GET"])
def scan_network():
    """
    扫描本地网络中的所有 IP 地址和指定端口。
    """
    # 获取本地所有 IP 地址
    hostname = socket.gethostname()
    local_ips = socket.gethostbyname_ex(hostname)[2]
    if "127.0.0.1" not in local_ips:
        local_ips.append("127.0.0.1")  # 确保 127.0.0.1 包含在扫描列表中
    local_ips.append("192.168.26.44")
    # 执行异步扫描
    async def scan_all_ips(ips):
        tasks = [scan_socket_broadcast(ip) for ip in ips]
        return await asyncio.gather(*tasks)

    scan_results = asyncio.run(scan_all_ips(local_ips))
    return jsonify(scan_results)

# def scan_local_network(port=7720):
#     """
#     扫描本地网络的指定端口，尝试连接，返回扫描结果。
#     """
#     results = []

#     # 获取本地所有 IP 地址，并手动添加 127.0.0.1
#     hostname = socket.gethostname()
#     local_ips = socket.gethostbyname_ex(hostname)[2]  # 获取所有本地 IP 地址
#     if "127.0.0.1" not in local_ips:
#         local_ips.append("127.0.0.1")  # 确保 127.0.0.1 在列表中

#     # 打印调试信息
#     print(f"Scanning IPs: {local_ips}")

#     # 尝试连接每个 IP 的指定端口
#     for ip in local_ips:
#         print(f"Scanning IP: {ip}, {time.time()}")
#         try:
#             with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#                 s.settimeout(5)  # 设置超时时间为 1 秒
#                 s.connect((ip, port))
#                 results.append({"ip": ip, "status": "success", "message": "Connected successfully!"})
#         except Exception as e:
#             results.append({"ip": ip, "status": "error", "message": "Failed to connect"})
#         print(f"Scanned IP: {ip}, {time.time()}")
#     return results

# @main.route("/scan", methods=["GET"])
# def scan_network():
#     """
#     路由：扫描网络并返回扫描结果。
#     """
#     scan_results = scan_local_network()
#     return jsonify(scan_results)
