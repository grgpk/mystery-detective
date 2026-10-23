import type { Metadata, Viewport } from "next";
import { Libre_Baskerville, Special_Elite } from "next/font/google";
import "./globals.css";

const typewriter = Special_Elite({ variable: "--font-typewriter", weight: "400", subsets: ["latin"] });
const body = Libre_Baskerville({ variable: "--font-body", weight: ["400", "700"], style: ["normal", "italic"], subsets: ["latin"] });

export const metadata: Metadata = {
  title: "The Last Alibi",
  description: "A new golden-age murder mystery every time you press Play, and the suspects talk back.",
};

export const viewport: Viewport = {
  themeColor: "#1c1814",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${typewriter.variable} ${body.variable} antialiased`}>
      <body>{children}</body>
    </html>
  );
}
