
export type RunningStatsData = {
  distanceKm: number;
  durationSeconds: number;
  paceSecondsPerKm: number | null;
  status: "idle" | "running" | "paused" | "completed";
};

type RunningStatsProps = {
  stats: RunningStatsData;
  isDemo?: boolean;
};

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);

  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

export default function RunningStats({
  stats,
  isDemo = false,
}: RunningStatsProps) {
  const cards = [
    {
      label: "DISTANCE",
      value: stats.distanceKm.toFixed(2),
      unit: "km",
      color: "bg-[#39DCCA]",
    },
    {
      label: "DURATION",
      value: formatTime(stats.durationSeconds),
      unit: "min:sec",
      color: "bg-[#F9EA49]",
    },
    {
      label: "AVG PACE",
      value:
        stats.paceSecondsPerKm === null
          ? "--"
          : formatTime(stats.paceSecondsPerKm),
      unit: "min/km",
      color: "bg-[#FF9BCC]",
    },
    {
      label: "RUN STATUS",
      value: stats.status === "completed"
      ? "DONE"
      : stats.status.toUpperCase(),
      unit: isDemo ? "Preview only" : "Run state",
      color: "bg-[#FFB876]",
    },
  ];

  return (
    <section
      aria-label="Running statistics"
      className="w-full border-[3px] border-black bg-white p-4 shadow-[6px_6px_0_#111]"
    >
      <h2 className="mb-2 text-xl font-black !text-black">
        RUNNING DASHBOARD
      </h2>

      {isDemo && (
        <p className="mb-4 text-sm font-bold text-gray-700">
          DEMO DATA — Not connected to GPS
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {cards.map((card) => (
          <div
            key={card.label}
            className={`min-w-0 border-2 border-black p-4 ${card.color}`}
          >
            <p className="text-xs font-black text-black">
              {card.label}
            </p>

            
            <p className="mt-2 break-words text-xl font-black leading-tight text-black sm:text-2xl">
              {card.value}
            </p>


            <p className="mt-1 text-sm text-gray-800">
              {card.unit}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
