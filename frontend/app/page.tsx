import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <div className="text-center">
        <h1 className="text-3xl font-bold">Ads Engine</h1>
        <p className="mt-2 text-muted-foreground">
          AI-powered ad management — Phase 1 scaffold ready
        </p>
      </div>
      <div className="flex gap-4">
        <Link
          href="/dashboard"
          className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:opacity-90"
        >
          Go to Dashboard
        </Link>
        <Link
          href="/approvals"
          className="rounded-md border px-4 py-2 text-sm hover:bg-muted"
        >
          Approval Queue
        </Link>
      </div>
    </main>
  );
}
