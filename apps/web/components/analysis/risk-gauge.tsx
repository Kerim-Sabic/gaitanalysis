import { riskBandLabel, riskTone } from "@/lib/format";
import { Badge } from "@/components/ui/badge";

/** Semicircular gauge for the Mobility Risk Support Score (screening aid). */
export function RiskGauge({
  score,
  band,
  confidence,
}: {
  score: number;
  band: string;
  confidence: number;
}) {
  const tone = riskTone(band);
  const color = {
    good: "hsl(var(--good))",
    warn: "hsl(var(--warn))",
    danger: "hsl(var(--danger))",
    muted: "hsl(var(--fg-subtle))",
  }[tone];

  const r = 70;
  const circ = Math.PI * r; // semicircle length
  const frac = Math.max(0, Math.min(100, score)) / 100;

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 180 100" className="w-full max-w-[240px]">
        <path
          d="M 20 95 A 70 70 0 0 1 160 95"
          fill="none"
          stroke="hsl(var(--muted))"
          strokeWidth="12"
          strokeLinecap="round"
        />
        <path
          d="M 20 95 A 70 70 0 0 1 160 95"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${frac * circ} ${circ}`}
          style={{ transition: "stroke-dasharray 0.8s cubic-bezier(0.16,1,0.3,1)" }}
        />
        <text
          x="90"
          y="78"
          textAnchor="middle"
          className="tabular fill-fg"
          style={{ fontSize: 30, fontWeight: 600 }}
        >
          {Math.round(score)}
        </text>
        <text x="90" y="93" textAnchor="middle" className="fill-current text-fg-subtle" style={{ fontSize: 9 }}>
          / 100
        </text>
      </svg>
      <div className="mt-1 flex items-center gap-2">
        <Badge tone={tone}>{riskBandLabel(band)}</Badge>
        <span className="text-[11px] text-fg-subtle">conf {Math.round(confidence * 100)}%</span>
      </div>
      <p className="mt-2 max-w-xs text-center text-[11px] leading-snug text-fg-subtle">
        Mobility Risk Support Score — a screening aid for clinician review, not a
        fall-risk diagnosis.
      </p>
    </div>
  );
}
