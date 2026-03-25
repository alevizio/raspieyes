import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "raspieyes — Lifelike eyes that follow you";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          background: "#131314",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        {/* Two eye circles */}
        <div style={{ display: "flex", gap: 64, marginBottom: 48 }}>
          {/* Left eye */}
          <div
            style={{
              width: 180,
              height: 180,
              borderRadius: "50%",
              background: "radial-gradient(circle at 40% 35%, #6db3f2 0%, #3a7bd5 40%, #1a3d6e 70%, #0a1a30 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 0 60px rgba(59,130,246,0.3), inset 0 0 30px rgba(0,0,0,0.5)",
              border: "8px solid #8a827a",
            }}
          >
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: "50%",
                background: "#050505",
                boxShadow: "0 0 20px rgba(0,0,0,0.8)",
              }}
            />
          </div>
          {/* Right eye */}
          <div
            style={{
              width: 180,
              height: 180,
              borderRadius: "50%",
              background: "radial-gradient(circle at 60% 35%, #6db3f2 0%, #3a7bd5 40%, #1a3d6e 70%, #0a1a30 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 0 60px rgba(59,130,246,0.3), inset 0 0 30px rgba(0,0,0,0.5)",
              border: "8px solid #8a827a",
            }}
          >
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: "50%",
                background: "#050505",
                boxShadow: "0 0 20px rgba(0,0,0,0.8)",
              }}
            />
          </div>
        </div>

        {/* Title */}
        <div
          style={{
            fontSize: 72,
            fontWeight: 700,
            color: "#E3E3E3",
            letterSpacing: "-0.02em",
            display: "flex",
          }}
        >
          raspi
          <span style={{ color: "#004C7C" }}>eyes</span>
        </div>

        {/* Tagline */}
        <div
          style={{
            fontSize: 24,
            color: "#9aa0a6",
            marginTop: 12,
          }}
        >
          Lifelike eyes that follow you. Built with Raspberry Pi.
        </div>

        {/* URL */}
        <div
          style={{
            fontSize: 16,
            color: "#444649",
            marginTop: 24,
          }}
        >
          raspieyes.dev
        </div>
      </div>
    ),
    { ...size }
  );
}
