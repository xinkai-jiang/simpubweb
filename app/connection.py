from dataclasses import asdict, dataclass, field
import ipaddress
import socket
from enum import Enum
import threading
import time
from typing import Callable, Optional, Union
import uuid
from utils import split_byte_to_str
import json
import zmq
import netifaces

from simpub.simdata import *

            
class EchoHeader(Enum):
    PING = b'\x00'
    HEARTBEAT = b'\x01'
    NODES = b'\x02'

class MessageReturnTypes(Enum):
    EMPTY = "EMPTY"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    NOSERVICE = "NOSERVICE"
    TIMEOUT = "TIMEOUT"


@dataclass 
class NodeAdress:
    ip : str
    port : int


@dataclass 
class NodeInfo:
    name : str
    nodeID : str
    addr : NodeAdress
    type : str
    servicePort : int
    topicPort : int
    serviceList : list[str] = field(default_factory=list)
    topicList : list[str] = field(default_factory=list)

    def to_str(self):
        return json.dumps(asdict(self))
    
    def to_bytes(self):
        return self.to_str().encode()
    
    @classmethod
    def from_string(cls, data : str):
        info =  cls(**json.loads(data))
        info.addr = NodeAdress(info.addr['ip'], info.addr['port'])
        return info

class ZMQSocketConnection:

    ctx : Optional[zmq.Context]= None
    SOCKETS = list()

    def __init__(self, type : zmq.SocketType):
        if ZMQSocketConnection.ctx == None:
            ZMQSocketConnection.ctx = zmq.Context()

        self._socket : zmq.Socket = ZMQSocketConnection.ctx.socket(type)
        ZMQSocketConnection.SOCKETS.append(self)
        self._connection = None
        self._send_lock = threading.Lock()

    def connect(self, ip : str, port : int = 0):
        self._connection = f"tcp://{ip}:{port}"
        self._socket.connect(self._connection)

    def get_port(self):
        endpoint: bytes = self._socket.getsockopt(zmq.LAST_ENDPOINT)  # type: ignore
        return int(endpoint.decode().split(":")[-1])
    
    def disconnect(self):
        self._socket.disconnect(self._connection)
        self._connection = None

    def bind(self, ip : str, port : int = 0):
        self._socket.bind(f"tcp://{ip}:{port}")

    def unbind(self):
        self._socket.unbind(self._connection)
        self._connection = None

    def subscribe(self, topic : str):
        self._socket.subscribe(topic)

    def send(self, message : str):
        print(message)
        with self._send_lock:
            self._socket.send_string(message)

    def has_message(self):
        return self._socket.poll(0, zmq.POLLIN)

    def recv(self, timeout : float = None) -> str:  
        if not timeout: 
            return self._socket.recv_string()
            
        if self._socket.poll(timeout * 1000, zmq.POLLIN):
            return self._socket.recv_string()
        else:
            return None

    def update(self):
        pass
    
    def empty_socket(self):
        while self.has_message():
            self._socket.recv()
    
    @classmethod
    def update_all(self):
        for socket in ZMQSocketConnection.SOCKETS:
            socket.update()

    def __del__(self):
        ZMQSocketConnection.SOCKETS.remove(self)
        self.disconnect()
        self._socket.close()

        if ZMQSocketConnection.ctx != None:
            del ZMQSocketConnection.ctx 
            ZMQSocketConnection.ctx = None
        


class ZMQRequestConnection(ZMQSocketConnection):

    def __init__(self):
        super().__init__(zmq.REQ)

    def request(self, service : str, request : Optional[Union[str, dict]]):
        if isinstance(request, dict):
            request = json.dumps(request)
        
        self.send(f"{service}|{request}")
        response = self.recv()

        if response == 'NOSERVICE':
            raise Exception("Service not found on the node.")
        
        return response
    
class ZMQReplyConnection(ZMQSocketConnection):
    def __init__(self):
        super().__init__(zmq.REP)
        self._callbacks = dict()

    def register(self, service : str, callback):
        self._callbacks[service] = callback

    def update(self):
        if self.has_message():
            message = self.recv()
            service, request = message.split('|')
            if service not in self._callbacks:
                self.send(MessageReturnTypes.NOSERVICE.value)
                return
            response = self._callbacks[service](request)
            self.send(response)

class ZMQPubConnection(ZMQSocketConnection):
    def __init__(self):
        super().__init__(zmq.PUB)

    def publish(self, topic : str, message : str):
        self.send(f"{topic}|{message}")

