
export type LeaderboardPlayer = {
  id: string;
  name: string;
  score: number;
  territories: number;
};

type LeaderboardProps = {
  players: LeaderboardPlayer[];
};

export default function Leaderboard({
  players,
}: LeaderboardProps) {
  const rankedPlayers = [...players].sort(
    (a, b) => b.score - a.score
  );

  return (
    <section
      aria-label="Leaderboard"
      className="w-full max-w-2xl border-[3px] border-black bg-white p-5 shadow-[6px_6px_0_#111]"
    >
      <h2 className="mb-2 text-2xl font-black !text-black">
        LEADERBOARD
      </h2>

      <p className="mb-5 text-sm text-gray-600">
        Demo rankings — sample player data
      </p>

      {rankedPlayers.length === 0 ? (
        <p role="status" className="text-gray-700">
          No players found.
        </p>
      ) : (
        <ol className="space-y-3">
          {rankedPlayers.map((player, index) => (
            <li
              key={player.id}
              className="flex flex-wrap items-center gap-3 border-2 border-black bg-yellow-200 p-4 text-black"
            >
              <span className="text-xl font-black">
                #{index + 1}
              </span>

              <div className="min-w-0 flex-1">
                <p className="break-words font-bold">
                  {player.name}
                </p>

                <p className="text-sm">
                  {player.territories} territories
                </p>
              </div>

              <span className="font-black">
                {player.score.toLocaleString()} pts
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
