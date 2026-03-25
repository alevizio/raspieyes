"use client";

import { useEffect, useRef } from "react";

const TAU = Math.PI * 2;

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

export const Eye = ({
  className,
  config = DEFAULT_CONFIG,
  targetX = 0,
  targetY = 0,
  isLeft = true,
}: {
  className?: string;
  config?: EyeConfig;
  targetX?: number;
  targetY?: number;
  isLeft?: boolean;
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Store props in refs so the rAF loop never restarts
  const targetRef = useRef({ x: targetX, y: targetY });
  targetRef.current = { x: targetX, y: targetY };

  const configRef = useRef(config);
  configRef.current = config;

  const isLeftRef = useRef(isLeft);
  isLeftRef.current = isLeft;

  const animRef = useRef({
    currentX: 0,
    currentY: 0,
    pupilDilation: 1.0,
    blinkProgress: 0,
    blinkTimer: 0,
    nextBlink: 3 + Math.random() * 4,
    breatheTime: Math.random() * 100,
    saccadeX: 0,
    saccadeY: 0,
    saccadeTimer: 0,
  });

  // Single rAF loop that never restarts — reads from refs
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // DPI scaling
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

      try {
        draw(ctx, dt);
      } catch {
        // Skip frame on error, don't kill the loop
      }

      frameId = requestAnimationFrame(loop);
    };

    frameId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frameId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Never restarts — reads current values from refs

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

    // Lerp toward target
    const factor = Math.min(1, 8.0 * dt);
    anim.currentX += (tgt.x - anim.currentX) * factor;
    anim.currentY += (tgt.y - anim.currentY) * factor;

    // Micro-saccades
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

    // Breathing pupil
    anim.breatheTime += dt;
    const breathe = Math.sin(anim.breatheTime * 0.2 * TAU) * 0.03;

    // Blink
    anim.blinkTimer += dt;
    if (anim.blinkProgress <= 0 && anim.blinkTimer > anim.nextBlink) {
      anim.blinkProgress = 0.01;
      anim.blinkTimer = 0;
      anim.nextBlink = 2.5 + Math.random() * 5;
    }
    if (anim.blinkProgress > 0 && anim.blinkProgress < 1) {
      anim.blinkProgress += dt * 8;
    } else if (anim.blinkProgress >= 1) {
      anim.blinkProgress -= dt * 6;
      if (anim.blinkProgress <= 0) anim.blinkProgress = 0;
    }

    // Offsets
    const rawX = (anim.currentX + anim.saccadeX) * maxOffset * size;
    const rawY = (anim.currentY + anim.saccadeY) * maxOffset * size;
    const crossEye = left ? 8 : -8;

    // Clear
    ctx.clearRect(0, 0, size, size);

    // --- Sclera ---
    const sDx = rawX * parallax.sclera;
    const sDy = rawY * parallax.sclera;
    const scleraGrad = ctx.createRadialGradient(
      cx + sDx - scleraR * 0.25,
      cy + sDy - scleraR * 0.3,
      scleraR * 0.1,
      cx + sDx,
      cy + sDy,
      scleraR
    );
    scleraGrad.addColorStop(0, "#ffffff");
    scleraGrad.addColorStop(0.6, cfg.scleraColor);
    scleraGrad.addColorStop(0.85, "#c8c0b8");
    scleraGrad.addColorStop(1, "#8a827a");
    ctx.beginPath();
    ctx.arc(cx + sDx, cy + sDy, scleraR, 0, TAU);
    ctx.fillStyle = scleraGrad;
    ctx.fill();

    // Sclera shadow ring
    const shadowGrad = ctx.createRadialGradient(
      cx + sDx, cy + sDy, irisR * 0.9,
      cx + sDx, cy + sDy, irisR * 1.4
    );
    shadowGrad.addColorStop(0, "rgba(10,5,15,0.5)");
    shadowGrad.addColorStop(1, "rgba(10,5,15,0)");
    ctx.beginPath();
    ctx.arc(cx + sDx, cy + sDy, irisR * 1.4, 0, TAU);
    ctx.fillStyle = shadowGrad;
    ctx.fill();

    // Veins
    ctx.save();
    ctx.globalAlpha = 0.15;
    for (let i = 0; i < 8; i++) {
      const angle = (i / 8) * TAU + 0.3;
      const startR = scleraR * 0.75;
      ctx.beginPath();
      ctx.moveTo(
        cx + sDx + Math.cos(angle) * startR,
        cy + sDy + Math.sin(angle) * startR
      );
      for (let s = 0; s < 5; s++) {
        const frac = s / 5;
        const r = startR - frac * scleraR * 0.3;
        const a = angle + Math.sin(frac * Math.PI * 2) * 0.15;
        ctx.lineTo(
          cx + sDx + Math.cos(a) * r,
          cy + sDy + Math.sin(a) * r
        );
      }
      ctx.strokeStyle = "#b03030";
      ctx.lineWidth = 1.5 - i * 0.1;
      ctx.stroke();
    }
    ctx.restore();

    // --- Iris ---
    const iDx = rawX * parallax.iris + crossEye;
    const iDy = rawY * parallax.iris;
    const irisGrad = ctx.createRadialGradient(
      cx + iDx, cy + iDy, pupilR * 0.8,
      cx + iDx, cy + iDy, irisR
    );
    irisGrad.addColorStop(0, cfg.irisColors[2]);
    irisGrad.addColorStop(0.4, cfg.irisColors[1]);
    irisGrad.addColorStop(0.75, cfg.irisColors[0]);
    irisGrad.addColorStop(1, "#0a1a30");
    ctx.beginPath();
    ctx.arc(cx + iDx, cy + iDy, irisR, 0, TAU);
    ctx.fillStyle = irisGrad;
    ctx.fill();

    // Iris fibers
    ctx.save();
    ctx.globalAlpha = 0.3;
    for (let i = 0; i < 60; i++) {
      const angle = (i / 60) * TAU;
      const innerR = pupilR * 1.1 + Math.random() * irisR * 0.1;
      const outerR = irisR * (0.6 + Math.random() * 0.35);
      ctx.beginPath();
      ctx.moveTo(
        cx + iDx + Math.cos(angle) * innerR,
        cy + iDy + Math.sin(angle) * innerR
      );
      ctx.lineTo(
        cx + iDx + Math.cos(angle + 0.02) * outerR,
        cy + iDy + Math.sin(angle + 0.02) * outerR
      );
      const brightness = 120 + Math.floor(Math.random() * 100);
      ctx.strokeStyle = `rgba(${brightness},${brightness + 40},${brightness + 80},0.4)`;
      ctx.lineWidth = 1 + Math.random();
      ctx.stroke();
    }
    ctx.restore();

    // Iris gloss
    const glossGrad = ctx.createRadialGradient(
      cx + iDx - irisR * 0.2, cy + iDy - irisR * 0.25, 0,
      cx + iDx - irisR * 0.2, cy + iDy - irisR * 0.25, irisR * 0.5
    );
    glossGrad.addColorStop(0, "rgba(255,255,255,0.15)");
    glossGrad.addColorStop(1, "rgba(255,255,255,0)");
    ctx.beginPath();
    ctx.arc(cx + iDx, cy + iDy, irisR, 0, TAU);
    ctx.fillStyle = glossGrad;
    ctx.fill();

    // --- Pupil ---
    const pDx = rawX * parallax.pupil + crossEye;
    const pDy = rawY * parallax.pupil;
    const dilatedR = pupilR * (anim.pupilDilation + breathe);
    const pupilGrad = ctx.createRadialGradient(
      cx + pDx, cy + pDy, 0,
      cx + pDx, cy + pDy, dilatedR
    );
    pupilGrad.addColorStop(0, cfg.pupilColor);
    pupilGrad.addColorStop(0.8, cfg.pupilColor);
    pupilGrad.addColorStop(1, "rgba(5,5,5,0)");
    ctx.beginPath();
    ctx.arc(cx + pDx, cy + pDy, dilatedR, 0, TAU);
    ctx.fillStyle = pupilGrad;
    ctx.fill();

    // Specular highlights
    const hlR = size * 0.035;
    const hlX = cx + pDx - dilatedR * 0.3;
    const hlY = cy + pDy - dilatedR * 0.3;
    const hlGrad = ctx.createRadialGradient(hlX, hlY, 0, hlX, hlY, hlR);
    hlGrad.addColorStop(0, cfg.highlightColor);
    hlGrad.addColorStop(0.6, "rgba(255,255,255,0.5)");
    hlGrad.addColorStop(1, "rgba(255,255,255,0)");
    ctx.beginPath();
    ctx.arc(hlX, hlY, hlR, 0, TAU);
    ctx.fillStyle = hlGrad;
    ctx.fill();

    // Secondary highlight
    const hl2X = cx + pDx + dilatedR * 0.2;
    const hl2Y = cy + pDy + dilatedR * 0.25;
    const hl2R = hlR * 0.4;
    ctx.beginPath();
    ctx.arc(hl2X, hl2Y, hl2R, 0, TAU);
    ctx.fillStyle = "rgba(255,255,255,0.4)";
    ctx.fill();

    // --- Full-eye gloss overlay ---
    const glossOverlay = ctx.createRadialGradient(
      cx - scleraR * 0.2, cy - scleraR * 0.25, scleraR * 0.05,
      cx - scleraR * 0.2, cy - scleraR * 0.25, scleraR * 0.8
    );
    glossOverlay.addColorStop(0, "rgba(255,255,255,0.18)");
    glossOverlay.addColorStop(0.5, "rgba(255,255,255,0.05)");
    glossOverlay.addColorStop(1, "rgba(255,255,255,0)");
    ctx.beginPath();
    ctx.arc(cx, cy, scleraR, 0, TAU);
    ctx.fillStyle = glossOverlay;
    ctx.fill();

    // --- Eyelids (blink) ---
    if (anim.blinkProgress > 0.01) {
      const lidTravel = anim.blinkProgress * (size / 2 + 10);
      ctx.fillStyle = "#0a0806";
      ctx.beginPath();
      ctx.rect(0, 0, size, cy - scleraR + lidTravel);
      ctx.fill();
      ctx.beginPath();
      ctx.rect(0, cy + scleraR - lidTravel, size, size);
      ctx.fill();
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
};
