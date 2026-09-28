import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@mosaic/design/tokens.css";
import "./globals.css";
export const metadata: Metadata = {
  title: { default: "mosAIc — Creative AI recipes", template: "%s · mosAIc" },
  description:
    "Explore creative AI recipes and try your own interpretation with original source attribution.",
  icons: { icon: "/favicon.svg" },
};
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
