// Procedural pixel textures (nearest-filtered canvases) for the diorama.
import * as THREE from 'three';

function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function canvasTexture(size, paint, repeat = [1, 1]) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  paint(canvas.getContext('2d'), size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.NearestMipmapNearestFilter;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(...repeat);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

const speckle = (colors, seed, density = 1) => (ctx, n) => {
  const r = rng(seed);
  ctx.fillStyle = colors[0];
  ctx.fillRect(0, 0, n, n);
  for (let i = 0; i < n * n * density; i++) {
    ctx.fillStyle = colors[1 + Math.floor(r() * (colors.length - 1))];
    ctx.fillRect(Math.floor(r() * n), Math.floor(r() * n), 1, 1 + (r() < 0.3 ? 1 : 0));
  }
};

export const grass = (repeat) => canvasTexture(32, speckle(['#6f9a48', '#5d8a3c', '#83ad55', '#9cc062', '#55803a'], 3, 0.45), repeat);

export const path = (repeat) => canvasTexture(32, speckle(['#c9ab7c', '#b8986a', '#d9bd8e', '#a98a5e'], 7, 0.4), repeat);

export const cobble = (repeat) => canvasTexture(32, (ctx, n) => {
  const r = rng(11);
  ctx.fillStyle = '#7d7468';
  ctx.fillRect(0, 0, n, n);
  for (let y = 0; y < n; y += 6) {
    const shift = (y / 6) % 2 ? 3 : 0;
    for (let x = -6; x < n; x += 7) {
      const tone = ['#b6aa98', '#a69a88', '#c4b9a6', '#9c907f'][Math.floor(r() * 4)];
      ctx.fillStyle = tone;
      ctx.fillRect(x + shift + 1, y + 1, 5, 4);
      ctx.fillStyle = '#d6ccba';
      ctx.fillRect(x + shift + 1, y + 1, 4, 1);
    }
  }
}, repeat);

export const plaster = (repeat) => canvasTexture(16, speckle(['#efe2c6', '#e5d6b6', '#f6ecd6'], 5, 0.25), repeat);

export const planks = (repeat, base = '#8a5a36') => canvasTexture(16, (ctx, n) => {
  const r = rng(13);
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, n, n);
  for (let y = 0; y < n; y += 4) {
    ctx.fillStyle = '#5e3a22';
    ctx.fillRect(0, y, n, 1);
    for (let i = 0; i < 3; i++) {
      ctx.fillStyle = r() < 0.5 ? '#9d6a42' : '#7a4e2e';
      ctx.fillRect(Math.floor(r() * n), y + 1 + Math.floor(r() * 3), 3, 1);
    }
  }
}, repeat);

export const roofTiles = (repeat, colors = ['#a8473a', '#8c3a30', '#c25a45', '#6e2c26']) => canvasTexture(16, (ctx, n) => {
  ctx.fillStyle = colors[0];
  ctx.fillRect(0, 0, n, n);
  for (let y = 0; y < n; y += 4) {
    const shift = (y / 4) % 2 ? 2 : 0;
    ctx.fillStyle = colors[3];
    ctx.fillRect(0, y + 3, n, 1);
    for (let x = shift; x < n; x += 4) {
      ctx.fillStyle = colors[1];
      ctx.fillRect(x, y, 1, 3);
      ctx.fillStyle = colors[2];
      ctx.fillRect(x + 1, y, 2, 1);
    }
  }
}, repeat);

export const thatch = (repeat) => canvasTexture(16, speckle(['#c79a4e', '#a97e3a', '#ddb565', '#8d6630'], 17, 0.8), repeat);

export const water = (repeat) => canvasTexture(32, (ctx, n) => {
  const r = rng(23);
  ctx.fillStyle = '#4c8fb0';
  ctx.fillRect(0, 0, n, n);
  for (let i = 0; i < 40; i++) {
    ctx.fillStyle = r() < 0.6 ? '#6fb3cc' : '#3a7697';
    ctx.fillRect(Math.floor(r() * n), Math.floor(r() * n), 2 + Math.floor(r() * 4), 1);
  }
}, repeat);

export const sky = (top, bottom) => {
  const canvas = document.createElement('canvas');
  canvas.width = 2;
  canvas.height = 256;
  const ctx = canvas.getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 256);
  gradient.addColorStop(0, top);
  gradient.addColorStop(1, bottom);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 2, 256);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
};
