
type PlayerProfileCardProps = {
  username: string;
  rank: number;
  territories: number;
};

function PlayerProfileCard({
  username,
  rank,
  territories,
}: PlayerProfileCardProps) {
  return (
    <section
      aria-label="Player profile"
      className="w-full max-w-sm border-[3px] border-black bg-white p-5 shadow-[6px_6px_0_#111]"
    >
      {/* Player Name */}
      <div className="mb-5 flex items-center gap-4">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center border-2 border-black bg-pink-400 text-2xl font-black text-black">
          {username.charAt(0).toUpperCase()}
        </div>

        <div>
          <h2 className="text-xl font-black !text-black">
            {username}
          </h2>
          <p className="text-sm text-gray-600">
            ConquestRunner Player
          </p>
        </div>
      </div>

      {/* Player Statistics */}
      <div className="grid grid-cols-2 gap-3">
        <div className="border-2 border-black bg-teal-300 p-3">
          <p className="text-xs font-bold text-black">
            TERRITORIES
          </p>
          <p className="text-3xl font-black text-black">
            {territories}
          </p>
        </div>

        <div className="border-2 border-black bg-yellow-300 p-3">
          <p className="text-xs font-bold text-black">
            RANK
          </p>
          <p className="text-3xl font-black text-black">
            #{rank}
          </p>
        </div>
      </div>
    </section>
  );
}

export default PlayerProfileCard;
