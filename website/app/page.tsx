"use client";

import { useEffect, useRef } from "react";
import { Eye } from "@/components/eye";

const HARDWARE_BOM = [
  { item: "Raspberry Pi 5 (8GB)", price: "$80", link: "https://www.raspberrypi.com/products/raspberry-pi-5/" },
  { item: "Pi Camera Module 3 NoIR", price: "$35", link: "https://www.raspberrypi.com/products/camera-module-3/" },
  { item: "2x Round HDMI Displays (1080x1080)", price: "~$50 each", link: "#" },
  { item: "Pi AI HAT+ (13 TOPS)", price: "~$77", link: "https://www.raspberrypi.com/products/ai-hat-plus/" },
  { item: "Pi AI Camera (IMX500)", price: "$70", link: "https://www.raspberrypi.com/products/ai-camera/" },
  { item: "USB-C Power Bank (20,000mAh+)", price: "~$30-40", link: "#" },
  { item: "USB Webcam with Stereo Mic", price: "~$30", link: "#" },
];

const FEATURES = [
  {
    title: "Face Tracking",
    description: "OpenCV DNN + MediaPipe detect faces and follow them with parallax layers.",
    icon: "👤",
  },
  {
    title: "Depth Reactive",
    description: "Pupil dilates as you get closer. Constricts when you walk away.",
    icon: "📏",
  },
  {
    title: "Audio Reactive",
    description: "Pulses to bass beats, startles at loud sounds, looks toward noise.",
    icon: "🔊",
  },
  {
    title: "Motion Detection",
    description: "Tracks hands, bodies, any movement — not just faces.",
    icon: "🖐️",
  },
  {
    title: "60fps Rendering",
    description: "Smooth parallax eye animation with predict-to-vsync pipeline.",
    icon: "🎯",
  },
  {
    title: "Open Source",
    description: "MIT licensed. Build your own for Burning Man, Halloween, or art installations.",
    icon: "💻",
  },
];

const REFERENCES = [
  {
    name: "pageauc/motion-track",
    description: "Motion tracking with OpenCV on Raspberry Pi",
    url: "https://github.com/pageauc/motion-track",
  },
  {
    name: "pageauc/speed-camera",
    description: "Speed camera using motion tracking and OpenCV",
    url: "https://github.com/pageauc/speed-camera",
  },
  {
    name: "Uberi/MotionTracking",
    description: "Real-time motion tracking algorithms",
    url: "https://github.com/Uberi/MotionTracking",
  },
  {
    name: "opencv/opencv",
    description: "Computer vision library — DNN face detection, MOG2 background subtraction",
    url: "https://github.com/opencv/opencv",
  },
  {
    name: "google-ai-edge/mediapipe",
    description: "Face detection and landmark tracking",
    url: "https://github.com/google-ai-edge/mediapipe",
  },
];

