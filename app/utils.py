from typing import List, Dict
import enum
import yaml
import zmq
from json import dumps, loads
import socket


class EchoHeader(enum.Enum):
    PING = b'\x00'
    HEARTBEAT = b'\x01'
    NODES = b'\x02'


def split_byte(bytes_msg: bytes) -> List[bytes]:
    return bytes_msg.split(b"|", 1)


def split_byte_to_str(bytes_msg: bytes) -> List[str]:
    return [item.decode() for item in split_byte(bytes_msg)]


def split_str(str_msg: str) -> List[str]:
    return str_msg.split("|", 1)


def read_qr_alignment_data(filepath: str) -> dict:
    """Read QR alignment data from a YAML file."""
    with open(filepath, 'r') as file:
        return yaml.safe_load(file)


def scan_network(ip: str) -> tuple[Dict, Dict]:
    _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    _socket.bind((ip, 0))
    _socket.settimeout(1)
    try:
        _socket.sendto(EchoHeader.NODES.value, ("127.0.0.1", 7720))
        data, _ = _socket.recvfrom(4096)
    except socket.timeout:
        print("No more messages...")
    finally:
        _socket.close()
    master_info, nodes_info = split_byte_to_str(data)
    return loads(master_info), loads(nodes_info)


def send_zmq_request(
    ip: str, port: int, service_name: str, request: Dict, timeout: int = 1000
) -> str:
    """
    Send a ZMQ request to the given IP and port with a specified timeout.
    
    :param ip: Target IP address.
    :param port: Target port number.
    :param service_name: The name of the service to identify the request.
    :param request: The request payload as a dictionary.
    :param timeout: Timeout in milliseconds for send and receive operations (default: 5000ms).
    :return: Response string from the server.
    :raises zmq.ZMQError: If a timeout occurs or there is a ZMQ-related error.
    """
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    try:
        socket.connect(f"tcp://{ip}:{port}")
        
        # Set timeout options
        socket.setsockopt(zmq.RCVTIMEO, timeout)  # Receive timeout
        socket.setsockopt(zmq.SNDTIMEO, timeout)  # Send timeout
        
        # Send the request
        socket.send_string("".join([service_name, "|", dumps(request)]))
        
        # Receive the response
        response = socket.recv_string()
        return response
    except zmq.ZMQError as e:
        raise zmq.ZMQError
    except Exception as e:
        raise e
    finally:
        socket.close()