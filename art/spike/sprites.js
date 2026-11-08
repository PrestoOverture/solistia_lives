// Parametric pixel characters: layered parts on one locked palette, gestures as part poses.
// A character is a spec (skin, hair, outfit, accessory); drawFrame paints one pose into a canvas.

export const W = 24, H = 40;

// Locked palette: every ramp is [shadow, base, light]; OUTLINE frames every silhouette.
export const PALETTE = {
  outline: '#2a1a1f',
  skin: ['#c98a6b', '#f2c4a0', '#fde3cc'],
  skin_tan: ['#a8694c', '#d9a07c', '#f0c7a5'],
  brown_hair: ['#5a3322', '#83502f', '#a8703f'],
  chestnut: ['#6b2f22', '#9a4a2c', '#c26b3c'],
  black: ['#1f1d2b', '#353248', '#4f4b66'],
  orange: ['#a9461f', '#e07a2e', '#f7a64e'],
  cyan: ['#1f6f86', '#37a6b8', '#78d3d6'],
  white: ['#b9b3c4', '#e9e5ee', '#ffffff'],
  green: ['#3e6b3a', '#5f9a4c', '#90c46a'],
  cream: ['#b8a07a', '#e2cfa4', '#f6e9c8'],
  red: ['#8e2231', '#c83a45', '#ec6a6a'],
  boots: ['#2e2230', '#45334a', '#5d4765'],
};

const OUTLINE = PALETTE.outline;

// Per-pose offsets for the parts: head and torso shift, legs shape, arm targets.
const POSES = {
  idle: {},
  nod: { headDy: 1 },
  bow: { headDy: 3, bodyDy: 1, eyes: 'closed', arms: ['chest', 'chest'] },
  wave: { arms: ['down', 'wave'] },
  point: { arms: ['down', 'point'] },
  hand_on_heart: { arms: ['down', 'chest'] },
  hips: { arms: ['hips', 'hips'] },
  kneel: { bodyDy: 6, legs: 'kneel', arms: ['down', 'chest'] },
  sit: { bodyDy: 5, legs: 'sit', arms: ['lap', 'lap'] },
};

export const GESTURES = Object.keys(POSES);

function painter(ctx) {
  const px = (x, y, c) => { ctx.fillStyle = c; ctx.fillRect(x | 0, y | 0, 1, 1); };
  const rect = (x, y, w, h, c) => { ctx.fillStyle = c; ctx.fillRect(x | 0, y | 0, w, h); };
  return { px, rect };
}

// A 2px-thick limb from point to point; the last two pixels are the hand.
function limb(p, points, sleeve, skin) {
  const cells = [];
  for (let i = 0; i < points.length - 1; i++) {
    const [x0, y0] = points[i], [x1, y1] = points[i + 1];
    const steps = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0), 1);
    for (let s = 0; s <= steps; s++) cells.push([Math.round(x0 + (x1 - x0) * s / steps), Math.round(y0 + (y1 - y0) * s / steps)]);
  }
  cells.forEach(([x, y], i) => {
    const c = i >= cells.length - 2 ? skin : sleeve;
    p.rect(x, y, 2, 2, c);
  });
}

function armPoints(kind, side, sx, sy) {
  const d = side; // -1 left (viewer's left), +1 right
  switch (kind) {
    case 'wave': return [[sx, sy], [sx + 3 * d, sy - 3], [sx + 4 * d, sy - 8], [sx + 4 * d, sy - 10]];
    case 'point': return [[sx, sy], [sx + 4 * d, sy + 1], [sx + 8 * d, sy + 1]];
    case 'chest': return [[sx, sy], [sx + d, sy + 4], [sx - 3 * d, sy + 4]];
    case 'hips': return [[sx, sy], [sx + 2 * d, sy + 3], [sx, sy + 6]];
    case 'lap': return [[sx, sy], [sx, sy + 4], [sx - 2 * d, sy + 6]];
    default: return [[sx, sy], [sx + d * 0.5, sy + 4], [sx + d * 0.5, sy + 7]];
  }
}

