import type { Metadata, Viewport } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Beacom", template: "%s · Beacom" },
  description: "Les avis de vos clients, analysés automatiquement : ce qui plaît, ce qui déçoit, établissement par établissement.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RacineLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
