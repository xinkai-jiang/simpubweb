from dataclasses import dataclass, field, is_dataclass
from enum import Enum
from hashlib import md5
from io import BytesIO
from queue import Queue as queue
from threading import Thread
import time
from typing import Optional
from uuid import uuid4
import numpy as np
from simpub.simdata import *
from scipy.spatial.transform import Rotation as R

from websockets.sync.server import serve, ServerConnection

from app.simpub_connection import SimPubConnection
from tqdm import tqdm

class JsonEncoder(json.JSONEncoder):
  def default(self, obj):
      if isinstance(obj, np.ndarray):
        return obj.tolist()
      elif isinstance(obj, np.generic):
        return obj.item()
      elif is_dataclass(obj):
        return asdict(obj)
      return super().default(obj)


class WebSocketConnection:

  def __init__(self, ws):
    self.ws : ServerConnection = ws

  def send(self, topic, message = ""):
    if not isinstance(message, str):
      message = json.dumps(message, cls=JsonEncoder)
    self.ws.send(topic + ":" + message)

  def recv(self):
    return self.ws.recv()


@dataclass
class Transform:
  position: np.ndarray = field(default_factory=lambda: np.array([0, 0, 0]))
  quaternion: np.ndarray = field(default_factory=lambda: np.array([0, 0, 0, 1]))
  scale : np.ndarray = field(default_factory=lambda: np.array([1, 1, 1]))

  def __post_init__(self):
    self.position = np.array(self.position)
    self.quaternion = np.array(self.quaternion)
    self.scale = np.array(self.scale)

  @classmethod
  def from_sim(cls, sim_transform : SimTransform, type : VisualType = None):

    
    position = np.array(sim_transform.pos)
    quaternion = np.array(sim_transform.rot)
    scale = np.array(sim_transform.scale)

    quaternion = np.array([-quaternion[0], -quaternion[1], quaternion[2], quaternion[3]])
    position[2] *= -1

    if type == VisualType.CYLINDER:
      scale = np.array([0.5 * scale[0], 2 * scale[1], 0.5 * scale[2]])

    return cls(
      position=position,
      quaternion=quaternion,
      scale=scale
    )
    

class RenderPrimitiveType(str, Enum):
  CUBE = "CUBE"
  SPHERE = "SPHERE"
  CAPSULE = "CAPSULE"
  CYLINDER = "CYLINDER"
  PLANE = "PLANE"
  QUAD = "QUAD"
  MESH = "MESH"
  NONE = "NONE"

  @classmethod
  def from_sim(cls, type):
  
    if type == "CUBE": return cls.CUBE
    if type == "SPHERE": return cls.SPHERE
    if type == "CAPSULE": return cls.CAPSULE
    if type == "CYLINDER": return cls.CYLINDER
    if type == "PLANE": return cls.PLANE
    if type == "QUAD": return cls.QUAD
    if type == "MESH": return cls.MESH

    return cls.NONE

@dataclass(frozen=True)
class WebMesh:
  name : str
  hash : str = None
  vertex_layout : tuple = None
  normal_layout : tuple = None
  index_layout : tuple = None
  uv_layout : tuple = None

@dataclass(frozen=True)
class WebMaterial:
  name : str
  color: list[float]
  emission: float = 0.5
  specular: float = 0.5
  shininess: float = 0.5
  reflectance: float = 0.0
  texture: Optional[str] = None

@dataclass(frozen=True)
class WebTexture:
  name : str
  hash : str
  width : int = 0
  height : int = 0
  repeat : tuple = field(default_factory=lambda: (1, 1))
  textureType : str = "2D"

@dataclass(frozen=True)
class WebVisual:
  type : str
  mesh : str
  material : str
  transform : Transform

@dataclass
class WebObject:
  name : str
  parent : str
  transform : Transform
  global_transform : Transform = field(default_factory=Transform)
  visuals : list[WebVisual] = field(default_factory=list)
  _dirty = False
  
  def apply_global_transform(self, transform : Transform):

    rot = R.from_quat(transform.quaternion)

    self.global_transform.position = transform.position + rot.apply(self.transform.position)
    self.global_transform.quaternion = (rot * R.from_quat(self.transform.quaternion)).as_quat()

