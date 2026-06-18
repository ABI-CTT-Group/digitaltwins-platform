<template>
  <div ref="host" class="heart-holo" aria-hidden="true"></div>
</template>

<script setup lang="ts">
/**
 * Real-time WebGL holographic heart for the landing hero.
 *
 * Two meshes extracted from the whole-body glTF, rendered on a transparent
 * canvas so the page aurora shows through:
 *   - body   (myocardium + ascending aorta): a delicate fine wireframe net +
 *             a faint cyan glass surface (fresnel rim, transparent core);
 *   - vessels (coronary tree): a soft low-alpha glow only — NO wireframe — so
 *             the vessels read as delicate hints, not bold lines.
 * The neon halo comes from a CSS glow on the canvas silhouette. It beats on a
 * smooth lub-dub loop and can be mouse-rotated (TrackballControls).
 */
import { onMounted, onBeforeUnmount, ref } from 'vue';
import * as THREE from 'three';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
import { TrackballControls } from 'three/addons/controls/TrackballControls.js';
// single OBJ with two material groups: `body` (fine, Loop-subdivided ~88k tris)
// and `vessels` (coronary tree) — OBJLoader splits them into two meshes.
import heartUrl from '@/assets/models/heart2.obj?url';

const host = ref<HTMLElement | null>(null);

let renderer: THREE.WebGLRenderer | null = null;
let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let group: THREE.Group | null = null;
let controls: TrackballControls | null = null;
const disposables: Array<{ dispose: () => void }> = [];
let raf = 0;
let observer: ResizeObserver | null = null;
let disposed = false;
const clock = new THREE.Clock();

const reduceMotion = typeof window !== 'undefined'
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const uniforms = {
  uTime: { value: 0 },
  uGlow: { value: 1 },
  uMinY: { value: -1 },
  uMaxY: { value: 1 },
  uCyan: { value: new THREE.Color(0x6fe0f2) },
  uDeep: { value: new THREE.Color(0x1080b5) },
  uMag: { value: new THREE.Color(0xd66bd0) },
};

const vertexShader = /* glsl */ `
  varying vec3 vN; varying vec3 vView; varying float vYn;
  uniform float uMinY, uMaxY;
  void main(){
    vec4 wp = modelMatrix * vec4(position,1.0);
    vN = normalize(mat3(modelMatrix)*normal);
    vView = normalize(cameraPosition - wp.xyz);
    vYn = (position.y - uMinY)/max(uMaxY-uMinY,0.0001);
    gl_Position = projectionMatrix * viewMatrix * wp;
  }
`;
const surfaceFrag = /* glsl */ `
  precision highp float;
  uniform float uTime; uniform float uGlow; uniform vec3 uCyan; uniform vec3 uDeep; uniform vec3 uMag;
  varying vec3 vN; varying vec3 vView; varying float vYn;
  void main(){
    vec3 n=normalize(vN), v=normalize(vView);
    float f = 1.0 - clamp(dot(n,v),0.0,1.0);
    float rim = pow(f, 1.9);
    vec3 col = mix(uDeep, uCyan, rim);
    col += uMag * smoothstep(0.5,0.1,vYn) * (0.14 + rim*0.4);     // soft magenta toward the apex
    float scan = 0.9 + 0.1*sin(vYn*80.0 - uTime*2.0);
    float a = (0.04 + 0.42*rim) * scan * uGlow;                  // glass: transparent core, lit rim
    gl_FragColor = vec4(col*(0.5+rim*0.45), a);
  }
`;
const innerFrag = /* glsl */ `
  precision highp float;
  uniform vec3 uDeep; varying vec3 vN; varying vec3 vView;
  void main(){
    vec3 n=normalize(vN), v=normalize(vView);
    float f = 1.0 - clamp(dot(n,v),0.0,1.0);
    gl_FragColor = vec4(uDeep*0.8, pow(f,3.0)*0.08);             // faint inner volume
  }
`;
// vessels: soft low-alpha glow only, no wireframe → delicate, not bold lines
const vesselFrag = /* glsl */ `
  precision highp float;
  uniform float uGlow; uniform vec3 uCyan; uniform vec3 uMag;
  varying vec3 vN; varying vec3 vView;
  void main(){
    vec3 n=normalize(vN), v=normalize(vView);
    float f = 1.0 - clamp(dot(n,v),0.0,1.0);
    vec3 col = mix(uMag, uCyan, 0.5);
    gl_FragColor = vec4(col*0.5, (0.04 + 0.04*f) * uGlow);
  }
`;

