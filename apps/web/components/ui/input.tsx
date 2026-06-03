import * as React from "react";
import { cn } from "@/lib/utils";

const base =
  "h-10 w-full rounded-xl border border-border bg-surface-2 px-3 text-sm text-fg " +
  "placeholder:text-fg-subtle/60 focus-visible:outline-none focus-visible:ring-2 " +
  "focus-visible:ring-primary/50 transition";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input ref={ref} className={cn(base, className)} {...props} />
));
Input.displayName = "Input";

export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => (
  <select ref={ref} className={cn(base, "pr-8", className)} {...props}>
    {children}
  </select>
));
Select.displayName = "Select";

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium text-fg-subtle">{label}</span>
      {children}
      {hint ? <span className="block text-[11px] text-fg-subtle/70">{hint}</span> : null}
    </label>
  );
}