export default function Home() {
  // Use refs instead of state — no React re-renders on mouse move
  const mouseRef = useRef({ x: 0, y: 0 });
  const eyeLeftRef = useRef<{ setTarget: (x: number, y: number) => void }>(null);
  const eyeRightRef = useRef<{ setTarget: (x: number, y: number) => void }>(null);

  useEffect(() => {
    const handleMouse = (e: MouseEvent) => {
      const nx = (e.clientX / window.innerWidth - 0.5) * 2;
      const ny = (e.clientY / window.innerHeight - 0.5) * 2;
      // Update refs directly — no re-render
      eyeLeftRef.current?.setTarget(nx, ny);
      eyeRightRef.current?.setTarget(nx, ny);
    };
    window.addEventListener("mousemove", handleMouse);
    return () => window.removeEventListener("mousemove", handleMouse);
  }, []);

  return (
    <main className="min-h-screen bg-black text-white">
      {/* Hero — Full-screen eyes */}
      <section className="h-screen flex flex-col items-center justify-center relative overflow-hidden">
        <div className="flex items-center gap-8 md:gap-16">
          <Eye ref={eyeLeftRef} isLeft={true} />
          <Eye ref={eyeRightRef} isLeft={false} />
        </div>
        <div className="absolute bottom-12 text-center">
          <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-3">
            raspi<span className="text-blue-400">eyes</span>
          </h1>
          <p className="text-lg md:text-xl text-zinc-400 max-w-md mx-auto">
            Lifelike eyes that follow you. Built with Raspberry Pi.
          </p>
          <div className="mt-6 flex gap-4 justify-center">
            <a
              href="https://github.com/alevizio/raspieyes"
              className="px-6 py-3 bg-white text-black rounded-full font-medium hover:bg-zinc-200 transition-colors"
            >
              View on GitHub
            </a>
            <a
              href="#build"
              className="px-6 py-3 border border-zinc-700 rounded-full font-medium hover:border-zinc-500 transition-colors"
            >
              Build Your Own
            </a>
          </div>
        </div>
        <p className="absolute bottom-4 text-xs text-zinc-600">
          Move your mouse — the eyes are watching
        </p>
      </section>

      {/* Features */}
      <section className="py-24 px-6 max-w-5xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-16">
          What it does
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="p-6 rounded-2xl bg-zinc-900/50 border border-zinc-800"
            >
              <span className="text-3xl">{f.icon}</span>
              <h3 className="text-lg font-semibold mt-3 mb-2">{f.title}</h3>
              <p className="text-zinc-400 text-sm leading-relaxed">
                {f.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Build Guide */}
      <section id="build" className="py-24 px-6 max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-4">
          Build Your Own
        </h2>
        <p className="text-zinc-400 text-center mb-16 max-w-2xl mx-auto">
          Everything you need to create your own pair of tracking eyes
          for Burning Man, Halloween, or any art installation.
        </p>

        {/* Hardware */}
        <h3 className="text-xl font-semibold mb-6">Hardware</h3>
        <div className="overflow-x-auto mb-12">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="py-3 pr-4 text-zinc-400 font-medium">Part</th>
                <th className="py-3 pr-4 text-zinc-400 font-medium">Price</th>
              </tr>
            </thead>
            <tbody>
              {HARDWARE_BOM.map((h) => (
                <tr key={h.item} className="border-b border-zinc-800/50">
                  <td className="py-3 pr-4">{h.item}</td>
                  <td className="py-3 pr-4 text-zinc-400">{h.price}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Setup Steps */}
        <h3 className="text-xl font-semibold mb-6">Quick Start</h3>
        <div className="space-y-6">
          {[
            {
              step: "1",
              title: "Flash Raspberry Pi OS",
              desc: "Flash Raspberry Pi OS Bookworm 64-bit to a microSD card. Enable SSH.",
            },
            {
              step: "2",
              title: "Connect Hardware",
              desc: "Plug in both round HDMI screens, camera module (CSI ribbon cable), and power.",
            },
            {
              step: "3",
              title: "Clone & Install",
              code: "git clone https://github.com/alevizio/raspieyes.git\ncd raspieyes && bash setup.sh",
            },
            {
              step: "4",
              title: "Configure",
              desc: "Edit config.txt to set RENDER_MODE=parallax, TRACKING=yes, and your preferred eye color.",
            },
            {
              step: "5",
              title: "Reboot & Enjoy",
              code: "sudo reboot",
              desc: "The eyes start automatically on boot. Walk in front of the camera!",
            },
          ].map((s) => (
            <div
              key={s.step}
              className="flex gap-4 p-4 rounded-xl bg-zinc-900/30 border border-zinc-800/50"
            >
              <span className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full bg-blue-500/20 text-blue-400 text-sm font-bold">
                {s.step}
              </span>
              <div>
                <h4 className="font-medium mb-1">{s.title}</h4>
                {s.desc && (
                  <p className="text-zinc-400 text-sm">{s.desc}</p>
                )}
                {s.code && (
                  <pre className="mt-2 p-3 rounded-lg bg-black text-sm text-green-400 overflow-x-auto">
                    {s.code}
                  </pre>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* References */}
      <section className="py-24 px-6 max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-4">
          Built With
        </h2>
        <p className="text-zinc-400 text-center mb-12 max-w-2xl mx-auto">
          Open source projects that made this possible.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {REFERENCES.map((r) => (
            <a
              key={r.name}
              href={r.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex flex-col p-4 rounded-xl bg-zinc-900/30 border border-zinc-800/50 hover:border-zinc-600 transition-colors"
            >
              <span className="text-sm font-mono text-blue-400">{r.name}</span>
              <span className="text-zinc-500 text-xs mt-1">{r.description}</span>
            </a>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-zinc-800 text-center text-zinc-500 text-sm">
        <p>
          Built for{" "}
          <span className="text-orange-400">Burning Man 2026</span> by{" "}
          <a
            href="https://github.com/alevizio"
            className="text-zinc-300 hover:text-white transition-colors"
          >
            Alejandro
          </a>
        </p>
        <p className="mt-2">
          <a
            href="https://github.com/alevizio/raspieyes"
            className="hover:text-white transition-colors"
          >
            GitHub
          </a>
          {" · "}
          MIT License
        </p>
      </footer>
    </main>
  );
}
