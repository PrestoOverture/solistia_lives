// Cropdale village square as a low-poly diorama with HD-2D post-processing.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPixelatedPass } from 'three/addons/postprocessing/RenderPixelatedPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import * as T from './textures.js';
import { W, H, drawFrame, CAST } from './sprites.js';

const params = new URLSearchParams(location.search);
const PART = params.get('part') || 'morning';
const FROZEN = params.has('t') ? parseFloat(params.get('t')) : null;
const PIXEL = parseInt(params.get('pixel') || '3');

const LIGHTING = {
  morning: { sky: ['#8cc4e8', '#f3e6c4'], sun: '#fff1d2', sunI: 2.6, hemi: ['#cfe6ff', '#6d7a4a', 1.1], sunPos: [-8, 12, 6], fog: '#dfe3d0', lamps: 0.2 },
  afternoon: { sky: ['#78b4e0', '#f7e2b0'], sun: '#ffe2a8', sunI: 2.8, hemi: ['#d8e6ff', '#7a7044', 1.0], sunPos: [6, 10, 5], fog: '#e8dcbc', lamps: 0.2 },
  evening: { sky: ['#4f4f8a', '#f29a64'], sun: '#ff9c5a', sunI: 2.0, hemi: ['#8c86c4', '#5a3e3a', 0.8], sunPos: [10, 4, 2], fog: '#b0807a', lamps: 1.4 },
  night: { sky: ['#0b1028', '#26305a'], sun: '#9fb4ff', sunI: 0.9, hemi: ['#4a5aa8', '#1a1e34', 0.9], sunPos: [-4, 10, 4], fog: '#182040', lamps: 1.8 },
}[PART];

const renderer = new THREE.WebGLRenderer({ antialias: false });
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
document.body.append(renderer.domElement);

const scene = new THREE.Scene();
scene.background = T.sky(...LIGHTING.sky);
scene.fog = new THREE.Fog(LIGHTING.fog, 26, 60);

const camera = new THREE.PerspectiveCamera(24, innerWidth / innerHeight, 0.5, 200);
camera.position.set(0, 9.5, 19);
camera.lookAt(0, 1.2, 0);

scene.add(new THREE.HemisphereLight(...LIGHTING.hemi));
const sun = new THREE.DirectionalLight(LIGHTING.sun, LIGHTING.sunI);
sun.position.set(...LIGHTING.sunPos);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -16, right: 16, top: 16, bottom: -16, near: 1, far: 50 });
sun.shadow.bias = -0.0008;
scene.add(sun);

// ---- helpers ----
const lambert = (opts) => new THREE.MeshLambertMaterial({ flatShading: true, ...opts });
function add(geometry, material, x, y, z, { ry = 0, cast = true, receive = true } = {}) {
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set(x, y, z);
  mesh.rotation.y = ry;
  mesh.castShadow = cast;
  mesh.receiveShadow = receive;
  scene.add(mesh);
  return mesh;
}
function group(x, z, ry = 0) {
  const g = new THREE.Group();
  g.position.set(x, 0, z);
  g.rotation.y = ry;
  scene.add(g);
  return g;
}
function put(g, geometry, material, x, y, z, opts = {}) {
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set(x, y, z);
  if (opts.rx) mesh.rotation.x = opts.rx;
  if (opts.ry) mesh.rotation.y = opts.ry;
  if (opts.rz) mesh.rotation.z = opts.rz;
  mesh.castShadow = opts.cast ?? true;
  mesh.receiveShadow = true;
  g.add(mesh);
  return mesh;
}

const lamps = [];
const glow = (color) => new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(LIGHTING.lamps) });

// ---- ground ----
add(new THREE.PlaneGeometry(80, 60).rotateX(-Math.PI / 2), lambert({ map: T.grass([40, 30]) }), 0, 0, -6, { cast: false });
add(new THREE.CircleGeometry(4.6, 10).rotateX(-Math.PI / 2), lambert({ map: T.cobble([8, 8]) }), 0, 0.02, 0.5, { cast: false });
add(new THREE.PlaneGeometry(2.2, 14).rotateX(-Math.PI / 2), lambert({ map: T.path([2, 12]) }), 0.6, 0.015, -9, { cast: false, ry: 0.12 });
add(new THREE.PlaneGeometry(16, 1.8).rotateX(-Math.PI / 2), lambert({ map: T.path([14, 2]) }), -8, 0.015, 2.5, { cast: false, ry: -0.08 });
// stone steps down toward the front
for (let i = 0; i < 3; i++) add(new THREE.BoxGeometry(3.4, 0.12, 0.5), lambert({ color: '#a89c88' }), 0, 0.06 - i * 0.02, 5.4 + i * 0.5);

