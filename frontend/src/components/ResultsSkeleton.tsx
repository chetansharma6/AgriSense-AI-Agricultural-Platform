import { LandSummarySkeleton } from "./LandSummary";

export default function ResultsSkeleton({ slow = false }: { slow?: boolean }) {
  return (
    <div>
      <LandSummarySkeleton slow={slow} />
      <div className="mt-8 grid gap-4 lg:grid-cols-3" aria-hidden="true">
        {[0, 1, 2].map((key) => (
          <div key={key} className="card animate-pulse border border-field/15 bg-white/50 motion-reduce:animate-none">
            <div className="flex justify-between gap-4"><div className="h-7 w-1/2 rounded bg-soil/10" /><div className="h-16 w-16 rounded-lg bg-soil/10" /></div>
            <div className="mt-3 h-4 w-3/4 rounded bg-soil/10" />
            <div className="mt-6 space-y-3">{[0, 1, 2].map((bar) => <div key={bar} className="h-3 rounded bg-soil/10" />)}</div>
            <div className="mt-6 h-4 w-4/5 rounded bg-soil/10" />
          </div>
        ))}
      </div>
    </div>
  );
}
