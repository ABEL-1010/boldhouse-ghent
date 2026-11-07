import { LiveSession } from "@/features/live-session";
import { SystemStatusCard } from "@/features/system-status";

export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-8 px-6 py-10">
      <header className="flex flex-wrap items-start justify-between gap-6">
        <div className="space-y-1">
          <h1 className="text-3xl font-semibold tracking-tight">Sentinel</h1>
          <p className="text-muted-foreground">
            Flight recorder and anomaly detector for AI agents. The AI does the work; the human
            stays in charge.
          </p>
        </div>
        <SystemStatusCard />
      </header>
      <LiveSession />
    </main>
  );
}
