import ipaddress
import socket
from enum import Enum
import threading
import time
from typing import Callable, Optional, Union
import uuid
import json
import zmq
import netifaces

from simpub.simdata import *

from app.udp_connection import NodeAdress, NodeInfo, UDPConnection
from app.zmq_connetion import MessageReturnTypes, ZMQPubConnection, ZMQReplyConnection, ZMQRequestConnection, ZMQSocketConnection, ZMQSubConnection


class SimPubConnection:

    INSTANCE = None

    def __init__(self, addr = "127.0.0.1"):
        if SimPubConnection.INSTANCE is not None:
            raise Exception("Only one instance of SimPubConnection is allowed")

        SimPubConnection.INSTANCE = self

        
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

        self._scene = None
        self._scene_state = dict()

        self.register_service("LoadSimScene", self.on_scene_load)
        self.subscribe_topic("SceneUpdate", self.on_scene_update)

        self._scene_load_hook = list()
        self._scene_state_hook = list()

    def register_on_scene_load(self, callback : Callable[[SimScene], None]):    
        self._scene_load_hook.append(callback)
    
    def register_on_scene_update(self, callback : Callable[[dict], None]):
        self._scene_state_hook.append(callback)

    def run(self):
        threading.Thread(target=self.loop).start()

    def on_scene_load(self, scene : str):
        self._scene = SimScene.from_string(scene)
        for hook in self._scene_load_hook:
            hook(self._scene)
        return MessageReturnTypes.SUCCESS.value
    
    def on_scene_update(self, update : str):
        for hook in self._scene_state_hook:
            hook(update)
        self._scene_state = update
    
    def register_service(self, service : str, callback : Callable[[str], str]):
        self._serviceCallbacks[service] = callback
        self._repSocket.register(service, callback)
        self._local_info.serviceList.append(service)

    def subscribe_topic(self, topic : str, callback : Callable[[str], None]):
        self._topicCallbacks[topic] = callback
        self._subSocket.register(topic, callback)
    
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

    def request(self, service : str, request : Optional[Union[str, dict]], type : type = str) -> Optional[Union[str, bytes]]:
        return self._reqSocket.request(service, request, type=type)

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
    