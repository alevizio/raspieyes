"use client";

import { useEffect, useRef, useState } from "react";
import { Eye } from "@/components/eye";
import { FadeIn } from "@/components/fade-in";

const HARDWARE_BOM = [
  { item: "Raspberry Pi 5 (8GB)", price: "$80", note: "Required" },
  { item: "2× Round HDMI Displays (1080×1080)", price: "~$100", note: "Required" },
  { item: "Pi Camera Module 3 NoIR", price: "$35", note: "Required" },
  { item: "USB-C Power Bank (20,000mAh+)", price: "~$30", note: "Portable power" },
  { item: "Pi AI HAT+ (13 TOPS)", price: "~$77", note: "Optional — NPU acceleration" },
  { item: "Pi AI Camera (IMX500)", price: "$70", note: "Optional — on-sensor inference" },
  { item: "USB Webcam with Stereo Mic", price: "~$30", note: "Optional — audio reactivity" },
];

const FEATURES = [
  {
    title: "Face Tracking",
    description: "OpenCV DNN + MediaPipe detect faces and follow them with multi-layer parallax.",
    icon: "👤",
  },
  {
    title: "Depth Reactive",
    description: "Pupil dilates dramatically as you get closer. Constricts when you walk away.",
    icon: "📏",
  },
  {
    title: "Audio Reactive",
    description: "Pulses to bass beats, startles at loud sounds, looks toward noise direction.",
    icon: "🔊",
  },
  {
    title: "Motion Detection",
    description: "Tracks hands, bodies, any movement — not just faces.",
    icon: "🖐️",
  },
  {
    title: "60fps Rendering",
    description: "Smooth parallax animation with predict-to-vsync pipeline on Raspberry Pi.",
    icon: "🎯",
  },
  {
    title: "Open Source",
    description: "MIT licensed. Build your own for Burning Man, Halloween, or art installations.",
    icon: "💻",
  },
];

const REFERENCES = [
  { name: "opencv/opencv", description: "DNN face detection, MOG2 background subtraction", url: "https://github.com/opencv/opencv" },
  { name: "google-ai-edge/mediapipe", description: "Face detection and landmark tracking", url: "https://github.com/google-ai-edge/mediapipe" },
  { name: "pageauc/motion-track", description: "Motion tracking with OpenCV on Raspberry Pi", url: "https://github.com/pageauc/motion-track" },
  { name: "pageauc/speed-camera", description: "Speed camera using motion tracking", url: "https://github.com/pageauc/speed-camera" },
  { name: "Uberi/MotionTracking", description: "Real-time motion tracking algorithms", url: "https://github.com/Uberi/MotionTracking" },
];

const BADGES = [
  { label: "Open Source", icon: "⚡" },
  { label: "60fps", icon: "🎯" },
  { label: "MIT Licensed", icon: "📜" },
  { label: "Raspberry Pi 5", icon: "🍓" },
];

const FAQ = [
  {
    q: "How long does the battery last?",
    a: "With a 20,000mAh power bank, you get about 5.5–6 hours. For a full Burning Man night (8–10+ hours), we recommend two power banks and swapping halfway through.",
  },
  {
    q: "Does it work in the dark?",
    a: "Yes. The Pi Camera Module 3 NoIR has no infrared filter, so it sees in near-darkness — especially with IR LED illumination. The motion detector also works at any light level.",
  },
  {
    q: "Can I use custom eye designs?",
    a: "Yes. Drop sclera.png, iris.png, and pupil.png into the assets/ folder and the renderer uses them as parallax layers instead of the procedural eye. You can also set RENDER_MODE=video in config.txt to loop mp4 videos instead.",
  },
  {
    q: "What displays work?",
    a: "Any HDMI display works, but the project is designed for round 1080×1080 screens (Waveshare WS070Round). The round shape makes the eyeball illusion convincing.",
  },
  {
    q: "Do I need the AI HAT+?",
    a: "No — it's optional. The Pi 5 CPU handles face detection fine at 15fps with OpenCV DNN. The AI HAT+ (13 TOPS NPU) lets you run detection at 30–60fps for smoother tracking.",
  },
  {
    q: "Can it detect multiple people?",
    a: "Yes. The centroid tracker follows the largest / closest person, but detects all movement in frame. When someone new approaches, the eye smoothly transitions to track them.",
  },
  {
    q: "Is it TSA / flight approved?",
    a: "Yes. Power banks under 100Wh (≈27,000mAh) are allowed in carry-on luggage. The 20,000mAh Baseus at 74Wh is well under the limit.",
  },
  {
    q: "Can I test without a Raspberry Pi?",
    a: "Yes! Run python3 eye_renderer.py --mouse --windowed on any Mac or Linux machine to test with mouse tracking, or --test-webcam for camera tracking.",
  },
];

