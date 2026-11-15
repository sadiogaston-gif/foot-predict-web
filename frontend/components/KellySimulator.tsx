"use client";

import { useMemo, useState } from "react";
import { odds, pct, signedPct } from "@/lib/format";
import type { ValueBet } from "@/lib/types";

interface KellySimulatorProps {
  valueBets: ValueBet[];
  bankrollDefault: number;
  /** Fraction de Kelly appliquée (0.25 = Quarter-Kelly). */
  fraction: number;
  /** Plafond de mise en % de la bankroll. */
  capPercent: number;
}

/**
 * Simulateur de mise basé sur le critère de Kelly fractionné.
 *
 * f* = (p × cote − 1) / (cote − 1)
 * mise = min(fraction × f* × bankroll, capPercent % × bankroll)
 *
 * Le plafond reproduit la stratégie B du backtesting (Quarter-Kelly, 3 % max).
 */
export default function KellySimulator({
  valueBets,
  bankrollDefault,
  fraction,
  capPercent,
}: KellySimulatorProps) {
  const markets = useMemo(
    () => valueBets.filter((bet) => bet.book_odds > 1),
    [valueBets],
  );

  const [marketKey, setMarketKey] = useState<string>(markets[0]?.market ?? "");
  const [bankroll, setBankroll] = useState<number>(bankrollDefault);

  const selected = markets.find((bet) => bet.market === marketKey) ?? markets[0] ?? null;

  const computation = useMemo(() => {
    if (!selected) return null;
    const p = selected.model_probability / 100;
    const b = selected.book_odds - 1;
    if (b <= 0) return null;

    const kellyFull = Math.max(0, (p * (b + 1) - 1) / b);
    const kellyFraction = fraction * kellyFull;
    const capAmount = (capPercent / 100) * bankroll;
    const recommended = Math.min(kellyFraction * bankroll, capAmount, bankroll);
    const potentialWin = recommended * b;

    return {
      kellyFull,
      kellyFraction,
      capAmount,
      recommended,
      potentialWin,
      shareOfBankroll: bankroll > 0 ? (recommended / bankroll) * 100 : 0,
    };
  }, [selected, bankroll, fraction, capPercent]);

  if (markets.length === 0) {
    return (
      <div className="card p-5">
        <p className="text-sm font-semibold text-fg">Aide à la décision</p>
        <p className="mt-2 text-[13px] leading-relaxed text-slate-400">
          Aucun marché exploitable sur ce match : les cotes du bookmaker ne présentent pas
          d&apos;espérance positive selon le modèle.
        </p>
      </div>
    );
  }

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-fg">Aide à la décision — Kelly fractionné</p>
          <p className="mt-1 text-[12px] text-slate-500">
            Quarter-Kelly ({fraction.toFixed(2)}) plafonné à {capPercent.toFixed(0)} % de la bankroll.
          </p>
        </div>
        <span className="chip border-ink-600 text-[10px]">Simulation</span>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Bankroll (€)
          </span>
          <input
            type="number"
            min={0}
            step={10}
            value={Number.isFinite(bankroll) ? bankroll : 0}
            onChange={(event) => setBankroll(Math.max(0, Number(event.target.value)))}
            className="tnum mt-2 w-full rounded-lg border border-ink-600 bg-ink-900 px-3 py-2 font-mono text-sm text-fg outline-none transition focus:border-accent/60"
          />
        </label>

        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Marché
          </span>
          <select
            value={selected?.market ?? ""}
            onChange={(event) => setMarketKey(event.target.value)}
            className="mt-2 w-full rounded-lg border border-ink-600 bg-ink-900 px-3 py-2 text-sm text-fg outline-none transition focus:border-accent/60"
          >
            {markets.map((bet) => (
              <option key={bet.market} value={bet.market}>
                {bet.label} — cote {odds(bet.book_odds)} ({signedPct(bet.ev_percent)})
              </option>
            ))}
          </select>
        </label>
      </div>

      {selected && computation ? (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div className="rounded-lg border border-ink-700/70 bg-ink-900/60 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Probabilité modèle</p>
              <p className="tnum mt-1 font-mono text-base text-fg">
                {pct(selected.model_probability)}
              </p>
            </div>
            <div className="rounded-lg border border-ink-700/70 bg-ink-900/60 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Cote jouée</p>
              <p className="tnum mt-1 font-mono text-base text-fg">{odds(selected.book_odds)}</p>
            </div>
            <div className="rounded-lg border border-ink-700/70 bg-ink-900/60 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Expected value</p>
              <p
                className={`tnum mt-1 font-mono text-base ${
                  selected.ev_percent > 0 ? "text-accent" : "text-danger"
                }`}
              >
                {signedPct(selected.ev_percent)}
              </p>
            </div>
            <div className="rounded-lg border border-ink-700/70 bg-ink-900/60 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Kelly brut</p>
              <p className="tnum mt-1 font-mono text-base text-slate-200">
                {(computation.kellyFull * 100).toFixed(1)} %
              </p>
            </div>
          </div>

          <div
            className={`mt-4 rounded-xl border p-4 ${
              selected.ev_percent > 0
                ? "border-accent/30 bg-accent/5"
                : "border-warn/30 bg-warn-soft/20"
            }`}
          >
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  Mise recommandée
                </p>
                <p className="tnum mt-1 font-mono text-3xl font-semibold text-accent">
                  {computation.recommended.toFixed(2)} €
                </p>
              </div>
              <div className="tnum text-right font-mono text-[12px] leading-relaxed text-slate-400">
                <p>{computation.shareOfBankroll.toFixed(2)} % de la bankroll</p>
                <p>Gain net potentiel : +{computation.potentialWin.toFixed(2)} €</p>
                <p className="text-slate-500">
                  Plafond {capPercent.toFixed(0)} % : {computation.capAmount.toFixed(2)} €
                </p>
              </div>
            </div>

            {selected.ev_percent <= 0 ? (
              <p className="mt-3 text-[12px] leading-relaxed text-warn/90">
                Espérance négative : la mise mathématiquement optimale est nulle. Le montant
                affiché ne doit pas être joué.
              </p>
            ) : null}
          </div>

          <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
            Le critère de Kelly suppose que vos probabilités sont exactes. Les nôtres sont
            calibrées mais imparfaites (Brier Score supérieur à celui du marché) : préférez la
            fraction la plus prudente.
          </p>
        </>
      ) : null}
    </div>
  );
}
