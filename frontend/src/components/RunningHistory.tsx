
export type RunRecord = {
  id: string;
  title: string;
  date: string;
  distanceKm: number;
  durationSeconds: number;
};

type RunningHistoryProps = {
  records: RunRecord[];
};

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(
      remainingSeconds
    ).padStart(2, "0")}`;
  }

  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

function getRunStyle(title: string) {
  const lowerTitle = title.toLowerCase();

  if (lowerTitle.includes("morning")) {
    return {
      icon: "☀️",
      color: "bg-pink-200",
    };
  }

  if (lowerTitle.includes("evening")) {
    return {
      icon: "🌙",
      color: "bg-teal-200",
    };
  }

  return {
    icon: "🏃",
    color: "bg-yellow-200",
  };
}

export default function RunningHistory({
  records,
}: RunningHistoryProps) {
  const totalRuns = records.length;

  const totalDistance = records.reduce(
    (total, record) => total + record.distanceKm,
    0
  );

  return (
    <section className="w-full space-y-5 border-[3px] border-black bg-white p-4 text-black shadow-[6px_6px_0_#111] sm:p-6">

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-black sm:text-3xl">
          RUNNING HISTORY
        </h2>

        <div className="flex h-12 w-12 items-center justify-center border-[3px] border-black bg-teal-300 text-2xl">
          🕘
        </div>
      </div>

      <p className="text-sm text-gray-600">
        Preview records — not connected to the backend.
      </p>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="border-[3px] border-black bg-yellow-300 p-4 shadow-[4px_4px_0_#111]">
          <p className="text-sm font-bold">
            TOTAL RUNS
          </p>

          <p className="mt-2 text-3xl font-black">
            {totalRuns}
          </p>
        </div>

        <div className="border-[3px] border-black bg-teal-300 p-4 shadow-[4px_4px_0_#111]">
          <p className="text-sm font-bold">
            TOTAL DISTANCE
          </p>

          <p className="mt-2 text-3xl font-black">
            {totalDistance.toFixed(2)} km
          </p>
        </div>
      </div>

      {/* Running records */}
      {records.length === 0 ? (
        <div className="border-2 border-dashed border-black bg-gray-50 p-6 text-center">
          <p className="text-lg font-bold">
            NO RUNS YET
          </p>

          <p className="mt-2 text-sm text-gray-600">
            Your completed running activities will appear here.
          </p>
        </div>
      ) : (
        <ol className="space-y-4">
          {records.map((record) => {
            const style = getRunStyle(record.title);

            return (
              <li
                key={record.id}
                className="space-y-4 border-[3px] border-black bg-white p-4 shadow-[4px_4px_0_#111]"
              >
                {/* Run title and date */}
                <div className="flex items-center gap-3">
                  <div
                    className={`flex h-12 w-12 shrink-0 items-center justify-center border-2 border-black text-2xl ${style.color}`}
                    aria-hidden="true"
                  >
                    {style.icon}
                  </div>

                  <div className="min-w-0 flex-1">
                    <h3 className="break-words text-lg font-black">
                      {record.title}
                    </h3>

                    <p className="text-sm text-gray-600">
                      {record.date}
                    </p>
                  </div>
                </div>

                {/* Divider */}
                <div className="border-t-2 border-black" />

                {/* Running metrics */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs font-bold text-gray-500">
                      DISTANCE
                    </p>

                    <p className="mt-1 text-xl font-black">
                      {record.distanceKm.toFixed(2)} km
                    </p>
                  </div>

                  <div>
                    <p className="text-xs font-bold text-gray-500">
                      DURATION
                    </p>

                    <p className="mt-1 text-xl font-black">
                      {formatDuration(record.durationSeconds)}
                    </p>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
