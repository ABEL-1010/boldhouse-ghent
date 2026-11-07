import { SystemStatusCard } from "@/features/system-status";

export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-6 py-12">
      <header className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight">Sentinel</h1>
        <p className="text-muted-foreground">Flight recorder and anomaly detector for AI agents.</p>
      </header>
      <SystemStatusCard />
    </main>
  );
}
