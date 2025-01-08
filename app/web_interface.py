from flask import Blueprint, Flask, jsonify, request, render_template
from typing import Dict
from .utils import *
from threading import Thread
from app.simpub_connection import SimPubConnection

class WebInterface:

    def __init__(self):
        
        self._conn = SimPubConnection()
        
        self.app = Flask("app", "/app/")

        self.app.route("/")(self.index)
        self.app.route("/devices", methods=["GET"])(self.devices)
        self.app.route("/scene_id", methods=["GET"])(self.scene_id)
        self.app.route("/scene", methods=["GET"])(self.scene)
        self.app.route("/scene_state", methods=["GET"])(self.scene_state)
        self.app.route("/start-qr-alignment", methods=["POST"])(self.start_qr_alignment)
        self.app.route("/stop-qr-alignment", methods=["POST"])(self.stop_qr_alignment)
        self.app.route("/rename-device", methods=["POST"])(self.rename_device)
        self.app.route("/env-occlusion", methods=["POST"])(self.env_occlusion)

    def run(self, port = 8000):
        Thread(target=self._conn.loop).start() # start connection
        self.app.run(port=port)


    def index(self):
        """Render the index page."""
        return render_template("index.html")

    def devices(self):
        master_info, nodes_info = self._conn.devices
        return {"status": "success", "master": master_info, "nodes": nodes_info}
    

    def scene_id(self):
        return self._conn.scene_id

    def scene(self):
        return self._conn.scene.to_string()

    def scene_state(self):
        return self._conn.scene_state

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
        
