
from enum import Enum
import json
import socket
from typing import Optional
from dataclasses import asdict, dataclass, field

from app.utils import split_byte_to_str

class EchoHeader(Enum):
    PING = b'\x00'
    HEARTBEAT = b'\x01'
    NODES = b'\x02'


@dataclass 
class NodeAdress:
    ip : str
    port : int


@dataclass 
class NodeInfo:
    name : str
    serviceList : list[str] = field(default_factory=list)
    topicList : list[str] = field(default_factory=list)
    nodeID : str = None
    addr : NodeAdress = None
    type : str = None
    servicePort : int = None
    topicPort : int = None

    def to_str(self):
        return json.dumps(asdict(self))
    
    def to_bytes(self):
        return self.to_str().encode()
    @classmethod
    def from_dict(cls, dict):
        info =  cls(**dict)
        info.addr = NodeAdress(info.addr['ip'], info.addr['port'])
        return info
    
    @classmethod
    def from_string(cls, data : str):
      info =  cls.from_dict(json.loads(data))
      return info  

class UDPConnection:

    SERVER_PORT = 7720

    def __init__(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.bind(("", 0))
        self._socket.settimeout(1)
       
    def __del__(self):
        self._socket.close()

    def recv(self, timeout : int = None):

        if not timeout:
            self._socket.settimeout(None)
            return self._socket.recvfrom(4096)
        
        self._socket.settimeout(timeout)
        try:
            msg, conn =  self._socket.recvfrom(4096)
            return msg.decode(), conn
        except TimeoutError as e:
            return None, None


    def scan_network(self) -> tuple[NodeInfo, list[NodeInfo]]:
        
        self._socket.sendto(EchoHeader.NODES.value, ("255.255.255.255", UDPConnection.SERVER_PORT))
        try:
            data,_ = self._socket.recvfrom(4096)
        except TimeoutError:
            return None, None
        
        master_info, nodes_info = split_byte_to_str(data)
        master_info, nodes_info = json.loads(master_info), json.loads(nodes_info)
        master_info['type'] = 'master'
        return NodeInfo.from_dict(master_info), ([NodeInfo.from_dict(i) for i in nodes_info.values()])
        
    
    def heartbeat(self, master_info : NodeInfo, local_info : NodeInfo, timeout : int) -> bool:

        hb_message = EchoHeader.HEARTBEAT.value + local_info.to_bytes()
        self._socket.sendto(hb_message, (master_info.addr.ip, UDPConnection.SERVER_PORT))
      
        data, _ = self.recv(timeout)

        if data is None:
            return False
        
        if "|" in data: data, conn = data.split("|", 1)
        
        return NodeInfo.from_string(data).nodeID == master_info.nodeID
        


    def search_master_node(self) -> Optional[NodeInfo]:
        self._socket.sendto(EchoHeader.PING.value, ("255.255.255.255", UDPConnection.SERVER_PORT))
        data, sender = self.recv(0.5)
        if data is None or "|" not in data:
            return None
        
        data, _ = data.split("|")
        return NodeInfo.from_string(data)