// ---- buildings ----
function cottage(x, z, ry, { w = 3.2, d = 2.6, h = 2.0, roof = 'tiles', sign = null, chimney = true } = {}) {
  const g = group(x, z, ry);
  const wall = lambert({ map: T.plaster([2, 2]) });
  const timber = lambert({ color: '#5b3a24' });
  put(g, new THREE.BoxGeometry(w, h, d), wall, 0, h / 2, 0);
  put(g, new THREE.BoxGeometry(w + 0.3, 0.35, d + 0.3), lambert({ color: '#8f8574' }), 0, 0.17, 0);
  for (const sx of [-w / 2, w / 2]) put(g, new THREE.BoxGeometry(0.16, h, 0.16), timber, sx, h / 2, d / 2 + 0.01);
  put(g, new THREE.BoxGeometry(w, 0.14, 0.12), timber, 0, h * 0.62, d / 2 + 0.02);
  put(g, new THREE.BoxGeometry(0.12, h * 0.62, 0.12), timber, -w * 0.18, h * 0.31, d / 2 + 0.02);
  // gable roof: a triangular prism
  const shape = new THREE.Shape([new THREE.Vector2(-w / 2 - 0.35, 0), new THREE.Vector2(w / 2 + 0.35, 0), new THREE.Vector2(0, h * 0.75)]);
  const roofGeo = new THREE.ExtrudeGeometry(shape, { depth: d + 0.6, bevelEnabled: false });
  roofGeo.translate(0, 0, -(d + 0.6) / 2);
  const roofMat = roof === 'thatch' ? lambert({ map: T.thatch([0.4, 0.4]) }) : lambert({ map: T.roofTiles([0.5, 0.5]) });
  put(g, roofGeo, roofMat, 0, h, 0);
  // door and windows (windows glow at night)
  put(g, new THREE.BoxGeometry(0.7, 1.15, 0.08), lambert({ map: T.planks([1, 1], '#6e4428') }), w * 0.22, 0.6, d / 2 + 0.04);
  for (const sx of [-w * 0.36, w * 0.0]) {
    const win = put(g, new THREE.BoxGeometry(0.55, 0.5, 0.06), glow('#ffcf7a'), sx - 0.1, h * 0.42 + 0.05, d / 2 + 0.05, { cast: false });
    lamps.push(win);
    put(g, new THREE.BoxGeometry(0.75, 0.1, 0.18), timber, sx - 0.1, h * 0.42 - 0.25, d / 2 + 0.08);
    put(g, new THREE.BoxGeometry(0.7, 0.18, 0.22), lambert({ color: '#7a4e2e' }), sx - 0.1, h * 0.42 - 0.38, d / 2 + 0.14);
    for (let f = 0; f < 4; f++) put(g, new THREE.BoxGeometry(0.1, 0.1, 0.1), lambert({ color: ['#e86a7a', '#f2d04e', '#d14a9a', '#ffffff'][f] }), sx - 0.35 + f * 0.17, h * 0.42 - 0.26, d / 2 + 0.18, { cast: false });
  }
  if (chimney) put(g, new THREE.BoxGeometry(0.4, 1.2, 0.4), lambert({ color: '#8a7a6a' }), -w * 0.3, h + 0.9, -d * 0.15);
  if (sign) {
    put(g, new THREE.BoxGeometry(0.06, 0.06, 0.8), timber, w / 2 - 0.1, h * 0.75, d / 2 + 0.4);
    put(g, new THREE.BoxGeometry(0.06, 0.5, 0.6), lambert({ color: sign }), w / 2 - 0.1, h * 0.75 - 0.32, d / 2 + 0.5);
  }
  return g;
}

cottage(-6.6, -2.4, 0.35, { w: 3.4, sign: '#c9a24a' });
cottage(-3.2, -6.4, 0.12, { w: 3.0, d: 2.4, roof: 'thatch' });
cottage(5.4, -4.6, -0.3, { w: 4.2, d: 3.0, h: 2.4, sign: '#3a8a8a' });
cottage(8.6, 0.8, -0.7, { w: 2.8, d: 2.4, roof: 'thatch' });
cottage(1.6, -10.5, 0.0, { w: 3.0, d: 2.4 });
cottage(-9.5, -9.5, 0.5, { w: 3.0, d: 2.4, roof: 'thatch' });

