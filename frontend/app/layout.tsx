import type { Metadata, Viewport } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

export const viewport: Viewport = {
  themeColor: "#05070b",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  title: "Foot Predict — Analyse & Value Bets",
  description:
    "Prédictions mathématiques 1X2, Over/Under 2.5, BTTS, Value Bets sur 13 championnats européens (première et deuxième divisions). Modèle Elo + Time Decay + Poisson Dixon-Coles + xG.",
  keywords: ["football", "prédictions", "value bets", "Elo", "Poisson", "Dixon-Coles"],
  manifest: "/manifest.json",
  icons: [
    {
      rel: "icon",
      type: "image/svg+xml",
      url: "/icons/icon.svg",
    },
    {
      rel: "icon",
      type: "image/png",
      sizes: "192x192",
      url: "/icons/icon-192x192.png",
    },
    {
      rel: "icon",
      type: "image/png",
      sizes: "512x512",
      url: "/icons/icon-512x512.png",
    },
    {
      rel: "apple-touch-icon",
      type: "image/png",
      sizes: "180x180",
      url: "/icons/icon-180x180.png",
    },
  ],
};

const themeScript = `(function(){try{var t=localStorage.getItem('fp-theme');if(!t){t=window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';}var d=document.documentElement;d.dataset.theme=t;d.style.colorScheme=t;}catch(e){}})();`;

const swRegisterScript = `(function(){if('serviceWorker' in navigator){window.addEventListener('load',()=>{navigator.serviceWorker.register('/sw.js').then((reg)=>console.log('SW registered:',reg)).catch((err)=>console.log('SW error:',err));}})})();`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#05070b" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="Foot Predict" />
      </head>
      <body className="min-h-screen bg-ink-950 font-sans text-slate-200 antialiased">
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <script dangerouslySetInnerHTML={{ __html: swRegisterScript }} />
        <div className="flex min-h-screen flex-col">
          <Navbar />
          <main className="mx-auto w-full max-w-[1280px] flex-1 px-4 pb-16 pt-8 sm:px-6 lg:px-8">
            {children}
          </main>
          <Footer />
        </div>
      </body>
    </html>
  );
}
