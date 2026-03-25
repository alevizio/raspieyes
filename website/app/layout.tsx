import type { Metadata } from "next";
import { Noto_Sans } from "next/font/google";
import "./globals.css";

const notoSans = Noto_Sans({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

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
      <head>
        {/* Datatype font — not on next/font/google, load via CSS */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Datatype:wght@100..900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className={`${notoSans.variable} antialiased`}>{children}</body>
    </html>
  );
}
