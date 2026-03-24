import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "raspieyes — Interactive Eye Tracking Art",
  description:
    "Open-source Raspberry Pi project that creates lifelike eyes that follow you. Built for Burning Man.",
  openGraph: {
    title: "raspieyes",
    description: "Lifelike eyes that follow you. Built with Raspberry Pi.",
    type: "website",
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