const STEPS = [
  {
    step: "1",
    title: "Flash Raspberry Pi OS",
    desc: "Flash Pi OS Bookworm 64-bit to a microSD card. Enable SSH, set hostname to raspieyes.",
  },
  {
    step: "2",
    title: "Connect Hardware",
    desc: "Plug both round HDMI screens, camera module (CSI ribbon), and power.",
  },
  {
    step: "3",
    title: "Clone & Install",
    code: "git clone https://github.com/alevizio/raspieyes.git\ncd raspieyes && bash setup.sh",
  },
  {
    step: "4",
    title: "Configure",
    desc: "Edit config.txt — set RENDER_MODE=parallax, TRACKING=yes, choose your eye color.",
  },
  {
    step: "5",
    title: "Reboot & Enjoy",
    code: "sudo reboot",
    desc: "Eyes start on boot. Walk in front of the camera.",
  },
];

const FaqItem = ({ q, a, open, onClick }: { q: string; a: string; open: boolean; onClick: () => void }) => (
  <button
    onClick={onClick}
    className="w-full text-left py-5 border-b border-zinc-800/40 group"
  >
    <div className="flex items-start justify-between gap-4">
      <h3 className="font-medium text-zinc-200 group-hover:text-white transition-colors">
        {q}
      </h3>
      <span
        className={`flex-shrink-0 text-zinc-600 transition-transform duration-300 mt-0.5 ${open ? "rotate-45" : ""}`}
      >
        +
      </span>
    </div>
    <div
      className={`overflow-hidden transition-all duration-300 ${open ? "max-h-40 opacity-100 mt-3" : "max-h-0 opacity-0"}`}
    >
      <p className="text-zinc-500 text-sm leading-relaxed pr-8">{a}</p>
    </div>
  </button>
);

const FaqSection = () => {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <section className="py-24 px-6 max-w-3xl mx-auto">
      <FadeIn>
        <h2 className="text-4xl md:text-5xl font-bold text-center mb-4 tracking-tight">
          Common <em className="italic text-blue-400 font-[Datatype]">Questions</em>
        </h2>
        <p className="text-zinc-500 text-center text-lg mb-14 max-w-xl mx-auto">
          Everything else you might want to know.
        </p>
      </FadeIn>

      <FadeIn>
        <div>
          {FAQ.map((item, i) => (
            <FaqItem
              key={i}
              q={item.q}
              a={item.a}
              open={openIndex === i}
              onClick={() => setOpenIndex(openIndex === i ? null : i)}
            />
          ))}
        </div>
      </FadeIn>
    </section>
  );
};

