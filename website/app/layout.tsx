import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://raspieyes.dev"),
  title: "raspieyes — Interactive Eye Tracking Art",
  description:
    "Open-source Raspberry Pi project that creates lifelike eyes that follow you. Built for Burning Man.",
  icons: {
    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>👁️</text></svg>",
  },
  openGraph: {
    title: "raspieyes",
    description: "Lifelike eyes that follow you. Built with Raspberry Pi.",
    type: "website",
    url: "https://raspieyes.dev",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
