import { OrbitControls } from './OrbitControls.js';
import * as THREE from "https://cdnjs.cloudflare.com/ajax/libs/three.js/0.172.0/three.module.min.js"

class Scene {
  constructor() {
    
    this.objects = []

    
    this.scene = new THREE.Scene();

    this.canvas =  document.querySelector('#scene_container')
    /* Renderer */
    
    this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio)

    this.renderer.setSize(this.canvas.width, this.canvas.height, false)


    /* Camera */
    this.camera = new THREE.PerspectiveCamera(75, this.canvas.clientWidth / this.canvas.clientHeight, 0.1, 1000);
    this.camera.position.set(2.5, 3.5, 0)
    this.camera.rotation.set(-1.5, 1.0, 1.5)

    /* Lighting */
    const ambientLight = new THREE.AmbientLight( 0xffffff );
    this.scene.add(ambientLight);

    const light = new THREE.DirectionalLight( 0xFFF4D6, 1.0 );
    light.position.set( 15, -10, 0);
    this.scene.add(light)

    /* Background */
    this.scene.background = new THREE.Color( 0xffffff);


    /* Scene grid */
    // const gridHelper = new THREE.GridHelper(10, 10);
    // this.scene.add( gridHelper );

    /* Orbit controls */
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);

    window.onresize = () => this.on_resize()
  }

  on_resize() {
    this.camera.aspect = this.canvas.clientWidth / this.canvas.clientHeight;
    this.camera.updateProjectionMatrix()
  }

  add_object = function(object) {
    this.objects.push(object)
    this.scene.add(object)
  }

  clear() {
    this.objects.forEach(obj => this.scene.remove(obj))
    this.objects = []
  }

  render() {
    requestAnimationFrame(() => this.render());
  
    this.controls.update();
  
    this.renderer.render(this.scene, this.camera);
  }

}

export default Scene;