// ---- trees, bushes, fences ----
function tree(x, z, s = 1, tint = '#4f8a3a') {
  const g = group(x, z);
  put(g, new THREE.CylinderGeometry(0.14 * s, 0.2 * s, 1.4 * s, 6), lambert({ color: '#6b4a2e' }), 0, 0.7 * s, 0);
  const leaf = lambert({ color: tint });
  const light = lambert({ color: new THREE.Color(tint).offsetHSL(0.02, 0.05, 0.1) });
  put(g, new THREE.IcosahedronGeometry(1.0 * s, 0), leaf, 0, 1.9 * s, 0);
  put(g, new THREE.IcosahedronGeometry(0.75 * s, 0), light, 0.45 * s, 2.4 * s, 0.25 * s);
  put(g, new THREE.IcosahedronGeometry(0.7 * s, 0), leaf, -0.5 * s, 2.2 * s, -0.2 * s);
}
function bush(x, z, s = 0.5, tint = '#5d9a40') {
  const light = new THREE.Color(tint).offsetHSL(0.02, 0.05, 0.08);
  [[0, 0, 1], [0.55, -0.1, 0.75], [-0.5, 0.05, 0.7], [0.1, 0.35, 0.65]].forEach(([dx, dz, k], i) =>
    add(new THREE.DodecahedronGeometry(s * k * 0.8, 1), lambert({ color: i === 3 ? light : tint }), x + dx * s, s * k * 0.55, z + dz * s));
}
[[-10, -3, 1.3], [10.5, -6, 1.4], [-12.5, 2, 1.1], [12, 3.5, 1.2], [-5.5, -12, 1.5], [6.5, -12.5, 1.3], [-14, -8, 1.6], [14, -11, 1.5], [-1.5, -14, 1.2]]
  .forEach(([x, z, s], i) => tree(x, z, s, ['#4f8a3a', '#5a9440', '#467f36'][i % 3]));
[[-4.8, 1.6], [-5.6, 3.8], [4.6, 2.6], [5.6, 4.4], [-2.2, -3.6], [3.2, -2.0], [-8.2, 5.2], [8.4, 5.8]]
  .forEach(([x, z], i) => bush(x, z, 0.45 + (i % 3) * 0.1, ['#5d9a40', '#6aa64a', '#4e8a38'][i % 3]));
for (let i = 0; i < 12; i++) {
  const x = -12 + i * 0.9;
  add(new THREE.BoxGeometry(0.12, 0.6, 0.12), lambert({ color: '#7a5434' }), x, 0.3, 6.3);
  if (i < 11) add(new THREE.BoxGeometry(0.9, 0.08, 0.06), lambert({ color: '#8c6440' }), x + 0.45, 0.42, 6.3);
}

// flower patches
const petals = ['#ff8aa6', '#ffd75e', '#ffffff', '#c47cff', '#ff6a5a'];
for (let i = 0; i < 70; i++) {
  const a = i * 2.4, r = 5.2 + (i % 7) * 0.35;
  const x = Math.cos(a) * r, z = 0.5 + Math.sin(a) * r * 0.8;
  if (z > -2 && Math.abs(x) < 4.2) continue;
  add(new THREE.BoxGeometry(0.09, 0.09, 0.09), lambert({ color: petals[i % petals.length] }), x, 0.08, z, { cast: false });
}

// ---- the well, crates, barrels ----
{
  const g = group(-2.6, -0.9);
  put(g, new THREE.CylinderGeometry(0.6, 0.65, 0.6, 8), lambert({ color: '#9a8f7e' }), 0, 0.3, 0);
  put(g, new THREE.CylinderGeometry(0.48, 0.48, 0.05, 8), lambert({ color: '#2f5a73' }), 0, 0.56, 0, { cast: false });
  for (const sx of [-0.5, 0.5]) put(g, new THREE.BoxGeometry(0.1, 1.3, 0.1), lambert({ color: '#6b4a2e' }), sx, 0.95, 0);
  const roof = new THREE.ConeGeometry(0.85, 0.55, 4);
  put(g, roof, lambert({ map: T.roofTiles([0.6, 0.6]) }), 0, 1.85, 0, { ry: Math.PI / 4 });
}
[[3.6, 0.4], [3.9, 1.1], [-6.0, 0.8]].forEach(([x, z], i) =>
  add(new THREE.BoxGeometry(0.55, 0.55, 0.55), lambert({ map: T.planks([1, 1], '#9a6a3e') }), x, 0.28, z, { ry: i * 0.4 }));