function drawHairBack(p, spec, cx, top) {
  const [s, b] = PALETTE[spec.hair.color];
  if (spec.hair.style === 'braids') {
    for (const side of [-1, 1]) {
      const x = cx + side * 5 - (side < 0 ? 1 : 0);
      for (let y = top + 8; y < top + 21; y++) p.rect(x, y, 2, 1, (y - top) % 3 === 0 ? s : b);
      p.rect(x, top + 21, 2, 1, PALETTE.red[1]);
    }
  } else if (spec.hair.style === 'twintails') {
    for (const side of [-1, 1]) {
      const x = cx + side * 7 - 1;
      p.rect(x, top + 3, 3, 6, b);
      p.rect(x + (side < 0 ? 0 : 1), top + 9, 2, 3, s);
    }
  } else if (spec.hair.style === 'long') {
    p.rect(cx - 6, top + 4, 12, 14, s);
  }
}

function drawHead(p, spec, cx, top, pose) {
  const skin = PALETTE[spec.skin];
  const [hs, hb, hl] = PALETTE[spec.hair.color];
  const widths = [6, 8, 10, 10, 10, 10, 10, 10, 9, 8, 6];
  widths.forEach((w, row) => p.rect(cx - (w >> 1), top + row, w, 1, skin[1]));
  p.rect(cx - 5, top + 8, 1, 1, skin[0]);
  // Hair cap and bangs.
  [6, 10, 12, 12].forEach((w, row) => p.rect(cx - (w >> 1), top - 1 + row, w, 1, row === 0 ? hl : hb));
  p.rect(cx - 6, top + 3, 2, 5, hb);
  p.rect(cx + 4, top + 3, 2, 5, hb);
  for (let x = cx - 4; x < cx + 4; x += 2) p.rect(x, top + 3, 1, 1 + ((x >> 1) & 1), hs);
  p.rect(cx - 2, top, 3, 1, hl);
  // Face.
  const eye = PALETTE.outline;
  if (pose.eyes === 'closed') {
    p.rect(cx - 3, top + 6, 2, 1, eye);
    p.rect(cx + 1, top + 6, 2, 1, eye);
  } else {
    p.rect(cx - 3, top + 5, 1, 2, eye);
    p.rect(cx + 2, top + 5, 1, 2, eye);
    p.px(cx - 3, top + 5, '#5b6fa8');
    p.px(cx + 2, top + 5, '#5b6fa8');
  }
  p.px(cx - 4, top + 7, '#e89a8c');
  p.px(cx + 3, top + 7, '#e89a8c');
  p.px(cx - 1, top + 8, skin[0]);
  // Accessories.
  if (spec.accessory === 'rose_headband') {
    p.rect(cx - 5, top + 1, 10, 1, PALETTE.black[1]);
    p.rect(cx - 6, top, 3, 3, PALETTE.red[1]);
    p.px(cx - 5, top + 1, PALETTE.red[2]);
    p.rect(cx - 6, top + 7, 1, 2, PALETTE.white[2]);
    p.rect(cx + 5, top + 7, 1, 2, PALETTE.white[2]);
  } else if (spec.accessory === 'ribbon') {
    p.rect(cx + 3, top - 2, 4, 2, PALETTE.red[1]);
    p.px(cx + 4, top - 2, PALETTE.red[2]);
  }
}

function drawLegs(p, spec, cx, hip, pose, walk) {
  const boot = PALETTE.boots;
  const skin = PALETTE[spec.skin];
  if (pose.legs === 'kneel') {
    p.rect(cx - 5, hip + 1, 10, 3, PALETTE[spec.outfit.skirt][0]);
    p.rect(cx - 6, hip + 3, 4, 2, boot[1]);
    return;
  }
  if (pose.legs === 'sit') {
    p.rect(cx - 4, hip + 1, 3, 3, skin[1]);
    p.rect(cx + 1, hip + 1, 3, 3, skin[1]);
    p.rect(cx - 4, hip + 4, 3, 2, boot[1]);
    p.rect(cx + 1, hip + 4, 3, 2, boot[1]);
    return;
  }
  const lift = [walk === 1 ? 1 : 0, walk === 3 ? 1 : 0];
  [[cx - 4, lift[0]], [cx + 1, lift[1]]].forEach(([x, up]) => {
    p.rect(x, hip, 3, 6 - up, skin[1]);
    p.px(x, hip, skin[0]);
    p.rect(x, hip + 5 - up, 3, 2, boot[1]);
    p.px(x + 2, hip + 5 - up, boot[2]);
  });
}