class ZMQSubConnection(ZMQSocketConnection):
    def __init__(self, topic : str = ""):
        super().__init__(zmq.SUB)
        self._topic = topic
        self._on_message = list()
    
    def set_topic(self, topic : str):
        self._topic = topic

    def register(self, fn : Callable[[str], None]):
        self._on_message.append(fn)

    def connect(self, ip, port):
        super().connect(ip, port)
        self.subscribe(self._topic)

    def update(self):
        message = None
        while self.has_message():
            message = self.recv()

        if not message: return 

        topic, message = message.split('|')
        if topic != self._topic: return 

        
        for fn in self._on_message:
            fn(message)

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
        data,_ = self._socket.recvfrom(4096)
    
        master_info, nodes_info = split_byte_to_str(data)
        master_info['type'] = 'master'
        return json.loads(master_info), json.loads(nodes_info)
    
    def heartbeat(self, master_info : NodeInfo, local_info : NodeInfo, timeout : int) -> bool:

        hb_message = EchoHeader.HEARTBEAT.value + local_info.to_bytes()
        self._socket.sendto(hb_message, (master_info.addr.ip, UDPConnection.SERVER_PORT))
      
        data, _ = self.recv(timeout)

        if data is None:
            return False

        return NodeInfo.from_string(data).nodeID == master_info.nodeID
         


    def search_master_node(self) -> Optional[NodeInfo]:
        self._socket.sendto(EchoHeader.PING.value, ("255.255.255.255", UDPConnection.SERVER_PORT))
        data, sender = self.recv(0.5)
        if data is None or "|" not in data:
            return None
        
        data, _ = data.split("|")
        return NodeInfo.from_string(data)
    
class SimPubConnection:

    def __init__(self, addr = "127.0.0.1"):
        
        self._udp = UDPConnection()

        self._pubSocket = ZMQPubConnection()
        self._repSocket = ZMQReplyConnection()
        self._subSocket = ZMQSubConnection()
        self._reqSocket = ZMQRequestConnection()


        self._repSocket.bind(addr)
        self._pubSocket.bind(addr)

        self._local_info = NodeInfo(
            name = "WebInterface",
            nodeID = uuid.uuid4().hex,
            addr = NodeAdress(ip = addr, port = UDPConnection.SERVER_PORT),
            type = "WebInterface",
            servicePort = self._repSocket.get_port(),
            topicPort = self._pubSocket.get_port(),
        )

        self._serviceCallbacks = dict()
        self._topicCallbacks = dict()

        self._cancelationTokenSource = None
        self._connected = False
        self._running = True

        self.register_service("LoadSimScene", self.on_scene_load)

    def on_scene_load(self, scene : str):
        
        self._scene = SimScene.from_string(scene)
        return MessageReturnTypes.SUCCESS.value
    
    def register_service(self, service : str, callback : Callable[[str], str]):
        self._serviceCallbacks[service] = callback
        self._repSocket.register(service, callback)
        self._local_info.serviceList.append(service)
    
    @property
    def devices(self):
        return self._udp.scan_network()    
            
    def loop(self, hb_timeout = 0.5, hb_interval = 0.2):
        while self._running:
            master_node = self._find_master_node() # this will block for 0.5s if no master node is found
            if master_node is None: continue

            self._start_connection(master_info=master_node)
            heartbeat = self._udp.heartbeat(master_node, self._local_info, hb_timeout)
            last_heartbeat = time.time()
            while heartbeat and self._running:
                
                ZMQSocketConnection.update_all()

                if time.time() - last_heartbeat > hb_interval:
                    heartbeat = self._udp.heartbeat(master_node, self._local_info, hb_timeout)
                    last_heartbeat = time.time()

            self._stop_connection()

    def _start_connection(self, master_info : NodeInfo):
        if self._connected:
            self._stop_connection()
        
        print("Connected")

        self._reqSocket.connect(master_info.addr.ip, master_info.servicePort)
        self._subSocket.connect(master_info.addr.ip, master_info.topicPort)
        self._subSocket.subscribe("")


    def _stop_connection(self):
        
        self._subSocket.empty_socket()

        if not self._connected:
            return 
        
        self._reqSocket.disconnect()
        self._subSocket.disconnect()

        self._connected = False

        print("Disconnected")


    def _find_master_node(self):
        master_node = self._udp.search_master_node()
        if not master_node: return None

        local_ip = self._get_local_ip_in_same_subnet(master_node.addr.ip)
        if local_ip is None: return None 

        self._local_info.addr = NodeAdress(ip = local_ip, port = UDPConnection.SERVER_PORT)

        return master_node

    def _get_local_ip_in_same_subnet(self, input_ip_address: str) -> str:

        try:
            input_ip_address = ipaddress.IPv4Address(input_ip_address)
        except ValueError:
            raise ValueError("Invalid IP address format.")

        subnet_mask = ipaddress.IPv4Address("255.255.255.0")

        # Get all network interfaces
        for interface in netifaces.interfaces():
            # Get addresses for this interface
            addrs = netifaces.ifaddresses(interface)
            # Check IPv4 addresses (AF_INET is for IPv4)
            if netifaces.AF_INET not in addrs: continue
            
            for addr_info in addrs[netifaces.AF_INET]:
                local_ip = addr_info['addr']
                    
                mask_int = int(subnet_mask)
                input_int = int(input_ip_address)
                local_int = int(ipaddress.IPv4Address(local_ip))

                if not (input_int & mask_int) == (local_int & mask_int): continue
                return local_ip 
        
        return None
    
if __name__ == "__main__":
    sim = SimPubConnection()
    sim.loop()