[[4.4, -0.2], [-6.6, 1.4]].forEach(([x, z]) =>
  add(new THREE.CylinderGeometry(0.3, 0.3, 0.7, 8), lambert({ map: T.planks([1, 1], '#7e5232') }), x, 0.35, z));

// ---- festival: canopy stalls, bunting, lantern posts ----
function stall(x, z, ry, stripe) {
  const g = group(x, z, ry);
  for (const [sx, sz] of [[-0.9, -0.6], [0.9, -0.6], [-0.9, 0.6], [0.9, 0.6]]) put(g, new THREE.BoxGeometry(0.08, 1.6, 0.08), lambert({ color: '#7a5434' }), sx, 0.8, sz);
  put(g, new THREE.BoxGeometry(1.9, 0.5, 0.5), lambert({ map: T.planks([2, 1], '#a07446') }), 0, 0.5, 0.45);
  const cloth = new THREE.CanvasTexture((() => {
    const c = document.createElement('canvas'); c.width = 8; c.height = 2;
    const ctx = c.getContext('2d');
    for (let i = 0; i < 8; i++) { ctx.fillStyle = i % 2 ? '#fff4e0' : stripe; ctx.fillRect(i, 0, 1, 2); }
    return c;
  })());
  cloth.magFilter = THREE.NearestFilter;
  cloth.colorSpace = THREE.SRGBColorSpace;
  put(g, new THREE.BoxGeometry(2.1, 0.06, 1.5), lambert({ map: cloth }), 0, 1.65, 0.05, { rx: 0.18 });
  for (let i = 0; i < 4; i++) put(g, new THREE.SphereGeometry(0.11, 6, 4), lambert({ color: ['#e85a3a', '#f2c84a', '#8ac44a', '#d14a6a'][i] }), -0.6 + i * 0.4, 0.82, 0.45);
}
stall(-3.4, 2.9, 0.5, '#d9503e');
stall(3.6, -1.6, -0.45, '#3e7fd9');

const posts = [[-4.2, 4.6], [-3.2, -2.6], [3.0, -3.4], [4.6, 3.8]];
posts.forEach(([x, z]) => {
  add(new THREE.BoxGeometry(0.14, 2.8, 0.14), lambert({ color: '#6b4a2e' }), x, 1.4, z);
  const lamp = add(new THREE.BoxGeometry(0.26, 0.32, 0.26), glow('#ffb45a'), x, 2.55, z + 0.15, { cast: false });
  lamps.push(lamp);
  if (LIGHTING.lamps > 1) {
    const light = new THREE.PointLight('#ffb060', LIGHTING.lamps * 2.2, 5.5, 1.8);
    light.position.set(x, 2.3, z + 0.4);
    scene.add(light);
  }
});
const flagColors = ['#e8503a', '#f2c84a', '#4aa0e0', '#f2f2f2', '#8ac44a', '#d95a9a'];
function bunting(a, b, sag = 0.6, count = 14) {
  for (let i = 0; i <= count; i++) {
    const t = i / count;
    const x = a[0] + (b[0] - a[0]) * t, z = a[1] + (b[1] - a[1]) * t;
    const y = 2.75 - sag * 4 * t * (1 - t);
    if (i < count) {
      const flag = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-0.13, 0, 0), new THREE.Vector3(0.13, 0, 0), new THREE.Vector3(0, -0.3, 0)]);
      flag.computeVertexNormals();
      add(flag, new THREE.MeshLambertMaterial({ color: flagColors[i % flagColors.length], side: THREE.DoubleSide }), x + (b[0] - a[0]) / count / 2, y - 0.02, z + (b[1] - a[1]) / count / 2, { ry: Math.atan2(-(b[1] - a[1]), b[0] - a[0]) });
    }
  }
}
bunting(posts[0], posts[1]);
bunting(posts[1], posts[2]);
bunting(posts[2], posts[3]);

// ---- distance: rolling hills, fields, a windmill ----
[[-22, -26, 9, '#7aa857'], [0, -32, 12, '#6e9e4e'], [22, -27, 10, '#86b060'], [-36, -20, 8, '#73a352'], [36, -18, 8, '#7aa857']]
  .forEach(([x, z, r, c]) => add(new THREE.SphereGeometry(r, 10, 6, 0, Math.PI * 2, 0, Math.PI / 2), lambert({ color: c }), x, -r * 0.45, z, { cast: false }));