function drawTorso(p, spec, cx, top) {
  const o = spec.outfit;
  const [ts, tb, tl] = PALETTE[o.top];
  // Bodice.
  p.rect(cx - 4, top, 8, 7, tb);
  p.rect(cx - 4, top, 1, 7, ts);
  p.rect(cx + 2, top + 1, 1, 5, tl);
  if (o.straps) {
    p.rect(cx - 4, top, 2, 2, PALETTE[o.straps][1]);
    p.rect(cx + 2, top, 2, 2, PALETTE[o.straps][1]);
    p.rect(cx - 1, top + 2, 2, 4, PALETTE.orange[1]);
  }
  // Sash.
  if (o.sash) {
    const [ss, sb, sl] = PALETTE[o.sash];
    p.rect(cx - 5, top + 7, 10, 2, sb);
    p.rect(cx - 5, top + 8, 10, 1, ss);
    p.rect(cx + 3, top + 9, 1, 3, sl);
    p.rect(cx + 4, top + 9, 1, 2, sb);
  }
  // Skirt: flares out toward the hem.
  const [ks, kb, kl] = PALETTE[o.skirt];
  const skirtTop = top + (o.sash ? 9 : 7);
  const rows = o.length ?? 7;
  for (let r = 0; r < rows; r++) {
    const w = 10 + Math.min(r, 4);
    p.rect(cx - (w >> 1), skirtTop + r, w, 1, kb);
    p.px(cx - (w >> 1), skirtTop + r, ks);
    p.px(cx + (w >> 1) - 1, skirtTop + r, ks);
    if (r % 2 === 0) p.px(cx + 1 - (r % 4), skirtTop + r, kl);
  }
  p.rect(cx - 7, skirtTop + rows - 1, 14, 1, ks);
  if (o.apron) {
    const [as, ab] = PALETTE[o.apron];
    p.rect(cx - 3, skirtTop, 6, rows - 1, ab);
    p.rect(cx - 3, skirtTop + rows - 2, 6, 1, as);
  }
  return skirtTop + rows;
}

function outline(ctx) {
  const img = ctx.getImageData(0, 0, W, H);
  const a = (x, y) => x >= 0 && y >= 0 && x < W && y < H && img.data[(y * W + x) * 4 + 3] > 0;
  const edge = [];
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    if (!a(x, y) && (a(x - 1, y) || a(x + 1, y) || a(x, y - 1) || a(x, y + 1))) edge.push([x, y]);
  }
  ctx.fillStyle = OUTLINE;
  edge.forEach(([x, y]) => ctx.fillRect(x, y, 1, 1));
}

// Paint one frame. gesture: a GESTURES key; walk: 0-3 walk phase or null.
export function drawFrame(ctx, spec, gesture = 'idle', walk = null, t = 0) {
  ctx.clearRect(0, 0, W, H);
  const p = painter(ctx);
  const pose = { ...POSES[gesture] };
  if (gesture === 'nod') pose.headDy = Math.floor(t * 4) % 2;
  const bob = walk === 1 || walk === 3 ? 1 : 0;
  const cx = 12;
  const bodyDy = (pose.bodyDy ?? 0) + bob;
  const headTop = 4 + bodyDy + (pose.headDy ?? 0);
  const torsoTop = 16 + bodyDy;
  drawHairBack(p, spec, cx, headTop);
  const hip = drawTorso(p, spec, cx, torsoTop) - 1;
  drawLegs(p, spec, cx, Math.min(hip, 32), pose, walk);
  const [left, right] = pose.arms ?? ['down', 'down'];
  const sleeve = PALETTE[spec.skin][1];
  const swing = walk === null ? 0 : [0, 1, 0, -1][walk];
  limb(p, armPoints(left, -1, cx - 6, torsoTop + 1 + swing), sleeve, PALETTE[spec.skin][1]);
  limb(p, armPoints(right, 1, cx + 4, torsoTop + 1 - swing), sleeve, PALETTE[spec.skin][1]);
  drawHead(p, spec, cx, headTop, pose);
  if (spec.hair.style === 'braids') {
    // Braid ends fall in front of the shoulders.
    for (const side of [-1, 1]) p.rect(cx + side * 5 - (side < 0 ? 1 : 0), torsoTop, 2, 3, PALETTE[spec.hair.color][1]);
  }
  outline(ctx);
}

export const CAST = {
  agnea: {
    skin: 'skin', hair: { style: 'braids', color: 'brown_hair' }, accessory: 'rose_headband',
    outfit: { top: 'black', straps: 'white', sash: 'cyan', skirt: 'orange', length: 8 },
  },
  pala: {
    skin: 'skin', hair: { style: 'twintails', color: 'chestnut' }, accessory: 'ribbon',
    outfit: { top: 'green', skirt: 'green', apron: 'cream', length: 6 },
  },
};
