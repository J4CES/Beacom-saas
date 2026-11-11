import { Inter } from "next/font/google";
import "./globals.css";

// On configure la police Inter avec toutes ses variations de poids
const inter = Inter({ 
  subsets: ["latin"],
  display: 'swap',
  variable: '--font-inter',
});

export const metadata = {
  title: "Beacom - E-réputation SaaS",
  description: "Gérez les avis de vos établissements",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={`${inter.variable}`}>
      {/* antialiased rend le texte beaucoup plus doux et net */}
      <body className={`${inter.className} antialiased bg-slate-50 text-slate-800`}>
        {children}
      </body>
    </html>
  );
}