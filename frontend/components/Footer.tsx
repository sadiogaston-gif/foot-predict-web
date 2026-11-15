import Link from "next/link";

/**
 * Pied de page présent sur toutes les pages.
 * Contient les mentions légales obligatoires (prédictions mathématiques,
 * absence de garantie de gain, prévention des risques liés aux jeux d'argent).
 */
export default function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="mt-auto border-t border-ink-700/70 bg-ink-950">
      <div className="mx-auto w-full max-w-[1280px] px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid gap-8 md:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <p className="text-sm font-semibold text-fg">
              FOOT<span className="text-accent">PREDICT</span>
            </p>
            <p className="mt-3 max-w-md text-[13px] leading-relaxed text-slate-400">
              Plateforme d&apos;analyse statistique du football européen. Les probabilités
              affichées proviennent d&apos;un modèle mathématique (classement Elo dynamique,
              pondération temporelle des performances, loi de Poisson ajustée Dixon-Coles)
              entraîné sur des données publiques de Football-Data.co.uk.
            </p>
          </div>

          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Avertissement
            </p>
            <p className="mt-3 text-[13px] leading-relaxed text-slate-400">
              Les prédictions sont <strong className="text-slate-200">purement mathématiques</strong> et
              ne constituent en aucun cas un conseil en pari. Aucun gain n&apos;est garanti :
              le modèle a montré un ROI négatif lors du backtesting publié sur la page
              Transparence.
            </p>
          </div>

          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Jeux d&apos;argent
            </p>
            <p className="mt-3 text-[13px] leading-relaxed text-slate-400">
              Les jeux d&apos;argent comportent des risques : endettement, isolement,
              dépendance. Interdits aux mineurs (18+). Si vous ou un proche êtes concerné,
              contactez <span className="text-slate-200">Joueurs Info Service</span> au
              09 74 75 13 13 (appel non surtaxé).
            </p>
          </div>
        </div>

        <div className="mt-8 flex flex-col gap-3 border-t border-ink-700/60 pt-6 text-[12px] text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <p>© {year} Foot Predict — Projet pédagogique, sans but lucratif.</p>
          <div className="flex items-center gap-4">
            <Link href="/performance" className="link-focus rounded transition hover:text-slate-300">
              Résultats du backtest
            </Link>
            <span className="hidden sm:inline">·</span>
            <span className="font-mono">18+ · Jouez responsable</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
