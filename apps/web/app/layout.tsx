import type { Metadata } from "next";
import "./globals.css";
import { Topbar } from "@/components/layout/topbar";
import { DISCLAIMER_TEXT } from "@/components/ui/disclaimer";

export const metadata: Metadata = {
  title: "Horalix Gait AI — Markerless AI gait analysis",
  description:
    "AI-assisted gait quantification from ordinary walking video. For clinician review — not a standalone diagnosis.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen app-bg antialiased">
        {/* Prevent theme flash before hydration */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('horalix-theme');var d=t?t==='dark':true;document.documentElement.classList.toggle('dark',d);}catch(e){}`,
          }}
        />
        <Topbar />
        <main className="mx-auto max-w-7xl px-4 pb-20 pt-8 sm:px-6">{children}</main>
        <footer className="border-t border-border">
          <div className="mx-auto max-w-7xl px-4 py-6 text-[11px] text-fg-subtle sm:px-6">
            {DISCLAIMER_TEXT}
          </div>
        </footer>
      </body>
    </html>
  );
}