// Cardiac-cycle long-axis contraction profile sampled from the morph animation of
// plan/reference/noInfarct.glb (1 = diastole / relaxed, dips at systole). 60 samples
// over one beat — drives heart2's squash so the rhythm matches the real simulation.
const BEAT_CURVE = [
  0.9683, 0.9701, 0.9719, 0.9739, 0.9759, 0.9779, 0.9800, 0.9820, 0.9841, 0.9861,
  0.9880, 0.9899, 0.9917, 0.9935, 0.9952, 0.9969, 0.9985, 1.0000, 0.9998, 0.9739,
  0.9655, 0.9611, 0.9574, 0.9411, 0.9321, 0.9262, 0.9204, 0.9150, 0.9099, 0.9050,
  0.8987, 0.8925, 0.8803, 0.8734, 0.8630, 0.8534, 0.8439, 0.8354, 0.8265, 0.8217,
  0.8265, 0.8336, 0.8409, 0.8484, 0.8559, 0.8634, 0.8709, 0.8784, 0.8858, 0.8933,
  0.9008, 0.9083, 0.9158, 0.9233, 0.9308, 0.9383, 0.9458, 0.9533, 0.9608, 0.9683,
];
const BEAT_PERIOD = 4.0;   // s per cycle (noInfarct's native cycle is 5.9 s; tightened for the hero)

// long-axis (apex→base) contraction factor for time t, looping the sampled curve.
function beatLong(t: number): number {
  const n = BEAT_CURVE.length;
  const p = ((t % BEAT_PERIOD) / BEAT_PERIOD) * n;
  const i = Math.floor(p) % n;
  const j = (i + 1) % n;
  const f = p - Math.floor(p);
  return BEAT_CURVE[i] * (1 - f) + BEAT_CURVE[j] * f;
}

// Uniform surface stipple: sample n points evenly over the mesh surface (area-
// weighted), independent of the triangulation. heart2's mesh is CAD-like/uneven,
// so a wireframe reads as "wireframe on"; an even point grain reads as the fine
// organic texture heart1 has. Sampled once at load; scales with the beat.
function sampleSurfaceGrain(geo: THREE.BufferGeometry, n: number): THREE.BufferGeometry {
  const pos = geo.attributes.position;
  const triCount = (pos.count / 3) | 0;
  const cum = new Float32Array(triCount);
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  const e1 = new THREE.Vector3(), e2 = new THREE.Vector3();
  let total = 0;
  for (let i = 0; i < triCount; i++) {
    a.fromBufferAttribute(pos, i * 3); b.fromBufferAttribute(pos, i * 3 + 1); c.fromBufferAttribute(pos, i * 3 + 2);
    total += e1.subVectors(b, a).cross(e2.subVectors(c, a)).length() * 0.5;
    cum[i] = total;
  }
  const out = new Float32Array(n * 3);
  for (let k = 0; k < n; k++) {
    const r = Math.random() * total;
    let lo = 0, hi = triCount - 1;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (cum[mid] < r) lo = mid + 1; else hi = mid; }
    a.fromBufferAttribute(pos, lo * 3); b.fromBufferAttribute(pos, lo * 3 + 1); c.fromBufferAttribute(pos, lo * 3 + 2);
    let u = Math.random(), v = Math.random();
    if (u + v > 1) { u = 1 - u; v = 1 - v; }
    out[k * 3] = a.x + (b.x - a.x) * u + (c.x - a.x) * v;
    out[k * 3 + 1] = a.y + (b.y - a.y) * u + (c.y - a.y) * v;
    out[k * 3 + 2] = a.z + (b.z - a.z) * u + (c.z - a.z) * v;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(out, 3));
  return g;
}

// shared center + scale (computed from the body, applied to both meshes so they stay aligned)
let center = new THREE.Vector3();
let normScale = 1;

function buildBody(g: THREE.BufferGeometry) {
  g.computeVertexNormals();
  g.computeBoundingBox();
  g.boundingBox!.getCenter(center);
  const size = new THREE.Vector3();
  g.boundingBox!.getSize(size);
  normScale = 2.6 / Math.max(size.x, size.y, size.z);   // a touch more contained in the hero
  g.translate(-center.x, -center.y, -center.z);
  g.scale(normScale, normScale, normScale);
  g.computeBoundingBox();
  uniforms.uMinY.value = g.boundingBox!.min.y;
  uniforms.uMaxY.value = g.boundingBox!.max.y;

  const innerMat = new THREE.ShaderMaterial({ vertexShader, fragmentShader: innerFrag, uniforms, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.BackSide });
  const surfMat = new THREE.ShaderMaterial({ vertexShader, fragmentShader: surfaceFrag, uniforms, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.FrontSide });
  const grainGeo = sampleSurfaceGrain(g, 48000);
  const grainMat = new THREE.PointsMaterial({ color: 0x9fe9f6, size: 0.008, sizeAttenuation: true, transparent: true, opacity: 0.34, depthWrite: false, blending: THREE.AdditiveBlending });
  disposables.push(g, innerMat, surfMat, grainGeo, grainMat);

  group!.add(new THREE.Mesh(g, innerMat));
  group!.add(new THREE.Mesh(g, surfMat));
  group!.add(new THREE.Points(grainGeo, grainMat));   // uniform organic grain (replaces wireframe)
}