[['#c8b65a', -12, -18], ['#9cbc5a', -4, -20], ['#d4a84a', 6, -19], ['#a6c86a', 14, -17]].forEach(([c, x, z]) =>
  add(new THREE.PlaneGeometry(7, 3.5).rotateX(-Math.PI / 2), lambert({ color: c }), x, 0.03, z, { cast: false, ry: 0.1 }));
{
  const g = group(-15, -15, 0.4);
  put(g, new THREE.CylinderGeometry(0.8, 1.2, 4.2, 8), lambert({ color: '#e6dbc4' }), 0, 2.1, 0);
  put(g, new THREE.ConeGeometry(1.2, 1.2, 8), lambert({ map: T.roofTiles([0.6, 0.6]) }), 0, 4.8, 0);
  const sails = new THREE.Group();
  sails.position.set(0, 3.6, 1.15);
  for (let i = 0; i < 4; i++) {
    const s = new THREE.Mesh(new THREE.BoxGeometry(0.5, 2.6, 0.05), lambert({ color: '#f4ecd8' }));
    s.position.y = 1.4;
    const arm = new THREE.Group();
    arm.rotation.z = i * Math.PI / 2;
    arm.add(s);
    s.castShadow = true;
    sails.add(arm);
  }
  g.add(sails);
  window.__sails = sails;
}

// ---- characters ----
const UNIT = 0.036; // world units per sprite pixel
const cast = [];
function character(spec, x, z, scale = 1) {
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const texture = new THREE.CanvasTexture(canvas);
  texture.magFilter = texture.minFilter = THREE.NearestFilter;
  texture.colorSpace = THREE.SRGBColorSpace;
  const height = H * UNIT * scale / Math.cos(0.42);
  const geometry = new THREE.PlaneGeometry(W * UNIT * scale, height).translate(0, height / 2, 0);
  const mesh = new THREE.Mesh(geometry, new THREE.MeshLambertMaterial({ map: texture, alphaTest: 0.5 }));
  mesh.position.set(x, 0.02, z);
  mesh.castShadow = true;
  scene.add(mesh);
  const blob = add(new THREE.CircleGeometry(0.28 * scale, 12).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: '#000', transparent: true, opacity: 0.28, depthWrite: false }), x, 0.04, z, { cast: false, receive: false });
  const actor = { spec, mesh, blob, canvas, texture, gesture: 'idle', walk: null, key: '' };
  cast.push(actor);
  return actor;
}
function paint(actor, t) {
  const walk = actor.walk === null ? null : Math.floor(t * 6) % 4;
  const key = `${actor.gesture}:${walk}:${actor.gesture === 'nod' ? Math.floor(t * 4) % 2 : 0}`;
  if (key === actor.key) return;
  actor.key = key;
  drawFrame(actor.canvas.getContext('2d'), actor.spec, actor.gesture, walk, t);
  actor.texture.needsUpdate = true;
}

// ?png=1: Agnea as a cleaned 80px PixelLab sheet (art/pixel/clean.py) instead of the parametric sprite
function pngCharacter(name, frames, x, z, height, aspect = 1) {
  const loader = new THREE.TextureLoader();
  const textures = Array.from({ length: frames }, (_, i) => {
    const texture = loader.load(`png/${name}_${i}.png`, () => FROZEN !== null && frame()); // frozen shots render once, so redraw on load
    texture.magFilter = texture.minFilter = THREE.NearestFilter;
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  });
  const h = height / Math.cos(0.42);
  const geometry = new THREE.PlaneGeometry(h * aspect, h).translate(0, h / 2, 0); // feet near the frame's bottom
  const mesh = new THREE.Mesh(geometry, new THREE.MeshLambertMaterial({ map: textures[0], alphaTest: 0.5 }));
  mesh.position.set(x, 0.02, z);
  mesh.castShadow = true;
  scene.add(mesh);
  const blob = add(new THREE.CircleGeometry(0.28, 12).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: '#000', transparent: true, opacity: 0.28, depthWrite: false }), x, 0.04, z, { cast: false, receive: false });
  return { mesh, blob, textures, gesture: 'idle', walk: null, png: true };
}

