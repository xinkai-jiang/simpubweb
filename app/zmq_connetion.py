from collections import defaultdict
from enum import Enum
import json
import threading
from typing import Callable, Optional, Union
import zmq


class MessageReturnTypes(Enum):
    EMPTY = "EMPTY"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    NOSERVICE = "NOSERVICE"
    TIMEOUT = "TIMEOUT"


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
        with self._send_lock:
            self._socket.send_string(message)

    def has_message(self):
        return self._socket.poll(0, zmq.POLLIN)

    def recv(self, type : type = str, timeout : float = None) -> str | bytes:  
        if not timeout: 
            if type == str:
                return self._socket.recv_string()
            else:
                return self._socket.recv()
            
        if self._socket.poll(int(timeout * 1000), zmq.POLLIN):
            if type == str:
                return self._socket.recv_string()
            else:
                return self._socket.recv()
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

    def request(self, service : str, request : Optional[Union[str, dict]], type : type = str) -> Optional[Union[str, bytes]]:
        if isinstance(request, dict):
            request = json.dumps(request)
        
        self.send(f"{service}|{request}")

        response = self.recv(type)
        
        if response == b'NOSERVICE':
            raise Exception("Service not found on the node.")
        if response == b'TIMEOUT':
            raise Exception("Request timed out.")
        
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
        self._on_message = defaultdict(list)

    def set_topic(self, topic : str):
        self._topic = topic

    def register(self, topic : str, fn : Callable[[str], None]):
        self._on_message[topic].append(fn)

    def connect(self, ip, port):
        super().connect(ip, port)
        self.subscribe("")

    def update(self):
        message = self.recv()
        while self.has_message():
            message = self.recv()
        

        if message is None: return 

        topic, message = message.split('|')

        message = json.loads(message) if message else None

        if topic not in self._on_message: return

        for fn in self._on_message[topic]:
            fn(message)
    