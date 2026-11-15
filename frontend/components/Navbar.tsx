"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";

const NAV_ITEMS = [
  { href: "/", label: "Matchs & Value Bets" },
  { href: "/history", label: "Historique" },
  { href: "/performance", label: "Transparence & Bilan" },
];

export default function Navbar() {
  const pathname = usePathname();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const toggleMenu = () => setIsMenuOpen((prev) => !prev);
  const closeMenu = () => setIsMenuOpen(false);

  // Fermer le menu au changement de route (navigation par lien).
  useEffect(() => {
    setIsMenuOpen(false);
  }, [pathname]);

  // Fermer le menu avec Échap et bloquer le défilement de la page lorsqu'il est ouvert.
  useEffect(() => {
    if (!isMenuOpen) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsMenuOpen(false);
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [isMenuOpen]);

  return (
    <header className="sticky top-0 z-50 border-b border-ink-700/70 bg-ink-950/80 backdrop-blur-xl">
      <div className="relative z-50 mx-auto flex h-16 w-full max-w-[1280px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="link-focus group flex items-center gap-3 rounded-lg"
        >
          <span className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-accent/30 bg-accent-soft">
            <span className="absolute inset-0 rounded-lg bg-accent/10 blur-md" aria-hidden />
            <svg viewBox="0 0 24 24" className="relative h-5 w-5 text-accent" fill="none" stroke="currentColor" strokeWidth={1.8}>
              <circle cx="12" cy="12" r="9" />
              <path d="M12 3v4M12 17v4M3 12h4M17 12h4" strokeLinecap="round" />
              <circle cx="12" cy="12" r="2.4" />
            </svg>
          </span>
          <span className="flex flex-col leading-none">
            <span className="text-[15px] font-semibold tracking-wide text-fg">
              FOOT<span className="text-accent">PREDICT</span>
            </span>
            <span className="mt-1 font-mono text-[10px] uppercase tracking-[0.22em] text-slate-500">
              Elo · Time Decay · Poisson
            </span>
          </span>
        </Link>

        <div className="flex items-center gap-2">
          {/* Navigation desktop */}
          <nav className="flex items-center gap-1 hidden md:flex">
            {NAV_ITEMS.map((item) => {
              const active =
                item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`link-focus rounded-lg px-3 py-2 text-[13px] font-medium transition ${
                    active
                      ? "bg-ink-800 text-fg"
                      : "text-slate-400 hover:bg-ink-800/60 hover:text-slate-200"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <ThemeToggle />
          {/* Bouton menu mobile */}
          <button
            type="button"
            className="md:hidden flex items-center justify-center rounded-lg border border-ink-600 bg-ink-800/60 px-3 py-2 transition hover:bg-ink-700 link-focus"
            onClick={toggleMenu}
            aria-label={isMenuOpen ? "Fermer le menu" : "Ouvrir le menu"}
            aria-expanded={isMenuOpen}
            aria-controls="mobile-menu"
          >
            <svg
              className={isMenuOpen ? "h-5 w-5" : "h-6 w-6"}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d={isMenuOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"}
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Voile + panneau mobile */}
      <div
        className={`fixed inset-0 z-[60] md:hidden pointer-events-none`}
        aria-hidden={!isMenuOpen}
      >
        <button
          type="button"
          tabIndex={isMenuOpen ? 0 : -1}
          aria-label="Fermer le menu"
          onClick={closeMenu}
          className={`absolute top-20 bottom-0 left-0 right-0 bg-ink-950/80 backdrop-blur-sm transition-opacity duration-200 z-[55] ${
            isMenuOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
          }`}
        />
        <div
          id="mobile-menu"
          className={`absolute bottom-0 left-0 right-0 top-20 w-full flex flex-col border-0 bg-ink-950 shadow-2xl transition-transform duration-300 ease-in-out z-[58] ${
            isMenuOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <nav className="w-full flex flex-col gap-2 overflow-y-auto px-4 py-4">
            {NAV_ITEMS.map((item) => {
              const active =
                item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={closeMenu}
                  className={`link-focus rounded-lg px-4 py-3 text-sm font-medium transition ${
                    active
                      ? "bg-ink-800 text-fg"
                      : "text-slate-400 hover:bg-ink-800/60 hover:text-slate-200"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="flex justify-center border-t border-ink-800 px-4 py-4">
            <ThemeToggle />
          </div>
        </div>
      </div>
    </header>
  );
}