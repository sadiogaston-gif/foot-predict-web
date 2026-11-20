"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";

type NavIcon = "ball" | "chart" | "clock" | "shield";

const NAV_ITEMS: { href: string; label: string; short: string; icon: NavIcon }[] = [
  { href: "/", label: "Matchs & Value Bets", short: "Matchs", icon: "ball" },
  { href: "/simulation", label: "Simulation", short: "Simulation", icon: "chart" },
  { href: "/history", label: "Historique", short: "Historique", icon: "clock" },
  { href: "/performance", label: "Transparence & Bilan", short: "Bilan", icon: "shield" },
];

function NavIconSvg({ name, className = "h-4 w-4" }: { name: NavIcon; className?: string }) {
  const common = {
    className,
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    viewBox: "0 0 24 24",
    "aria-hidden": true,
  } as const;
  switch (name) {
    case "ball":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 3v4M12 17v4M3 12h4M17 12h4" strokeLinecap="round" />
          <circle cx="12" cy="12" r="2.4" />
        </svg>
      );
    case "chart":
      return (
        <svg {...common}>
          <path d="M4 19h16M6 16l4-5 3 3 5-7" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M15 7h3v3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "clock":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "shield":
      return (
        <svg {...common}>
          <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3Z" strokeLinejoin="round" />
          <path d="m9 12 2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
  }
}

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export default function Navbar() {
  const pathname = usePathname();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const toggleMenu = () => setIsMenuOpen((prev) => !prev);
  const closeMenu = () => setIsMenuOpen(false);

  // Fermer le menu au changement de route.
  useEffect(() => {
    setIsMenuOpen(false);
  }, [pathname]);

  // Gestion Échap et overflow du body.
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
    <header className="sticky top-0 z-50 w-full border-b border-ink-700/60 bg-ink-950/90 backdrop-blur-lg supports-[backdrop-filter]:bg-ink-950/70">
      <div className="relative z-50 mx-auto flex h-14 w-full max-w-[1400px] items-center gap-1 px-3 sm:gap-2 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link
          href="/"
          className="link-focus group mr-1 flex shrink-0 items-center gap-2 rounded-lg px-1.5 py-1.5 transition hover:bg-ink-800/50 sm:mr-4 sm:gap-2.5 sm:px-2"
        >
          <span className="relative flex h-8 w-8 items-center justify-center rounded-lg border border-accent/30 bg-accent-soft">
            <span className="absolute inset-0 rounded-lg bg-accent/10 blur-md" aria-hidden />
            <svg viewBox="0 0 24 24" className="relative h-5 w-5 text-accent" fill="none" stroke="currentColor" strokeWidth={1.8}>
              <circle cx="12" cy="12" r="9" />
              <path d="M12 3v4M12 17v4M3 12h4M17 12h4" strokeLinecap="round" />
              <circle cx="12" cy="12" r="2.4" />
            </svg>
          </span>
          <span className="hidden flex-col leading-none sm:flex">
            <span className="text-[14px] font-semibold tracking-wide text-fg">
              FOOT<span className="text-accent">PREDICT</span>
            </span>
            <span className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.22em] text-slate-500">
              Elo · Poisson
            </span>
          </span>
        </Link>

        {/* Onglets desktop (style Sofascore) */}
        <nav className="hidden flex-1 items-center gap-1 md:flex" aria-label="Navigation principale">
          {NAV_ITEMS.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`link-focus relative flex items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium transition ${
                  active
                    ? "bg-ink-800 text-fg"
                    : "text-slate-400 hover:bg-ink-800/60 hover:text-slate-200"
                }`}
              >
                <NavIconSvg name={item.icon} className={`h-4 w-4 ${active ? "text-accent" : ""}`} />
                <span>{item.short}</span>
                {active ? (
                  <span className="absolute -bottom-[11px] left-1/2 h-0.5 w-6 -translate-x-1/2 rounded-full bg-accent" />
                ) : null}
              </Link>
            );
          })}
        </nav>

        {/* Actions droites */}
        <div className="ml-auto flex items-center gap-2">
          <span className="hidden items-center gap-1.5 rounded-full border border-accent/20 bg-accent/5 px-2.5 py-1 text-[10px] font-medium text-accent lg:flex">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
            </span>
            Live
          </span>
          <ThemeToggle className="px-2 py-2" />

          {/* Bouton hamburger mobile */}
          <button
            type="button"
            className="md:hidden flex h-9 w-9 items-center justify-center rounded-lg border border-ink-600 bg-ink-800/60 text-slate-300 transition hover:bg-ink-700 hover:text-fg"
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
      <div className="fixed inset-0 z-[60] md:hidden" aria-hidden={!isMenuOpen}>
        <button
          type="button"
          tabIndex={isMenuOpen ? 0 : -1}
          aria-label="Fermer le menu"
          onClick={closeMenu}
          className={`absolute inset-0 bg-ink-950/80 backdrop-blur-sm transition-opacity duration-200 z-[55] ${
            isMenuOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
          }`}
        />
        <div
          id="mobile-menu"
          className={`absolute inset-0 w-full flex flex-col border-b border-ink-700/60 bg-ink-950/98 backdrop-blur-xl shadow-2xl transition-transform duration-300 ease-in-out z-[58] ${
            isMenuOpen ? "translate-y-0" : "-translate-y-full"
          }`}
        >
          <nav className="flex w-full flex-col gap-1.5 overflow-y-auto px-4 py-6" aria-label="Navigation mobile">
            <p className="mb-2 px-3 text-[10px] uppercase tracking-[0.2em] text-slate-600">
              Navigation
            </p>
            {NAV_ITEMS.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={closeMenu}
                  aria-current={active ? "page" : undefined}
                  className={`link-focus flex items-center gap-3 rounded-xl px-4 py-3.5 text-[14px] font-medium transition ${
                    active
                      ? "bg-accent/10 text-accent ring-1 ring-accent/20"
                      : "text-slate-300 hover:bg-ink-800/60 hover:text-slate-100"
                  }`}
                >
                  <NavIconSvg name={item.icon} className="h-5 w-5" />
                  {item.label}
                  {active ? <span className="ml-auto h-1.5 w-1.5 rounded-full bg-accent" /> : null}
                </Link>
              );
            })}
          </nav>
          <div className="mt-auto border-t border-ink-800 px-4 py-5 text-center text-[11px] text-slate-600">
            FOOTPREDICT · Analyse mathématique
          </div>
        </div>
      </div>
    </header>
  );
}