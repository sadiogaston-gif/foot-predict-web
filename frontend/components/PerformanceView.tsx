"use client";

import { useEffect, useState } from "react";
import BankrollChart from "@/components/BankrollChart";
import KpiCard from "@/components/KpiCard";
import { apiGet } from "@/lib/api";
import { pct, signedPct, units } from "@/lib/format";
import type { BacktestStats, StrategyStats } from "@/lib/types";

function RoiText({ value }: { value: number }) {
  return (
    <span className={value > 0 ? "text-accent" : value < 0 ? "text-danger" : "text-slate-300"}>
      {signedPct(value)}
    </span>
  );
}

function StrategyCard({
  title,
  subtitle,
  stats,
}: {
  title: string;
  subtitle: string;
  stats: StrategyStats;
}) {
  const positive = stats.profit > 0;
  return (
    <div className="rounded-xl border border-ink-700/70 bg-ink-900/50 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[13px] font-semibold text-fg">{title}</p>
          <p className="mt-0.5 text-[11px] text-slate-500">{subtitle}</p>
        </div>
        <span
          className={`tnum rounded-md border px-2 py-0.5 font-mono text-[11px] ${
            positive
              ? "border-accent/40 bg-accent/10 text-accent"
              : "border-danger/40 bg-danger/10 text-danger"
          }`}
        >
          {signedPct(stats.roi_percent)}
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-[12px]">
        <div>
          <dt className="text-slate-500">Misé</dt>
          <dd className="tnum mt-0.5 font-mono text-slate-200">{stats.staked.toFixed(2)} u</dd>
        </div>
        <div>
          <dt className="text-slate-500">Profit net</dt>
          <dd className={`tnum mt-0.5 font-mono ${positive ? "text-accent" : "text-danger"}`}>
            {units(stats.profit)}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Drawdown max</dt>
          <dd className="tnum mt-0.5 font-mono text-slate-200">
            {stats.max_drawdown_units.toFixed(2)} u
            <span className="ml-1 text-[10px] text-slate-500">({pct(stats.max_drawdown_percent)})</span>
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Bankroll finale</dt>
          <dd className="tnum mt-0.5 font-mono text-slate-200">{stats.final_bankroll.toFixed(2)} u</dd>
        </div>
      </dl>
    </div>
  );
}