export default function Home() {
  const eyeLeftRef = useRef<{ setTarget: (x: number, y: number) => void }>(null);
  const eyeRightRef = useRef<{ setTarget: (x: number, y: number) => void }>(null);

  useEffect(() => {
    const handleMouse = (e: MouseEvent) => {
      const nx = (e.clientX / window.innerWidth - 0.5) * 2;
      const ny = (e.clientY / window.innerHeight - 0.5) * 2;
      eyeLeftRef.current?.setTarget(nx, ny);
      eyeRightRef.current?.setTarget(nx, ny);
    };
    window.addEventListener("mousemove", handleMouse);
    return () => window.removeEventListener("mousemove", handleMouse);
  }, []);

  return (
    <main className="min-h-screen text-white">
      {/* ── Hero ── */}
      <section className="h-screen flex flex-col items-center justify-center relative overflow-hidden">
        {/* Radial glow behind eyes */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(59,130,246,0.06),transparent_60%)]" />

        <div className="relative flex items-center gap-6 md:gap-14 mb-12">
          <Eye ref={eyeLeftRef} isLeft={true} />
          <Eye ref={eyeRightRef} isLeft={false} />
        </div>

        <div className="relative text-center px-6">
          <h1 className="text-5xl md:text-7xl lg:text-8xl font-bold tracking-tight mb-4">
            raspi<em className="not-italic text-blue-400">eyes</em>
          </h1>
          <p className="text-lg md:text-2xl text-zinc-500 max-w-lg mx-auto leading-relaxed">
            Lifelike eyes that follow you.{" "}
            <span className="text-zinc-400">Built with Raspberry Pi.</span>
          </p>
          <div className="mt-8 flex flex-col sm:flex-row gap-4 justify-center">
            <a
              href="https://github.com/alevizio/raspieyes"
              className="px-8 py-3.5 bg-blue-500 text-white rounded-full font-medium hover:bg-blue-400 transition-all duration-300 hover:shadow-[0_0_24px_rgba(59,130,246,0.3)]"
            >
              View on GitHub
            </a>
            <a
              href="#build"
              className="px-8 py-3.5 border border-zinc-700/60 rounded-full font-medium text-zinc-300 hover:border-zinc-500 hover:text-white transition-all duration-300"
            >
              Build Your Own
            </a>
          </div>
        </div>

        <p className="absolute bottom-6 text-xs text-zinc-600 animate-pulse">
          Move your mouse — the eyes are watching
        </p>
      </section>

      {/* ── Trust Badges ── */}
      <FadeIn className="flex flex-wrap justify-center gap-3 px-6 -mt-8 mb-24">
        {BADGES.map((b) => (
          <span
            key={b.label}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-zinc-800/60 bg-zinc-900/40 text-sm text-zinc-400 backdrop-blur-sm"
          >
            <span>{b.icon}</span>
            {b.label}
          </span>
        ))}
      </FadeIn>

      {/* ── Features ── */}
      <section className="py-24 px-6 max-w-5xl mx-auto">
        <FadeIn>
          <h2 className="text-4xl md:text-5xl font-bold text-center mb-4 tracking-tight">
            What it <em className="italic text-blue-400 font-[Datatype]">does</em>
          </h2>
          <p className="text-zinc-500 text-center text-lg mb-16 max-w-xl mx-auto">
            Real-time rendered eyes that react to everything around them.
          </p>
        </FadeIn>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {FEATURES.map((f, i) => (
            <FadeIn key={f.title} delay={i * 80}>
              <div className="group p-7 rounded-2xl bg-zinc-900/40 border border-zinc-800/50 hover:border-zinc-600/60 transition-all duration-300">
                <div className="w-11 h-11 rounded-xl bg-zinc-800/60 flex items-center justify-center text-2xl mb-4 group-hover:bg-zinc-700/60 transition-colors">
                  {f.icon}
                </div>
                <h3 className="text-base font-semibold mb-2 text-zinc-100">
                  {f.title}
                </h3>
                <p className="text-zinc-500 text-sm leading-relaxed">
                  {f.description}
                </p>
              </div>
            </FadeIn>
          ))}
        </div>
      </section>

      {/* ── Build Guide ── */}
      <section id="build" className="py-24 px-6 max-w-4xl mx-auto">
        <FadeIn>
          <h2 className="text-4xl md:text-5xl font-bold text-center mb-4 tracking-tight">
            Build Your <em className="italic text-blue-400 font-[Datatype]">Own</em>
          </h2>
          <p className="text-zinc-500 text-center text-lg mb-20 max-w-xl mx-auto">
            Everything you need to make a pair of tracking eyes.
          </p>
        </FadeIn>

        {/* Hardware BOM */}
        <FadeIn className="mb-20">
          <h3 className="text-xl font-semibold mb-6 text-zinc-200">Hardware</h3>
          <div className="rounded-2xl bg-zinc-900/30 border border-zinc-800/50 overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-800/60">
                  <th className="py-3.5 px-5 text-zinc-500 font-medium text-xs uppercase tracking-wider">Part</th>
                  <th className="py-3.5 px-5 text-zinc-500 font-medium text-xs uppercase tracking-wider">Price</th>
                  <th className="py-3.5 px-5 text-zinc-500 font-medium text-xs uppercase tracking-wider hidden sm:table-cell">Note</th>
                </tr>
              </thead>
              <tbody>
                {HARDWARE_BOM.map((h, i) => (
                  <tr
                    key={h.item}
                    className={`border-b border-zinc-800/30 ${i % 2 === 0 ? "bg-zinc-900/20" : ""}`}
                  >
                    <td className="py-3 px-5 text-zinc-200">{h.item}</td>
                    <td className="py-3 px-5 text-zinc-400 font-mono text-xs">{h.price}</td>
                    <td className="py-3 px-5 text-zinc-600 text-xs hidden sm:table-cell">{h.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </FadeIn>

        {/* Quick Start — Timeline */}
        <FadeIn>
          <h3 className="text-xl font-semibold mb-8 text-zinc-200">Quick Start</h3>
          <div className="relative pl-8 border-l border-zinc-800/60">
            {STEPS.map((s, i) => (
              <FadeIn key={s.step} delay={i * 100}>
                <div className="relative mb-8 last:mb-0">
                  {/* Circle on timeline */}
                  <span className="absolute -left-[calc(2rem+10px)] w-5 h-5 rounded-full bg-blue-500/20 border-2 border-blue-500/50 flex items-center justify-center">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                  </span>
                  <div className="p-5 rounded-xl bg-zinc-900/30 border border-zinc-800/40">
                    <h4 className="font-medium mb-1.5 text-zinc-100">
                      <span className="text-blue-400/70 mr-2 text-sm">0{s.step}</span>
                      {s.title}
                    </h4>
                    {s.desc && (
                      <p className="text-zinc-500 text-sm leading-relaxed">{s.desc}</p>
                    )}
                    {s.code && (
                      <pre className="mt-3 p-3.5 rounded-lg bg-black/60 text-xs text-green-400/80 overflow-x-auto font-mono leading-relaxed">
                        {s.code}
                      </pre>
                    )}
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </FadeIn>
      </section>

      {/* ── References ── */}
      <section className="py-24 px-6 max-w-4xl mx-auto">
        <FadeIn>
          <h2 className="text-4xl md:text-5xl font-bold text-center mb-4 tracking-tight">
            Built <em className="italic text-blue-400 font-[Datatype]">With</em>
          </h2>
          <p className="text-zinc-500 text-center text-lg mb-12 max-w-xl mx-auto">
            Open source projects that made this possible.
          </p>
        </FadeIn>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {REFERENCES.map((r, i) => (
            <FadeIn key={r.name} delay={i * 60}>
              <a
                href={r.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-start gap-3 p-5 rounded-xl bg-zinc-900/30 border border-zinc-800/40 hover:border-zinc-600/50 transition-all duration-300"
              >
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-mono text-blue-400 group-hover:text-blue-300 transition-colors">
                    {r.name}
                  </span>
                  <span className="block text-zinc-500 text-xs mt-1.5 leading-relaxed">
                    {r.description}
                  </span>
                </div>
                <span className="text-zinc-600 group-hover:text-zinc-400 transition-colors mt-0.5">
                  ↗
                </span>
              </a>
            </FadeIn>
          ))}
        </div>
      </section>

      {/* ── FAQ ── */}
      <FaqSection />

      {/* ── Footer CTA ── */}
      <section className="py-32 px-6 relative">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(59,130,246,0.04),transparent_60%)]" />
        <FadeIn className="relative text-center">
          <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-6">
            Ready to <em className="italic text-blue-400 font-[Datatype]">build</em>?
          </h2>
          <p className="text-zinc-500 text-lg mb-10 max-w-md mx-auto">
            Clone the repo, flash a Pi, and bring your art to life.
          </p>
          <a
            href="https://github.com/alevizio/raspieyes"
            className="inline-flex items-center gap-2 px-10 py-4 bg-blue-500 text-white rounded-full font-medium text-lg hover:bg-blue-400 transition-all duration-300 hover:shadow-[0_0_32px_rgba(59,130,246,0.3)]"
          >
            ⭐ Star on GitHub
          </a>
        </FadeIn>
      </section>

      {/* ── Footer ── */}
      <footer className="py-16 px-6 border-t border-zinc-800/40 text-center">
        <p className="text-zinc-500 text-sm">
          Built for{" "}
          <span className="text-orange-400/80">Burning Man 2026</span> by{" "}
          <a
            href="https://github.com/alevizio"
            className="text-zinc-300 hover:text-white transition-colors"
          >
            Alejandro
          </a>
        </p>
        <p className="mt-3 text-zinc-600 text-xs">
          <a
            href="https://github.com/alevizio/raspieyes"
            className="hover:text-zinc-400 transition-colors"
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
