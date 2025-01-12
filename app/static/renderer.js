import * as THREE from "https://cdnjs.cloudflare.com/ajax/libs/three.js/0.172.0/three.module.min.js"
import AssetManager  from "./asset.js";
import WebSocketConnection from "./connection.js";
import Scene from "./scene.js";

const scene = new Scene()
const assets = new AssetManager("asset/")
const connection = new WebSocketConnection(window.location.hostname, 8001)


const bodies = {}
let root = null

connection.register_instruction("LOAD_MESH", data => assets.load_geometry(data))

connection.register_instruction("LOAD_TEXTURE", data => assets.load_texture(data))

connection.register_instruction("LOAD_MATERIAL", data =>  assets.load_material(data))

connection.register_instruction("LOAD_COMPLETE", data => {

  if (!root) return

  const center = new THREE.Vector3();
  const boundingBox = new THREE.Box3();
  
  boundingBox.setFromObject(root);
  boundingBox.getCenter(center);
  root.position.set(-center.x, 0.1 , -center.z)


})

connection.register_instruction("RESET", data => scene.clear())

function update_transforms(body, transform) {
  body.position.set(...transform.position);
  body.quaternion.set(...transform.quaternion);
}


connection.register_instruction("UPDATE_TRANSFORM", data => {
  for (const [name, transform] of Object.entries(data)) {
    const body = bodies[name]
    update_transforms(body, transform)
  }
});

connection.register_instruction("CREATE_OBJECT", body =>  {

  const bodyObj = new THREE.Group()
  bodyObj.name = body.name

  update_transforms(bodyObj, body.transform)
  bodies[bodyObj.name] = bodyObj


  const visuals = new THREE.Group()
  visuals.name = "Visuals";
  bodyObj.add(visuals)


  body.visuals.forEach(visual => {

    const geometry = {
      'MESH' : () => new THREE.BoxGeometry(),
      "PLANE": () => new THREE.PlaneGeometry(),
      "SPHERE": () => new THREE.SphereGeometry(),
      "CUBE" : () => new THREE.BoxGeometry(),
      "CYLINDER" : () => new THREE.CylinderGeometry(),
      "CAPSULE" : () => new THREE.CapsuleGeometry(),
    }[visual.type]()
    
  
    const material = new THREE.MeshPhysicalMaterial({color: new THREE.Color(1, 1, 0.9, 1).getHex()}) 
    const visualObj = new THREE.Mesh(geometry, material)


    if (visual.mesh) {
      visualObj.visible = false
      assets.on_geometry_load(visual.mesh, geometry => {
        visualObj.geometry = geometry
        visualObj.visible = true
        visualObj.needs_update = true
      })
    }
    if (visual.material) {
      assets.on_material_load(visual.material, material => {
        visualObj.material = material
        visualObj.needs_update = true
      })
    }

    visualObj.scale.set(...visual.transform.scale)
    visualObj.position.set(...visual.transform.position)
    visualObj.quaternion.set(...visual.transform.quaternion)
    visuals.add(visualObj)

  })

  if (body.parent) {
    bodies[body.parent].add(bodyObj)
  } else {
    console.log(bodyObj)
    scene.add_object(bodyObj)
    root = bodyObj
  } 
})


connection.connect()
scene.render()