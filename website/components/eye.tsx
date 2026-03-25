"use client";

import { useEffect, useRef, useImperativeHandle, forwardRef } from "react";

const TAU = Math.PI * 2;

// Seeded PRNG — stable random per frame so stipple doesn't flicker
const mulberry32 = (seed: number) => {
  return () => {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
};

export interface EyeHandle {
  setTarget: (x: number, y: number) => void;
}

interface EyeConfig {
  size: number;
  scleraColor: string;
  irisColors: [string, string, string];
  pupilColor: string;
  highlightColor: string;
  irisRatio: number;
  pupilRatio: number;
  parallax: { sclera: number; iris: number; pupil: number };
  maxOffset: number;
}

const DEFAULT_CONFIG: EyeConfig = {
  size: 400,
  scleraColor: "#e8e4e0",
  irisColors: ["#1a3d6e", "#3a7bd5", "#6db3f2"],
  pupilColor: "#050505",
  highlightColor: "rgba(255,255,255,0.9)",
  irisRatio: 0.38,
  pupilRatio: 0.18,
  parallax: { sclera: 0.03, iris: 0.55, pupil: 0.9 },
  maxOffset: 0.35,
};

// --- Hand-drawn rendering helpers ---

const drawRoughCircle = (
  ctx: CanvasRenderingContext2D,
  cx: number, cy: number, radius: number,
  jitter: number, segments: number, rng: () => number
) => {
  ctx.beginPath();
  for (let i = 0; i <= segments; i++) {
    const a = (i / segments) * TAU;
    const r = radius + Math.sin(a * 7) * jitter + (rng() - 0.5) * jitter * 0.8;
    const x = cx + Math.cos(a) * r;
    const y = cy + Math.sin(a) * r;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
};

const drawStipple = (
  ctx: CanvasRenderingContext2D,
  cx: number, cy: number, radius: number,
  count: number, dotSize: number, rng: () => number,
  falloff: number = 1.0 // 0 = uniform, 1 = dense center
) => {
  for (let i = 0; i < count; i++) {
    const a = rng() * TAU;
    // Weighted radius — more dots near center
    const t = rng();
    const r = radius * (falloff > 0 ? Math.pow(t, falloff * 0.5) : t);
    const x = cx + Math.cos(a) * r;
    const y = cy + Math.sin(a) * r;
    // Alpha fades toward edge
    const edgeFade = 1.0 - (r / radius) * 0.6;
    ctx.globalAlpha = edgeFade * (0.4 + rng() * 0.5);
    ctx.fillRect(x, y, dotSize + rng() * dotSize, dotSize + rng() * dotSize);
  }
  ctx.globalAlpha = 1;
};

const drawCrosshatch = (
  ctx: CanvasRenderingContext2D,
  cx: number, cy: number, innerR: number, outerR: number,
  count: number, rng: () => number
) => {
  // Radial strokes
  for (let i = 0; i < count; i++) {
    const a = (i / count) * TAU + (rng() - 0.5) * 0.04;
    const r1 = innerR + rng() * (outerR - innerR) * 0.2;
    const r2 = innerR + 0.3 * (outerR - innerR) + rng() * (outerR - innerR) * 0.65;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1);
    // Slight curve via quadratic
    const midA = a + (rng() - 0.5) * 0.06;
    const midR = (r1 + r2) * 0.5;
    ctx.quadraticCurveTo(
      cx + Math.cos(midA) * midR,
      cy + Math.sin(midA) * midR,
      cx + Math.cos(a + (rng() - 0.5) * 0.03) * r2,
      cy + Math.sin(a + (rng() - 0.5) * 0.03) * r2
    );
    ctx.lineWidth = 0.5 + rng() * 1.2;
    ctx.globalAlpha = 0.3 + rng() * 0.5;
    ctx.stroke();
  }

  // Concentric arc hatching
  const rings = 5 + Math.floor(rng() * 3);
  for (let r = 0; r < rings; r++) {
    const ringR = innerR + ((r + 0.5) / rings) * (outerR - innerR);
    const arcCount = 8 + Math.floor(rng() * 6);
    for (let a = 0; a < arcCount; a++) {
      const startA = rng() * TAU;
      const sweep = 0.15 + rng() * 0.35;
      ctx.beginPath();
      ctx.arc(cx, cy, ringR + (rng() - 0.5) * 2, startA, startA + sweep);
      ctx.lineWidth = 0.4 + rng() * 0.8;
      ctx.globalAlpha = 0.15 + rng() * 0.3;
      ctx.stroke();
    }
  }
  ctx.globalAlpha = 1;
};

export const Eye = forwardRef<EyeHandle, {
  className?: string;
  config?: EyeConfig;
  isLeft?: boolean;
}>(({
  className,
  config = DEFAULT_CONFIG,
  isLeft = true,
}, ref) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const targetRef = useRef({ x: 0, y: 0 });
  const configRef = useRef(config);
  configRef.current = config;
  const isLeftRef = useRef(isLeft);
  isLeftRef.current = isLeft;

  useImperativeHandle(ref, () => ({
    setTarget: (x: number, y: number) => {
      targetRef.current = { x, y };
    },
  }));

  const animRef = useRef({
    currentX: 0,
    currentY: 0,
    pupilDilation: 1.0,
    blinkProgress: 0,
    blinkPhase: 0 as number,
    blinkTimer: 0,
    nextBlink: 3 + Math.random() * 4,
    breatheTime: Math.random() * 100,
    saccadeX: 0,
    saccadeY: 0,
    saccadeTimer: 0,
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const logicalSize = DEFAULT_CONFIG.size;
    canvas.width = logicalSize * dpr;
    canvas.height = logicalSize * dpr;
    ctx.scale(dpr, dpr);

    let lastTime = performance.now();
    let frameId: number;

    const loop = (now: number) => {
      const dt = Math.min((now - lastTime) / 1000, 0.1);
      lastTime = now;
      try { draw(ctx, dt); } catch { /* skip frame */ }
      frameId = requestAnimationFrame(loop);
    };

    frameId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frameId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const draw = (ctx: CanvasRenderingContext2D, dt: number) => {
    const anim = animRef.current;
    const cfg = configRef.current;
    const tgt = targetRef.current;
    const left = isLeftRef.current;

    const { size, irisRatio, pupilRatio, parallax, maxOffset } = cfg;
    const cx = size / 2;
    const cy = size / 2;
    const scleraR = size * 0.44;
    const irisR = size * irisRatio;
    const pupilR = size * pupilRatio;

    // --- Animation (identical to before) ---
    const factor = Math.min(1, 8.0 * dt);
    anim.currentX += (tgt.x - anim.currentX) * factor;
    anim.currentY += (tgt.y - anim.currentY) * factor;

    anim.saccadeTimer += dt;
    if (anim.saccadeTimer > 0.3) {
      anim.saccadeTimer = 0;
      const mag = Math.random() < 0.05 ? 0.02 : 0.006;
      anim.saccadeX = (Math.random() - 0.5) * mag * 2;
      anim.saccadeY = (Math.random() - 0.5) * mag * 2;
    } else {
      anim.saccadeX *= 1 - Math.min(1, 6 * dt);
      anim.saccadeY *= 1 - Math.min(1, 6 * dt);
    }

    anim.breatheTime += dt;
    const breathe = Math.sin(anim.breatheTime * 0.2 * TAU) * 0.03;

    if (anim.blinkPhase === 0) {
      anim.blinkTimer += dt;
      anim.blinkProgress = 0;
      if (anim.blinkTimer > anim.nextBlink) {
        anim.blinkPhase = 1;
        anim.blinkTimer = 0;
        anim.nextBlink = 3 + Math.random() * 6;
      }
    } else if (anim.blinkPhase === 1) {
      anim.blinkProgress = Math.min(1, anim.blinkProgress + dt * 10);
      if (anim.blinkProgress >= 1) anim.blinkPhase = 2;
    } else {
      anim.blinkProgress = Math.max(0, anim.blinkProgress - dt * 7);
      if (anim.blinkProgress <= 0) anim.blinkPhase = 0;
    }

    const rawX = (anim.currentX + anim.saccadeX) * maxOffset * size;
    const rawY = (anim.currentY + anim.saccadeY) * maxOffset * size;
    const crossEye = left ? 8 : -8;

    // Seeded RNG — stable per frame so stipple doesn't flicker
    const rng = mulberry32(42);

    // --- Clear (transparent) ---
    ctx.clearRect(0, 0, size, size);

    // --- Sclera (stippled white) ---
    const sDx = rawX * parallax.sclera;
    const sDy = rawY * parallax.sclera;
    const scleraCx = cx + sDx;
    const scleraCy = cy + sDy;

    // Rough sclera outline
    ctx.save();
    drawRoughCircle(ctx, scleraCx, scleraCy, scleraR, 2.5, 120, rng);
    ctx.clip();

    // Sclera fill — stipple dots creating the white eyeball
    ctx.fillStyle = "#d8d8d0";
    drawStipple(ctx, scleraCx, scleraCy, scleraR, 2800, 1.5, rng, 0.3);

    // Denser white near center
    ctx.fillStyle = "#e8e8e4";
    drawStipple(ctx, scleraCx, scleraCy, scleraR * 0.6, 800, 1.8, rng, 0.5);

    // Edge shadow — denser dark dots near rim
    ctx.fillStyle = "#1a1a1a";
    for (let i = 0; i < 600; i++) {
      const a = rng() * TAU;
      const r = scleraR * (0.75 + rng() * 0.25);
      const x = scleraCx + Math.cos(a) * r;
      const y = scleraCy + Math.sin(a) * r;
      ctx.globalAlpha = 0.1 + rng() * 0.25;
      const ds = 1 + rng() * 1.5;
      ctx.fillRect(x, y, ds, ds);
    }
    ctx.globalAlpha = 1;

    // --- Veins (scratchy white lines) ---
    ctx.strokeStyle = "#888880";
    for (let i = 0; i < 10; i++) {
      const angle = (i / 10) * TAU + rng() * 0.4;
      const startR = scleraR * 0.95;
      ctx.beginPath();
      ctx.moveTo(
        scleraCx + Math.cos(angle) * startR,
        scleraCy + Math.sin(angle) * startR
      );
      for (let s = 0; s < 6; s++) {
        const frac = (s + 1) / 6;
        const r = startR - frac * scleraR * 0.35;
        const a = angle + Math.sin(frac * Math.PI * 3) * 0.12 + (rng() - 0.5) * 0.08;
        ctx.lineTo(
          scleraCx + Math.cos(a) * r,
          scleraCy + Math.sin(a) * r
        );
      }
      ctx.lineWidth = 0.3 + rng() * 0.8;
      ctx.globalAlpha = 0.08 + rng() * 0.12;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // --- Iris (crosshatched) ---
    const iDx = rawX * parallax.iris + crossEye;
    const iDy = rawY * parallax.iris;
    const irisCx = cx + iDx;
    const irisCy = cy + iDy;

    // Dark iris base circle
    ctx.fillStyle = "#181818";
    ctx.beginPath();
    ctx.arc(irisCx, irisCy, irisR, 0, TAU);
    ctx.fill();

    // Iris ring — stipple to create the mid-tone
    ctx.fillStyle = "#999990";
    drawStipple(ctx, irisCx, irisCy, irisR, 1200, 1.2, rng, 0.2);

    // Inner glow near pupil
    ctx.fillStyle = "#b0b0a8";
    drawStipple(ctx, irisCx, irisCy, irisR * 0.55, 400, 1.0, rng, 0.6);

    // Crosshatch strokes — the main texture
    ctx.strokeStyle = "#c8c8c0";
    drawCrosshatch(ctx, irisCx, irisCy, pupilR * 1.1, irisR * 0.95, 100, rng);

    // Darker crosshatch overlay for depth
    ctx.strokeStyle = "#404038";
    drawCrosshatch(ctx, irisCx, irisCy, pupilR * 1.3, irisR * 0.7, 40, rng);

    // Iris outer edge ring — dark stroke
    drawRoughCircle(ctx, irisCx, irisCy, irisR, 1.5, 80, rng);
    ctx.strokeStyle = "#2a2a28";
    ctx.lineWidth = 1.8;
    ctx.globalAlpha = 0.7;
    ctx.stroke();
    ctx.globalAlpha = 1;

    // --- Pupil (solid black) ---
    const pDx = rawX * parallax.pupil + crossEye;
    const pDy = rawY * parallax.pupil;
    const dilatedR = pupilR * (anim.pupilDilation + breathe);
    const pupilCx = cx + pDx;
    const pupilCy = cy + pDy;

    ctx.fillStyle = "#000000";
    ctx.beginPath();
    ctx.arc(pupilCx, pupilCy, dilatedR, 0, TAU);
    ctx.fill();

    // Pupil edge stipple — soft transition
    ctx.fillStyle = "#1a1a18";
    for (let i = 0; i < 200; i++) {
      const a = rng() * TAU;
      const r = dilatedR * (0.85 + rng() * 0.25);
      ctx.globalAlpha = 0.2 + rng() * 0.3;
      ctx.fillRect(pupilCx + Math.cos(a) * r, pupilCy + Math.sin(a) * r, 1.2, 1.2);
    }
    ctx.globalAlpha = 1;

    // --- Highlight (rough white smudge) ---
    const hlCx = pupilCx - dilatedR * 0.35;
    const hlCy = pupilCy - dilatedR * 0.35;
    ctx.fillStyle = "#ffffff";
    for (let i = 0; i < 60; i++) {
      const a = rng() * TAU;
      const r = rng() * size * 0.025;
      ctx.globalAlpha = 0.3 + rng() * 0.5;
      const ds = 1 + rng() * 2;
      ctx.fillRect(hlCx + Math.cos(a) * r, hlCy + Math.sin(a) * r, ds, ds);
    }

    // Secondary highlight — scattered dots
    const hl2Cx = pupilCx + dilatedR * 0.25;
    const hl2Cy = pupilCy + dilatedR * 0.2;
    for (let i = 0; i < 15; i++) {
      const a = rng() * TAU;
      const r = rng() * size * 0.01;
      ctx.globalAlpha = 0.15 + rng() * 0.25;
      ctx.fillRect(hl2Cx + Math.cos(a) * r, hl2Cy + Math.sin(a) * r, 1, 1);
    }
    ctx.globalAlpha = 1;

    // --- Scanline overlay ---
    ctx.fillStyle = "#ffffff";
    for (let y = 0; y < size; y += 3) {
      ctx.globalAlpha = 0.015 + Math.sin(y * 0.5) * 0.008;
      ctx.fillRect(0, y, size, 1);
    }
    ctx.globalAlpha = 1;

    // Restore from sclera clip
    ctx.restore();

    // --- Eyelids (blink) ---
    if (anim.blinkProgress > 0.01) {
      const lidTravel = anim.blinkProgress * (scleraR + 4);
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, scleraR, 0, TAU);
      ctx.clip();
      ctx.fillStyle = "#000000";
      ctx.fillRect(0, cy - scleraR - 4, size, lidTravel);
      ctx.fillRect(0, cy + scleraR + 4 - lidTravel, size, lidTravel);
      ctx.restore();
    }
  };

  return (
    <canvas
      ref={canvasRef}
      width={config.size}
      height={config.size}
      className={className}
      style={{ width: config.size / 2, height: config.size / 2 }}
    />
  );
});

Eye.displayName = "Eye";
