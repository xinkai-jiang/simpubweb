import io
from flask import Blueprint, Flask, jsonify, request, render_template, send_file
from typing import Dict

from app.scene_renderer import SceneRenderer
from .utils import *
from threading import Thread
from app.simpub_connection import SimPubConnection
from websockets.sync.server import serve

class WebInterface:

    def __init__(self, host="127.0.0.1", web_port=8000, ws_port=8001):
        
        self._conn = SimPubConnection()
        self._renderer = SceneRenderer(self._conn)
        
        self._app = Flask("app", "/app/", )
        self._app.logger.disabled = True

        self._app.route("/")(self.index)
        self._app.route("/devices", methods=["GET"])(self.devices)
        self._app.route("/start-qr-alignment", methods=["POST"])(self.start_qr_alignment)
        self._app.route("/stop-qr-alignment", methods=["POST"])(self.stop_qr_alignment)
        self._app.route("/rename-device", methods=["POST"])(self.rename_device)
        self._app.route("/env-occlusion", methods=["POST"])(self.env_occlusion)
        self._app.route("/asset/<asset>")(self.send_binary_asset)

        self._host = host 
        self._web_port = web_port
        self._ws_port = ws_port

        self._conn.register_on_scene_load(self._renderer.update_scene)
        self._conn.register_on_scene_update(self._renderer.update_state)

    def run(self):
        self._conn.run()
        self._renderer.run(host=self._host, port=self._ws_port)    
        self._app.run(host=self._host, port=self._web_port)


    def index(self):
        """Render the index page."""
        return render_template("index.html")

    def devices(self):
        master_info, nodes_info = self._conn.devices
        return {"status": "success", "master": master_info, "nodes": nodes_info}

    def send_binary_asset(self, asset : str):
        data = self._renderer.on_data_request(asset)
        return send_file(io.BytesIO(data), mimetype='image/png')

    def start_qr_alignment(self):
        """Send QR calibration data to a specific node."""
        node_info: Dict = request.json  # type: ignore
        name = node_info.get("name")
        # Read QR alignment data from the YAML file
        try:
            qr_data = read_qr_alignment_data("QRAlignment.yaml")
        except FileNotFoundError:
            return jsonify({"status": "error", "message": "QRAlignment.yaml file not found"}), 500
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error reading YAML: {str(e)}"}), 500
        # Send the QR data via ZeroMQ
        try:
            response = self._conn.request(f"{name}/StartQRAlignment", qr_data)
            return jsonify({"status": "success", "message": "QR Calibration successful", "response": response})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error during QR Calibration: {str(e)}"}), 500


    def stop_qr_alignment(self):
        """Stop the QR alignment process for a given IP and port."""
        node_info: Dict = request.json  # type: ignore
        name = node_info.get("name")
        
        try:
            response = self._conn.request("{name}/StopQRAlignment")
            return jsonify({"status": "success", "message": "Stopped QR Alignment", "response": response})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error during Stop QR Alignment: {str(e)}"}), 500


    def rename_device(self):
        data = request.get_json()
        new_name = data.get('newName')
        try:
            response =self._conn.request("Rename", new_name)
            return jsonify({"status": "success", "message": "Rename Device", "response": response})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error during rename device: {str(e)}"}), 500


    def env_occlusion(self):
        node_info: Dict = request.json  # type: ignore
        name = node_info.get("name")
        try:
            response = self._conn.request(f"{name}/ToggleOcclusion")
            return {"status": "success", "message": "ToggleOcclusion", "response": response}
        except Exception as e:
            return {"status": "error", "message": f"Error during Toggle Occlusion: {str(e)}"}
        
