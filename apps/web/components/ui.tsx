"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import type { PublicRecipe } from "@mosaic/types";
import { messageFor } from "@mosaic/api";

export function Icon({
  name = "60349",
  size = 24,
  height = size,
}: {
  name?: string;
  size?: number;
  height?: number;
}) {
  return (
    <img
      className="icon"
      src={`/assets/${name}.svg`}
      width={size}
      height={height}
      alt=""
    />
  );
}
export function Shell({
  children,
  about = false,
}: {
  children: ReactNode;
  about?: boolean;
}) {
  const pathname = usePathname();
  return (
    <div className={`site ${about ? "about-site" : ""}`}>
      <header className="header">
        <Link href="/" className="brand">
          <span className="brand-mark">{about ? "M" : "m"}</span>
          <span>mosAIc</span>
        </Link>
        <nav aria-label="主要導覽">
          {[
            { href: "/", label: "Discover" },
            ...(!about
              ? [
                  { href: "/my-recipes", label: "My Recipes" },
                  { href: "/community", label: "Community" },
                ]
              : []),
            { href: "/about", label: "About" },
          ].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={pathname === item.href ? "page" : undefined}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        {!about && (
          <Link
            href="/"
            className="button primary header-cta"
            title="Choose a recipe to create your own interpretation"
          >
            Create Your Own
          </Link>
        )}
      </header>
      {children}
      <footer className="footer">
        <p>
          {about
            ? "© 2026 mosAIc. All rights reserved."
            : "© 2025 mosAIc. Creative AI prompt sharing platform."}
        </p>
        <div>
          {!about && <Link href="/about">About</Link>}
          <span>Terms{about ? " of Service" : ""}</span>
          <span>Privacy{about ? " Policy" : ""}</span>
          {!about && <span>Help</span>}
        </div>
      </footer>
    </div>
  );
}
export function Panel({
  title,
  children,
  className = "",
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}
export function Placeholder({
  label,
  className = "",
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div className={`placeholder ${className}`}>
      <Icon />
      {label && <span>{label}</span>}
    </div>
  );
}
export function Attribution({
  creatorName,
  creatorInstagramUrl,
  sourcePostUrl,
}: Pick<
  PublicRecipe,
  "creatorName" | "creatorInstagramUrl" | "sourcePostUrl"
>) {
  const href = creatorName
    ? creatorInstagramUrl || sourcePostUrl
    : sourcePostUrl;
  const safe = /^https?:\/\//i.test(href);
  const label = creatorName || "來源待確認 · 查看原始貼文";
  return safe ? (
    <a
      className="attribution"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
    >
      {label}
    </a>
  ) : (
    <span className="attribution">{creatorName || "來源待確認"}</span>
  );
}
export function Back({
  href = "/",
  children = "Back to Discover",
}: {
  href?: string;
  children?: ReactNode;
}) {
  return (
    <Link href={href} className="back">
      <Icon name="7057b" size={16} />
      {children}
    </Link>
  );
}
export function DataState({
  loading,
  error,
  retry,
}: {
  loading?: boolean;
  error?: unknown;
  retry?: () => void;
}) {
  return (
    <div className="state" role={error ? "alert" : "status"} aria-live="polite">
      <p>{loading ? "載入中…" : messageFor(error)}</p>
      {retry && (
        <button onClick={retry} className="button">
          重新載入
        </button>
      )}
    </div>
  );
}
export function Tags({ tags }: { tags: string[] }) {
  return (
    <div className="tags">
      {tags.map((tag) => (
        <span key={tag}>{tag}</span>
      ))}
    </div>
  );
}
export const categories = [
  "All",
  "Geometric",
  "Editorial",
  "Paper Cut",
  "Photography",
  "Abstract",
  "Illustration",
];
// The public contract has no category field. These local facets only match words
// explicitly present in a recipe's title/summary; they do not alter API records.
export function recipeTags(recipe: PublicRecipe): string[] {
  const text = recipe.title + " " + recipe.summary;
  return [
    ["Geometric", /geometric|幾何/i],
    ["Editorial", /editorial|編輯/i],
    ["Paper Cut", /paper.?cut|紙雕/i],
    ["Photography", /photo|照片/i],
    ["Abstract", /abstract|抽象/i],
    ["Illustration", /portrait|插畫|彩鉛/i],
  ]
    .filter(([, pattern]) => (pattern as RegExp).test(text))
    .map(([name]) => name as string);
}
