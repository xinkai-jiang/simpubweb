import socket
from enum import Enum
from typing import Optional, Union
from utils import split_byte_to_str
import json
import zmq

            
class EchoHeader(Enum):
    PING = b'\x00'
    HEARTBEAT = b'\x01'
    NODES = b'\x02'

class ZMQSocketConnection:

    ctx : Optional[zmq.Context]= None

    def __init__(self, type : zmq.SocketType, ip : str = None, port : int = None):
        if ZMQConnection.ctx == None:
            ZMQConnection.ctx = zmq.Context()

        self._socket : zmq.Socket = ZMQSocketConnection.ctx.socket(type)
        self._socket.connect(f"tcp://{ip}:{port}")

    def send(self, message : str):
        self._socket.send_string(message)

    def recv(self) -> str:
        return self._socket.recv_string()

    def __del__(self):
        if ZMQConnection.ctx != None:
            del ZMQConnection.ctx 
            ZMQConnection.ctx = None


class ZMQRequestConnection(ZMQSocketConnection):

    def __init__(self, ip : str, port : int):
        super().__init__(zmq.REQ, ip, port)


    def request(self, service : str, request : Optional[Union[str, dict]]):
        if isinstance(request, dict):
            request = json.dumps(request)
        
        self.send(f"{service}|{request}")
        response = self.recv()

        if response == 'NOSERVICE':
            raise Exception("Service not found on the node.")
        
        return response
    

class UDPConnection:
    
    PORT = 7720

    def __init__(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.bind(("", 0))
        self._socket.settimeout(1)
       
    def __del__(self):
        self._socket.close()

    def scan_network(self):
        
        self._socket.sendto(EchoHeader.NODES.value, ("255.255.255.255", UDPConnection.PORT))
        data,_ = self._socket.recvfrom(4096)
    
        master_info, nodes_info = split_byte_to_str(data)
        master_info['type'] = 'master'
        return json.loads(master_info), json.loads(nodes_info)

class ZMQConnection:
    def __init__(self):
        self._socket = 

class SimPubConnection:

    def __init__(self):
        
        self._udp = UDPConnection()


    def scan_network(self):
        return self._udp.scan_network()    
