import type { ReactNode } from "react";
import { Shell } from "./ui";

/** Shared layout for the short privacy and terms pages. */
export function LegalPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <Shell>
      <main className="body legal">
        <h1>{title}</h1>
        <p className="legal-updated">最後更新：{updated}</p>
        {children}
      </main>
    </Shell>
  );
}
