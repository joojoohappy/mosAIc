import Link from "next/link";
export default function NotFound() {
  return (
    <main className="state">
      <h1>找不到這個頁面</h1>
      <Link href="/">Back to Discover</Link>
    </main>
  );
}
