

import PlayerSettings, {
  type ProfilePlayer,
} from "./components/PlayerSettings";
import Achievements from "./components/Achievements";
import { mockAchievements } from "./mocks/achievements";
import RunningHistory from "./components/RunningHistory";
import { mockRunningHistory } from "./mocks/runningHistory";
import RunningStats from "./components/RunningStats";
import { mockRunningStats } from "./mocks/runningStats";
import ConfirmationDialog from "./components/ConfirmationDialog";
import MapPlaceholder from "./components/MapPlaceholder";
import { useState } from "react";

import GameButton from "./components/GameButton";
import PlayerProfileCard from "./components/PlayerProfileCard";
import Leaderboard from "./components/Leaderboard";
import { mockLeaderboard } from "./mocks/leaderboard";

type Page =
  | "game"
  | "leaderboard"
  | "history"
  | "achievements"
  | "profile";


export default function PreviewApp() {
  const [page, setPage] = useState<Page>("game");
  const [showConfirm, setShowConfirm] = useState(false);

  const [players, setPlayers] = useState<ProfilePlayer[]>(
    mockLeaderboard
  );

  const currentPlayer = players.find(
    (player) => player.id === "3"
  );

  const rankedPlayers = [...players].sort(
    (a, b) => b.score - a.score
  );

  const currentRank =
    rankedPlayers.findIndex(
      (player) => player.id === currentPlayer?.id
    ) + 1;

  return (

    <main className="flex min-h-screen flex-col items-center gap-8 bg-[#F7F2EA] p-6">
      <span className="text-lg font-black text-black sm:text-xl">
        CONQUEST RUNNER
      </span>

      
<nav
  aria-label="Main navigation"
  className="w-full max-w-5xl border-[3px] border-black bg-white p-3 shadow-[6px_6px_0_#111] sm:p-5"
>
  {/* Navigation header */}
  <div className="mb-4 flex items-center justify-between gap-3">
    <span className="text-lg font-black text-black sm:text-xl">
      CONQUEST RUNNER
    </span>

    <span
      aria-hidden="true"
      className="flex h-10 w-10 shrink-0 items-center justify-center border-2 border-black bg-yellow-300 text-xl"
    >
      🎮
    </span>
  </div>

  {/* Colorful navigation tabs */}
  <div className="grid grid-cols-5 gap-1.5 sm:gap-3">
    {(
      [
        {
          id: "game",
          label: "GAME",
          icon: "🗺️",
          color: "bg-teal-300",
        },
        {
          id: "leaderboard",
          label: "LEADERBOARD",
          icon: "🏆",
          color: "bg-pink-300",
        },
        {
          id: "history",
          label: "HISTORY",
          icon: "🕒",
          color: "bg-yellow-300",
        },
        {
          id: "achievements",
          label: "ACHIEVEMENTS",
          icon: "🏅",
          color: "bg-orange-300",
        },
        {
          id: "profile",
          label: "PROFILE",
          icon: "👤",
          color: "bg-purple-300",
        },
      ] as const
    ).map((item) => (
      <button
        key={item.id}
        type="button"
        onClick={() => setPage(item.id)}
        aria-current={page === item.id ? "page" : undefined}
        aria-label={item.label}
        className={`flex min-w-0 flex-col items-center justify-center gap-2 border-2 border-black px-1 py-3 text-black transition-all duration-200 hover:-translate-y-1 hover:shadow-[3px_3px_0_#111] sm:px-3 ${
          page === item.id
            ? `${item.color} shadow-[4px_4px_0_#111]`
            : "bg-gray-100 hover:bg-gray-200"
        }`}
      >
        <span aria-hidden="true" className="text-xl sm:text-2xl">
          {item.icon}
        </span>

        <span className="max-w-full break-words text-center text-[9px] font-black leading-tight sm:text-xs md:text-sm">
          {item.label}
        </span>
      </button>
    ))}
  </div>
</nav>


      

{page === "game" ? (
  <div className="flex w-full max-w-5xl flex-col gap-6">

    {/* Running Dashboard at the top */}
    <RunningStats
      stats={mockRunningStats}
      isDemo={true}
    />

    {/* Map and Player Profile below */}
    <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">

      <MapPlaceholder />

      <div className="flex min-w-0 flex-col items-center gap-6">
        <PlayerProfileCard
          username={currentPlayer?.name ?? "Player One"}
          rank={currentRank || 0}
          territories={currentPlayer?.territories ?? 0}
/>

        <GameButton
          label="START RUN"
          onClick={() => setShowConfirm(true)}
        />
      </div>
    </div>
  </div>

) : page === "leaderboard" ? (
  <Leaderboard players={players} />
) : page === "history" ? (
  <div className="w-full max-w-3xl">
    <RunningHistory records={mockRunningHistory} />
  </div>

) : page === "achievements" ? (
  <Achievements achievements={mockAchievements} />
) : (
  <PlayerSettings
    players={players}
    onChange={setPlayers}
  />
)}

    <ConfirmationDialog
      open={showConfirm}
      onCancel={() => setShowConfirm(false)}
      onConfirm={() => {
      setShowConfirm(false);
        alert("UI Preview only — GPS has not started.");
     }}
/>  
    </main>
  );
}
