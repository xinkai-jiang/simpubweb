import * as THREE from "https://cdnjs.cloudflare.com/ajax/libs/three.js/0.172.0/three.module.min.js"

class Asset {
  constructor() {
    this.loaded = false
    this.on_load_callbacks = []
    this.data = null
  }

  set_asset(asset) {
    this.data = asset
    this.loaded = true

    this.on_load_callbacks.forEach(func => func(this.data))
  }

  on_load(func) {
    if (this.loaded) return func(this.data)
    this.on_load_callbacks.push(func)
  } 
}

function AssetDict() {
  const dict = {};
  return {
      get: (key) =>  {
          if (!(key in dict)) dict[key] = new Asset()
          return dict[key];
      },
      dict: dict
  };
}

class AssetManager {

  constructor(url) {

    this.geometries = AssetDict()
    this.materials = AssetDict()
    this.textures = AssetDict()

    this.url = url

  }


  on_geometry_load = (name, func) => this.geometries.get(name).on_load(func)
    
  on_material_load = (name, func) => this.materials.get(name).on_load(func)

  on_texture_load = (name, func)  => this.textures.get(name).on_load(func)
  

  // Geometry loading
  load_geometry(geometry_info) {
    if (geometry_info.name in this.geometries) return

    fetch(this.url + geometry_info.hash)
    .then(req => req.blob())
    .then(req => req.arrayBuffer())
    .then(data => {
      const geometry = new THREE.BufferGeometry();

      const indices = new Uint32Array(data, geometry_info.index_layout[0], geometry_info.index_layout[1]);
      geometry.setIndex(new THREE.BufferAttribute(indices, 1));

      const vertices = new Float32Array(data, geometry_info.vertex_layout[0], geometry_info.vertex_layout[1]);
      geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
      
      const normals = new Float32Array(data, geometry_info.normal_layout[0], geometry_info.normal_layout[1]);
      geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
      
      if (geometry_info.uv_layout[1] > 0) {
        const uvs = new Float32Array(data, geometry_info.uv_layout[0], geometry_info.uv_layout[1]);
        geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2))
      }

      this.geometries.get(geometry_info.name).set_asset(geometry)
    })
  }

  // textures 
  load_texture(texture_info) {

    fetch(this.url + texture_info.hash)
    .then(data => data.blob())
    .then(data => data.arrayBuffer())
    .then(data => {
      const rgbData = new Uint8Array(data);
      const rgbaData = new Uint8Array(rgbData.length + (rgbData.length / 3));

      for (let i = 0; i < rgbData.length; i++) {
          rgbaData[i * 4] = rgbData[i * 3];
          rgbaData[i * 4 + 1] = rgbData[i * 3 + 1];
          rgbaData[i * 4+ 2] = rgbData[i * 3 + 2];
          rgbaData[i * 4+ 3] = 255;
      }
      
      var tex = new THREE.DataTexture(rgbaData, texture_info.height, texture_info.width, THREE.RGBAFormat)

      tex.wrapS = tex.wrapT = THREE.RepeatWrapping;

      tex.offset.set( 0, 0 );
      tex.repeat.set(...texture_info.repeat);

      console.log(tex.repeat)
      
      tex.needsUpdate = true
      console.log(texture_info.name)
      this.textures.get(texture_info.name).set_asset(tex)
    })
  }

  // Material loading
  load_material(material) {   

    const mat = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color(material.color[0], material.color[1], material.color[2], material.color[3]),
      roughness: 1.0 - material.shininess,
      metalness: material.reflectance,
      specularIntensity : material.specular,
    })
    
    if (material.texture) {
      this.on_texture_load(material.texture, tex => {
        mat.map = tex
        mat.needsUpdate = true
      })
    }

    this.materials.get(material.name).set_asset(mat)
  }
}


export default AssetManager;