class SceneRenderer:


  def __init__(self, simpub : SimPubConnection):

    self.assets = dict()
    self.simpub = simpub
    self.meshes = dict()
    self.textures = dict()
    self.materials = dict()

    self.object_list : list[WebObject]= list()
    self.objects : dict[str, WebObject] = dict()

    self.clients : list[WebSocketConnection] = list()

    self.last_update = 0

    self._new_scenes : queue[SimScene] = queue()

  def run(self, host : str, port : int):
    Thread(target=self.ws_loop, args=[host, port]).start()
    Thread(target=self.update).start()

  def ws_loop(self, host : str, port : int):
    with serve(self.ws_on_connection, host, port) as server:
        server.serve_forever()

  def ws_on_connection(self, websocket):
      websocket = WebSocketConnection(websocket)
      self.clients.append(websocket)
      try:
          self.render_scene(websocket)
          while True:
              message = websocket.recv()
              if message is None:
                  break
      except Exception as e:
        ...
      finally:
        self.clients.remove(websocket)


  def update_state(self, new_state):
    time = new_state["time"]
    state = new_state["updateData"]
    

    for obj in self.object_list:
      
      global_pos = np.zeros(3)
      global_rot = R.from_euler("xyz", np.zeros(3))

      if parent := self.objects.get(obj.parent):
        global_pos = parent.global_transform.position
        global_rot = R.from_quat(parent.global_transform.quaternion)
      
      global_rot = global_rot.inv()

      transform = Transform.from_sim(SimTransform(pos=state[obj.name][:3], rot=state[obj.name][3:]))
      pos = transform.position
      rot = transform.quaternion

      obj.global_transform.position = pos
      obj.global_transform.quaternion = rot

      obj.transform.position = global_rot.apply(np.array(pos) - np.array(global_pos))
      obj.transform.quaternion = (global_rot * R.from_quat(rot)).as_quat()

    
  def get_asset(self, asset):
    return self.assets[asset]

  def update_scene(self, scene : SimScene):
    self._new_scenes.put(scene)

  def _update_scene(self, scene : SimScene):

    scene_objects = scene.get_objects()

    visuals = [visual for obj in scene_objects for visual in obj.visuals]

    self.tracked_objs = list()

    sim_meshes : list[SimMesh] = [visual.mesh for visual in visuals if visual.mesh]
    sim_materials : list[SimMaterial] = [visual.material for visual in visuals if visual.material]
    sim_textures : list[SimTexture] = [material.texture for material in sim_materials if material.texture]

    self.meshes.clear()
    self.materials.clear()
    self.textures.clear()

    mesh2name = dict()
    mat2name = dict()
    tex2name = dict()

    try:
      for mesh in sim_meshes:
        name = self.create_mesh(mesh)
        mesh2name[mesh] = name

      for tex in sim_textures:
        name = self.create_texture(tex)
        tex2name[tex] = name

      for mat in sim_materials:
        name = self.create_material(mat, tex2name=tex2name)
        mat2name[mat] = name

 

    except BufferError as e:
      print(e)
      return

    self.object_list.clear()
    self.objects.clear()

    objs : list[tuple[str, SimObject]]= [(None, scene.root)]
    while len(objs) > 0:
      parent_name, obj = objs.pop(0)

      self.create_object(obj.name, obj.trans, parent_name)

      for visual in obj.visuals:
        if visual.type == VisualType.MESH:
          self.attach_mesh(
            obj_name=obj.name,
            mesh=mesh2name[visual.mesh], 
            material=mat2name[visual.material], 
            transform=visual.trans
          )
        else:
          self.attach_primitive(
            obj_name=obj.name, 
            type=visual.type, 
            material=mat2name[visual.material],
            transform=visual.trans, 
          )

      objs.extend((obj.name, child) for child in obj.children)

    # update all clients
    for client in self.clients:
      self.render_scene(client)
      
  def update(self, frame_rate = 30):
    while True:
      if self._new_scenes.qsize() > 0:
        self._update_scene(self._new_scenes.get())

      current = time.time() 
      if (current - self.last_update) < 1 / frame_rate: 
        time.sleep(1 / frame_rate - (current - self.last_update))

      self.last_update = time.time()

      updates = dict()
      self.loaded = True
      for obj in self.object_list:
        if obj._dirty:
          updates[obj.name] = obj.transform
          obj._dirty = False

      if len(updates) == 0: continue

      for client in list(self.clients):
        client.send("UPDATE_TRANSFORM", updates)

  def render_scene(self, client : ServerConnection):

    while not self.loaded: time.sleep(0.1)

    client.send("RESET")

    for obj in self.object_list:
      client.send("CREATE_OBJECT", obj)

    for mat in self.materials.values():
      client.send("LOAD_MATERIAL", mat)

    for mesh in self.meshes.values():
      client.send("LOAD_MESH", mesh)

    for tex in self.textures.values():
      client.send("LOAD_TEXTURE", tex)

    client.send("LOAD_COMPLETE")

    

  def on_data_request(self, data_id : str):
    if data_id in self.assets:
      return self.assets[data_id]
    return None


  def create_object(self, name : str, transform : SimTransform, parent : str = None) -> str:
    name = name or str(uuid4())

    obj = self.objects[name] = WebObject(
      name=name,
      parent=parent,
      transform=Transform.from_sim(transform)
    )

    if parent: obj.apply_global_transform(self.objects[parent].global_transform)

    self.object_list.append(obj)
    
    return name

  def update_transform(self, name : str, transform : SimTransform) -> None:

    if name not in self.objects: return
    transform = Transform.from_sim(transform)

    obj = self.objects[name]
    
    obj.transform.position = transform.position
    obj.transform.quaternion = transform.quaternion
    obj._dirty = True


  def attach_mesh(self, obj_name : str, mesh : str, material : str, transform : SimTransform) -> None:
    self.objects[obj_name].visuals.append(
      WebVisual(
        type="MESH",
        material=material,
        mesh=mesh,
        transform=Transform.from_sim(transform)
      )
    )

  def attach_primitive(self, obj_name : VisualType, type : str, material : str, transform : SimTransform) -> None:
    self.objects[obj_name].visuals.append(
      WebVisual(
        type=RenderPrimitiveType.from_sim(type),
        material=material,
        mesh=None,
        transform=Transform.from_sim(transform, type)
      )
    )

  def create_material(
    self, 
    material : SimMaterial,
    name = None,
    tex2name : dict[SimTexture, str] = dict()
    ) -> str:

    name = name or str(uuid4())

    material = WebMaterial(
      name=name,
      color=material.color,
      emission=np.max(np.nan_to_num(np.divide(material.emissionColor, material.color), nan=0)) if material.emissionColor else 0, 
      shininess=material.shininess,
      reflectance=material.reflectance,
      texture=tex2name.get(material.texture),
    )

    self.materials[name] = material

    return name

  def create_texture(self, tex : SimTexture) -> str:

    data = self.simpub.request("Asset", tex.hash, bytes)
      
    hash = md5(data).hexdigest()

    name = uuid4().hex

    texture = WebTexture(
      name=name,
      hash=hash,
      width=tex.width,
      height=tex.height,
      repeat=tex.textureScale
    )

    self.textures[name] = texture
    self.assets[hash] = data

    return name

  def create_mesh(self, mesh : SimMesh) -> str:
    
    data = self.simpub.request("Asset", mesh.hash, bytes)
    

    if len(data) < mesh.verticesLayout[1]:
      raise BufferError("Failed to load mesh data" + mesh.hash)
    

    vertices = np.frombuffer(data, dtype=np.float32,  offset=mesh.verticesLayout[0],  count=int(mesh.verticesLayout[1] / 4)).copy().reshape(-1, 3)
    indices = np.frombuffer(data, dtype=np.uint32,    offset=mesh.indicesLayout[0],   count=int(mesh.indicesLayout[1] / 4),).copy().reshape(-1, 3)
    normals = np.frombuffer(data, dtype=np.float32,   offset=mesh.normalsLayout[0],   count=int(mesh.normalsLayout[1] / 4),).copy().reshape(-1, 3)
    uvs = np.frombuffer(data, dtype=np.float32,       offset=mesh.uvLayout[0],        count=int(mesh.uvLayout[1] / 4),).copy().reshape(-1, 2) if mesh.uvLayout[1] else None


    vertices[:, 2] *= -1

    normals[:, 2] *= -1

    indices = indices[:, [0, 2, 1]].copy()


    mesh_data = BytesIO()
    vertex_layout = mesh_data.tell(), len(vertices.flatten())
    mesh_data.write(vertices)

    index_layout = mesh_data.tell(), len(indices.flatten())
    mesh_data.write(indices)

    normal_layout = mesh_data.tell(), len(normals.flatten())
    mesh_data.write(normals)
    
    uv_layout = mesh_data.tell(), len(uvs.flatten()) if uvs is not None else 0
    if uvs is not None: mesh_data.write(uvs)

    bytes_data = mesh_data.getbuffer()

    name = uuid4().hex

    mesh = WebMesh(
      name=name,
      hash=md5(bytes_data).hexdigest(),
      vertex_layout=vertex_layout,
      index_layout=index_layout,
      normal_layout=normal_layout,
      uv_layout=uv_layout
    )

    self.meshes[name] = mesh
    self.assets[mesh.hash] = bytes_data
    return name