// ?png=1: the 80px dance sheet; ?png=text: the single text-prompted 48x80 sprite with its skirt redrawn
const PNG = params.get('png');
const agnea = PNG === 'text' ? pngCharacter('agnea_text', 1, -0.6, 1.6, 40 * UNIT * 80 / 67, 48 / 80)
  : PNG ? pngCharacter('agnea', 9, -0.6, 1.6, 40 * UNIT * 80 / 76) : character(CAST.agnea, -0.6, 1.6);
const pala = character(CAST.pala, 0.8, 1.9, 0.86);

// Demo timeline: Agnea walks in from the right, then gestures; Pala waves back.
function direct(t) {
  const loop = t % 16;
  if (PNG) {
    // the sheet is a dance: hold the idle frame, then step through the poses
    const i = loop < 4 ? 0 : 1 + Math.floor((loop - 4) / 1.5) % 8;
    agnea.mesh.material.map = agnea.textures[params.has('frame') ? +params.get('frame') : i % agnea.textures.length];
    pala.gesture = loop > 4 && loop < 7 ? 'wave' : 'idle';
    return;
  }
  if (loop < 3) {
    agnea.walk = 0; agnea.gesture = 'idle';
    agnea.mesh.position.x = 5 - (loop / 3) * 5.6;
  } else {
    agnea.walk = null;
    agnea.mesh.position.x = -0.6;
    agnea.gesture = ['idle', 'wave', 'hand_on_heart', 'point', 'bow', 'nod', 'kneel'][Math.floor((loop - 3) / 1.9) % 7];
  }
  pala.gesture = loop > 4 && loop < 7 ? 'wave' : loop > 11 ? 'hips' : 'idle';
  if (params.get('pose')) agnea.gesture = params.get('pose');
  agnea.blob.position.x = agnea.mesh.position.x;
}

// ---- post-processing: pixelate, bloom, tilt-shift, grade ----
const composer = new EffectComposer(renderer);
const pixelPass = new RenderPixelatedPass(PIXEL, scene, camera, { normalEdgeStrength: 0.25, depthEdgeStrength: 0.35 });
composer.addPass(pixelPass);
composer.addPass(new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), PART === 'night' || PART === 'evening' ? 0.55 : 0.3, 0.45, 0.88));
const tiltShift = new ShaderPass({
  uniforms: {
    tDiffuse: { value: null },
    resolution: { value: new THREE.Vector2(innerWidth, innerHeight) },
    focus: { value: 0.42 },
    band: { value: 0.16 },
    amount: { value: 5.0 },
    warmth: { value: PART === 'night' ? 0.0 : 0.05 },
  },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
  fragmentShader: `
    uniform sampler2D tDiffuse; uniform vec2 resolution; uniform float focus, band, amount, warmth; varying vec2 vUv;
    const vec2 disk[12] = vec2[](vec2(-0.326,-0.406),vec2(-0.840,-0.074),vec2(-0.696,0.457),vec2(-0.203,0.621),
      vec2(0.962,-0.195),vec2(0.473,-0.480),vec2(0.519,0.767),vec2(0.185,-0.893),vec2(0.507,0.064),
      vec2(0.896,0.412),vec2(-0.322,-0.933),vec2(-0.792,-0.598));
    void main(){
      float d = smoothstep(band, band + 0.32, abs(vUv.y - focus));
      vec2 r = amount * d / resolution * 2.0;
      vec4 c = texture2D(tDiffuse, vUv);
      for (int i = 0; i < 12; i++) c += texture2D(tDiffuse, vUv + disk[i] * r);
      c /= 13.0;
      c.rgb += vec3(warmth, warmth * 0.4, -warmth * 0.5) * d;
      float v = smoothstep(0.95, 0.35, length((vUv - 0.5) * vec2(1.25, 1.0)));
      c.rgb *= mix(0.72, 1.0, v);
      gl_FragColor = c;
    }`,
});
composer.addPass(tiltShift);
composer.addPass(new OutputPass());

const clock = new THREE.Clock();
function frame() {
  const t = FROZEN ?? clock.getElapsedTime();
  direct(t);
  cast.forEach(actor => paint(actor, t));
  window.__sails.rotation.z = t * 0.4;
  composer.render();
  if (FROZEN === null) requestAnimationFrame(frame);
  else document.body.dataset.ready = '1';
}
frame();
addEventListener('resize', () => {
  renderer.setSize(innerWidth, innerHeight);
  composer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
});