function buildVessels(g: THREE.BufferGeometry) {
  g.computeVertexNormals();
  g.translate(-center.x, -center.y, -center.z);
  g.scale(normScale, normScale, normScale);
  const mat = new THREE.ShaderMaterial({ vertexShader, fragmentShader: vesselFrag, uniforms, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide });
  disposables.push(g, mat);
  group!.add(new THREE.Mesh(g, mat));
}

function resize() {
  if (!renderer || !camera || !host.value) return;
  const w = host.value.clientWidth || 1;
  const h = host.value.clientHeight || 1;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  controls?.handleResize();
}

function render() {
  if (!renderer || !scene || !camera || !group) return;
  const t = clock.getElapsedTime();
  if (!reduceMotion) {
    uniforms.uTime.value = t;                     // drives the surface scan shimmer
    // real contraction: the whole heart gets a little SMALLER through systole,
    // shortening a bit more along apex→base (local Y). No radial bulge — both axes
    // shrink — so it reads as a beat, not a squash. Curve = noInfarct's rhythm.
    const c = 1.0 - beatLong(t);                  // contraction amount (0 = diastole)
    const long = 1.0 - 0.70 * c;                  // apex→base shortening
    const radial = 1.0 - 0.42 * c;                // radial shrink (less than long)
    group.scale.set(radial, long, radial);
    uniforms.uGlow.value = 0.9 + c * 1.2;         // glow swells through systole
  }
  controls?.update();
  renderer.render(scene, camera);
}

function animate() {
  raf = requestAnimationFrame(animate);
  render();
}

onMounted(() => {
  const el = host.value;
  if (!el) return;

  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
  camera.position.set(0, 0, 7.4);

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  el.appendChild(renderer.domElement);

  group = new THREE.Group();
  group.rotation.set(5.5683, 5.8469, 4.9567);   // pose chosen in the picker (X 319°, Y 335°, Z 284°)
  scene.add(group);

  const canInteract = window.matchMedia('(pointer: fine)').matches;
  controls = new TrackballControls(camera, renderer.domElement);
  controls.noZoom = true;
  controls.noPan = true;
  controls.rotateSpeed = 2.4;
  controls.dynamicDampingFactor = 0.12;
  controls.enabled = canInteract;
  el.style.pointerEvents = canInteract ? 'auto' : 'none';
  resize();

  // one OBJ → two sub-meshes; the larger is the body, the other the vessels
  new OBJLoader().load(heartUrl, (obj) => {
    if (disposed) return;
    const meshes: THREE.Mesh[] = [];
    obj.traverse((o) => { if ((o as THREE.Mesh).isMesh) meshes.push(o as THREE.Mesh); });
    meshes.sort((a, b) => b.geometry.attributes.position.count - a.geometry.attributes.position.count);
    if (meshes[0]) buildBody(meshes[0].geometry);   // body first → fixes the shared transform
    if (meshes[1]) buildVessels(meshes[1].geometry);
    if (reduceMotion && !canInteract) render();
    else animate();
  }, undefined, (err) => console.error('[HeartHologram] heart load failed', err));

  observer = new ResizeObserver(resize);
  observer.observe(el);
});

onBeforeUnmount(() => {
  disposed = true;
  if (raf) cancelAnimationFrame(raf);
  observer?.disconnect();
  controls?.dispose();
  disposables.forEach((d) => d.dispose());
  if (renderer) {
    renderer.domElement.remove();
    renderer.dispose();
    renderer.forceContextLoss();
  }
  renderer = scene = camera = group = controls = null;
});
</script>

<style scoped>
.heart-holo {
  position: absolute;
  inset: 0;
  filter: drop-shadow(0 0 13px rgba(95, 214, 232, 0.24)) drop-shadow(0 0 36px rgba(58, 170, 215, 0.16));
}
.heart-holo :deep(canvas) {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