export default function PerformanceView() {
  const [stats, setStats] = useState<BacktestStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiGet<BacktestStats>("/api/backtest/stats", controller.signal)
      .then((response) => setStats(response))
      .catch((err: Error) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, []);

  if (loading) {
    return (
      <div className="space-y-5">
        <div className="skeleton h-8 w-64" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="skeleton h-24" />
          ))}
        </div>
        <div className="skeleton h-80 w-full" />
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="card border-danger/30 bg-danger-soft/20 p-6">
        <p className="text-sm font-semibold text-danger">Statistiques indisponibles</p>
        <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-slate-300">
          {error ?? "Aucun rapport de backtest trouvé."}
        </p>
        <p className="mt-3 text-[12px] text-slate-500">
          Générez les exports avec <code className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-[11px] text-slate-300">python run_backtest.py</code>{" "}
          puis rechargez cette page.
        </p>
      </div>
    );
  }

  const flat = stats.strategy_flat;
  const kelly = stats.strategy_kelly;
  const brierGap = stats.brier_model - stats.brier_bookmaker;

  return (
    <div className="space-y-6">
      {/* En-tête ---------------------------------------------------------- */}
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="chip border-info/30 bg-info/5 text-info">Phase 2 · Backtesting</span>
          <span className="chip">Saison {stats.season}</span>
          <span className="chip">Warm-up {stats.warmup_seasons.join(", ")}</span>
        </div>
        <h1 className="text-[26px] font-semibold tracking-tight text-fg sm:text-3xl">
          Transparence &amp; Bilan
        </h1>
        <p className="max-w-3xl text-sm leading-relaxed text-slate-400">
          Résultats d&apos;une simulation chronologique sans fuite de données sur{" "}
          <span className="tnum font-mono text-slate-200">{stats.matches}</span> matchs. Chaque
          rencontre est prédite avec un moteur qui ne connaît que les matchs strictement
          antérieurs, puis mise à jour avec le résultat réel.
        </p>
      </header>

      {/* KPI -------------------------------------------------------------- */}
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <KpiCard
          label="ROI — Flat 1 u"
          value={signedPct(flat.roi_percent)}
          tone={flat.roi_percent >= 0 ? "positive" : "negative"}
          hint={`${units(flat.profit)} sur ${flat.staked.toFixed(0)} u misées`}
        />
        <KpiCard
          label="ROI — Quarter-Kelly"
          value={signedPct(kelly.roi_percent)}
          tone={kelly.roi_percent >= 0 ? "positive" : "negative"}
          hint={`${units(kelly.profit)} · plafond 3 % par pari`}
        />
        <KpiCard
          label="Brier Score modèle"
          value={stats.brier_model.toFixed(4)}
          tone="accent"
          hint={`Bookmaker : ${stats.brier_bookmaker.toFixed(4)} · écart ${brierGap >= 0 ? "+" : ""}${brierGap.toFixed(4)}`}
        />
        <KpiCard
          label="Précision 1X2"
          value={pct(stats.accuracy_1x2)}
          hint={`Log-loss ${stats.logloss_model.toFixed(4)} · hasard = 0,6667`}
        />
        <KpiCard
          label="Paris simulés"
          value={String(stats.bets)}
          hint={`${stats.wins} gagnants · taux ${pct(stats.win_rate)}`}
        />
        <KpiCard
          label="Cote moyenne jouée"
          value={stats.avg_odds.toFixed(2)}
          hint={`EV moyenne ${signedPct(stats.avg_ev)}`}
        />
      </section>

      {/* Courbe de bankroll ---------------------------------------------- */}
      <section className="card p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-fg">Évolution de la bankroll</h2>
            <p className="mt-1 text-[12px] text-slate-500">
              Un point par jour de paris · bankroll initiale{" "}
              {stats.params.initial_bankroll?.toFixed(0) ?? "100"} unités
            </p>
          </div>
          <div className="flex items-center gap-4 text-[11px] text-slate-400">
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-4 rounded-full bg-info" /> Flat 1 u
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-4 rounded-full bg-warn" /> Quarter-Kelly
            </span>
          </div>
        </div>
        <div className="mt-3">
          <BankrollChart
            points={stats.bankroll_curve}
            initial={stats.params.initial_bankroll ?? 100}
          />
        </div>
      </section>

      {/* Stratégies ------------------------------------------------------- */}
      <section className="card p-5">
        <h2 className="text-sm font-semibold text-fg">Comparaison des stratégies de mise</h2>
        <p className="mt-1 text-[12px] text-slate-500">
          Détection : EV ≥ {(stats.params.ev_threshold * 100).toFixed(0)} % et cotes entre{" "}
          {stats.params.min_odds.toFixed(2)} et {stats.params.max_odds.toFixed(2)}.
        </p>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <StrategyCard
            title="Stratégie A — Flat betting"
            subtitle="1 unité fixe sur chaque value bet détecté"
            stats={flat}
          />
          <StrategyCard
            title="Stratégie B — Quarter-Kelly"
            subtitle={`${stats.params.kelly_fraction.toFixed(2)} × Kelly, plafonné à ${(stats.params.kelly_cap * 100).toFixed(0)} % de la bankroll initiale`}
            stats={kelly}
          />
        </div>
      </section>

      {/* Par championnat --------------------------------------------------- */}
      <section className="card p-5">
        <h2 className="text-sm font-semibold text-fg">Performance par championnat</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="table-base min-w-[640px]">
            <thead>
              <tr>
                <th>Championnat</th>
                <th className="text-right">Paris</th>
                <th className="text-right">Réussite</th>
                <th className="text-right">Cote moy.</th>
                <th className="text-right">ROI flat</th>
                <th className="text-right">Profit flat</th>
                <th className="text-right">ROI Kelly</th>
              </tr>
            </thead>
            <tbody>
              {stats.by_league.map((row) => (
                <tr key={row.league}>
                  <td className="max-w-[220px] truncate text-[13px] text-slate-200">{row.league}</td>
                  <td className="tnum text-right font-mono text-[12px]">{row.bets}</td>
                  <td className="tnum text-right font-mono text-[12px]">{pct(row.win_rate)}</td>
                  <td className="tnum text-right font-mono text-[12px]">{row.avg_odds.toFixed(2)}</td>
                  <td className="tnum text-right font-mono text-[12px]">
                    <RoiText value={row.roi_flat} />
                  </td>
                  <td className={`tnum text-right font-mono text-[12px] ${row.profit_flat >= 0 ? "text-accent" : "text-danger"}`}>
                    {units(row.profit_flat)}
                  </td>
                  <td className="tnum text-right font-mono text-[12px]">
                    <RoiText value={row.roi_kelly} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Par type de pari -------------------------------------------------- */}
      <section className="card p-5">
        <h2 className="text-sm font-semibold text-fg">Performance par type de pari</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="table-base min-w-[640px]">
            <thead>
              <tr>
                <th>Type</th>
                <th className="text-right">Paris</th>
                <th className="text-right">Réussite</th>
                <th className="text-right">Cote moy.</th>
                <th className="text-right">ROI flat</th>
                <th className="text-right">Profit flat</th>
                <th className="text-right">ROI Kelly</th>
              </tr>
            </thead>
            <tbody>
              {stats.by_market.map((row) => (
                <tr key={row.market}>
                  <td className="text-[13px] text-slate-200">{row.label}</td>
                  <td className="tnum text-right font-mono text-[12px]">{row.bets}</td>
                  <td className="tnum text-right font-mono text-[12px]">{pct(row.win_rate)}</td>
                  <td className="tnum text-right font-mono text-[12px]">{row.avg_odds.toFixed(2)}</td>
                  <td className="tnum text-right font-mono text-[12px]">
                    <RoiText value={row.roi_flat} />
                  </td>
                  <td className={`tnum text-right font-mono text-[12px] ${row.profit_flat >= 0 ? "text-accent" : "text-danger"}`}>
                    {units(row.profit_flat)}
                  </td>
                  <td className="tnum text-right font-mono text-[12px]">
                    <RoiText value={row.roi_kelly} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Lecture critique --------------------------------------------------- */}
      <section className="card border-warn/20 bg-warn-soft/10 p-5">
        <h2 className="text-sm font-semibold text-fg">Comment lire ces résultats</h2>
        <ul className="mt-3 space-y-2 text-[13px] leading-relaxed text-slate-300">
          <li>
            <span className="text-slate-500">1.</span> Le modèle bat les fréquences de base
            ({stats.brier_baserate.toFixed(4)} de Brier) : il apporte une information réelle.
          </li>
          <li>
            <span className="text-slate-500">2.</span> Il reste derrière le marché
            ({stats.brier_bookmaker.toFixed(4)}) : les bookmakers intègrent plus d&apos;information
            (compositions, blessures, flux de paris).
          </li>
          <li>
            <span className="text-slate-500">3.</span> Un ROI négatif sur une seule saison ne
            prouve pas l&apos;absence d&apos;avantage, mais aucun ROI positif statistiquement
            significatif n&apos;a été observé. Les écarts par championnat reposent sur des
            sous-échantillons de 150 à 210 paris.
          </li>
          <li>
            <span className="text-slate-500">4.</span> La détection affichée (EV ≥ 5 %) est
            volontairement large : {stats.bets} paris sur {stats.matches} matchs traduisent une
            sur-confiance du modèle, pas une inefficience du marché.
          </li>
        </ul>
        <p className="mt-4 text-[11px] text-slate-500">
          Données : Football-Data.co.uk · cotes Bet365 (repli moyenne du marché) · aucun gain
          n&apos;est garanti.
        </p>
      </section>
    </div>
  );
}
