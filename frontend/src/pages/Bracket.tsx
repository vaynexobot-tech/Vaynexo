// Turnir setkasi (olimpiya tizimi): foydalanuvchi ko'rinishi va admin uchun g'olibni belgilash.
import { t } from "../i18n";

export interface BSide { entry_id: number; name: string; mine: boolean }
export interface BMatch { id: number; slot: number; a: BSide | null; b: BSide | null; winner: number | null }
export interface BracketT { rounds: { round: number; name: string; matches: BMatch[] }[]; champion: BSide | null; entries: number }

const RNAME: Record<string, string> = { Final: "Final", "Yarim final": "Yarim final", "Chorak final": "Chorak final" };

function Side({ s, win, done, onPick }: { s: BSide | null; win: boolean; done: boolean; onPick?: () => void }) {
  const cls = "bk-side" + (win ? " win" : done && s ? " lose" : "") + (s?.mine ? " mine" : "");
  return (
    <div className={cls}>
      <span className="ell grow">{s ? s.name : <span className="mut">{done ? t("avtomatik o'tish") : "—"}</span>}</span>
      {win && <span>🏆</span>}
      {onPick && s && !done && <button className="bk-pick" onClick={onPick}>✓</button>}
    </div>
  );
}

export function BracketView({ b, onPick }: { b: BracketT; onPick?: (matchId: number, entryId: number) => void }) {
  if (!b.rounds.length) return null;
  return (
    <>
      {b.champion && (
        <div className="hero center" style={{ alignItems: "center", gap: 4 }}>
          <div style={{ fontSize: 34 }}>🏆</div>
          <div className="mut xs">{t("Chempion")}</div>
          <div className="hf bb y" style={{ fontSize: 20 }}>{b.champion.name}</div>
        </div>
      )}
      <div className="bk">
        {b.rounds.map((r) => (
          <div key={r.round} className="bk-col">
            <div className="bk-h">{RNAME[r.name] ? t(RNAME[r.name]) : t("{n}-raund", { n: r.round })}</div>
            {r.matches.map((m) => {
              const done = !!m.winner || (r.round === 1 && !!m.a && !m.b);
              const can = !!onPick && !!m.a && !!m.b && !m.winner;
              return (
                <div key={m.id} className="bk-m">
                  <Side s={m.a} win={!!m.a && m.winner === m.a.entry_id} done={done} onPick={can ? () => onPick!(m.id, m.a!.entry_id) : undefined} />
                  <Side s={m.b} win={!!m.b && m.winner === m.b.entry_id} done={done} onPick={can ? () => onPick!(m.id, m.b!.entry_id) : undefined} />
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </>
  );
}
