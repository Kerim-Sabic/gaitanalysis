"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Asymmetry, JointCurve } from "@horalix/shared";
import { cn } from "@/lib/utils";

const LEFT = "#f2a93b";
const RIGHT = "#5aa0f7";
const GRID = "hsl(var(--border))";

function tooltipStyle() {
  return {
    contentStyle: {
      background: "hsl(var(--surface))",
      border: "1px solid hsl(var(--border))",
      borderRadius: 12,
      fontSize: 12,
      color: "hsl(var(--fg))",
    },
    labelStyle: { color: "hsl(var(--fg-subtle))" },
  };
}

export function JointCurveChart({ curves }: { curves: JointCurve[] }) {
  // Group into selectable pairs (knee, hip) + singletons (trunk).
  const groups = useMemo(() => {
    const byBase: Record<string, { left?: JointCurve; right?: JointCurve; single?: JointCurve }> =
      {};
    for (const c of curves) {
      const m = c.key.match(/^(knee|hip)_(left|right)$/);
      if (m) {
        byBase[m[1]] = byBase[m[1]] || {};
        byBase[m[1]][m[2] as "left" | "right"] = c;
      } else {
        byBase[c.key] = { single: c };
      }
    }
    return byBase;
  }, [curves]);

  const keys = Object.keys(groups);
  const [active, setActive] = useState(keys[0] ?? "");
  const g = groups[active];

  const data = useMemo(() => {
    if (!g) return [];
    if (g.single) return g.single.samples.map((p) => ({ t: p.t, value: p.value }));
    const left = g.left?.samples ?? [];
    const right = g.right?.samples ?? [];
    const n = Math.max(left.length, right.length);
    return Array.from({ length: n }, (_, i) => ({
      t: (left[i] ?? right[i])?.t ?? 0,
      left: left[i]?.value ?? null,
      right: right[i]?.value ?? null,
    }));
  }, [g]);

  if (!keys.length) return <Empty label="No joint curves available." />;

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        {keys.map((k) => (
          <button
            key={k}
            onClick={() => setActive(k)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs capitalize transition",
              active === k
                ? "border-primary/40 bg-primary/15 text-primary"
                : "border-border bg-surface-2 text-fg-subtle hover:text-fg",
            )}
          >
            {k}
          </button>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="t"
            tickFormatter={(v) => `${Number(v).toFixed(1)}s`}
            stroke="hsl(var(--fg-subtle))"
            fontSize={11}
            tickLine={false}
          />
          <YAxis
            stroke="hsl(var(--fg-subtle))"
            fontSize={11}
            tickLine={false}
            width={36}
            unit="°"
          />
          <Tooltip {...tooltipStyle()} formatter={(v) => `${Number(v).toFixed(1)}°`} />
          {g?.single ? (
            <Line type="monotone" dataKey="value" stroke={RIGHT} dot={false} strokeWidth={2} isAnimationActive />
          ) : (
            <>
              <Line type="monotone" dataKey="left" name="Left" stroke={LEFT} dot={false} strokeWidth={2} connectNulls />
              <Line type="monotone" dataKey="right" name="Right" stroke={RIGHT} dot={false} strokeWidth={2} connectNulls />
            </>
          )}
        </LineChart>
      </ResponsiveContainer>
      {!g?.single ? (
        <Legend />
      ) : null}
    </div>
  );
}

export function AsymmetryChart({ items }: { items: Asymmetry[] }) {
  const data = items
    .filter((a) => a.asymmetry_percent !== null)
    .map((a) => ({
      name: a.label,
      value: Number(a.asymmetry_percent),
      status: a.status,
    }));
  if (!data.length) return <Empty label="Asymmetry could not be computed." />;

  const color = (status: string) =>
    status === "good"
      ? "hsl(var(--good))"
      : status === "low_confidence"
        ? "hsl(var(--danger))"
        : "hsl(var(--warn))";

  return (
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * 46)}>
      <BarChart layout="vertical" data={data} margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" unit="%" stroke="hsl(var(--fg-subtle))" fontSize={11} tickLine={false} />
        <YAxis
          type="category"
          dataKey="name"
          width={120}
          stroke="hsl(var(--fg-subtle))"
          fontSize={11}
          tickLine={false}
        />
        <Tooltip {...tooltipStyle()} formatter={(v) => `${Number(v).toFixed(1)}%`} />
        <ReferenceLine x={5} stroke="hsl(var(--good))" strokeDasharray="4 4" />
        <ReferenceLine x={10} stroke="hsl(var(--warn))" strokeDasharray="4 4" />
        <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={16}>
          {data.map((d, i) => (
            <Cell key={i} fill={color(d.status)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function Legend() {
  return (
    <div className="mt-2 flex items-center justify-center gap-4 text-[11px] text-fg-subtle">
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-3 rounded" style={{ background: LEFT }} /> Left
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-3 rounded" style={{ background: RIGHT }} /> Right
      </span>
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-border text-xs text-fg-subtle">
      {label}
    </div>
  );
}
