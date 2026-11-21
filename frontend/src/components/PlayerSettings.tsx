
import { useState } from "react";
import type { LeaderboardPlayer } from "./Leaderboard";

export type ProfilePlayer = LeaderboardPlayer & {
  avatar?: string;
  avatarColor?: string;
};

type Props = {
  players: ProfilePlayer[];
  onChange: (players: ProfilePlayer[]) => void;
};

const avatars = ["🏃", "🥷", "🤖", "🦊"];

const colors = [
  "#FF9BCC",
  "#39DCCA",
  "#F9EA49",
  "#FFB876",
  "#B8A4FF",
];

export default function PlayerSettings({
  players,
  onChange,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const [nickname, setNickname] = useState("");
  const [avatar, setAvatar] = useState("🏃");
  const [avatarColor, setAvatarColor] = useState("#FF9BCC");

  function startAdd() {
    setAdding(true);
    setEditingId(null);
    setNickname("");
  }

  function addPlayer() {
    const name = nickname.trim();
    if (!name || name.length > 24) return;

    const newPlayer: ProfilePlayer = {
      id: crypto.randomUUID(),
      name,
      score: 0,
      territories: 0,
      avatar: "🏃",
      avatarColor: "#FF9BCC",
    };

    onChange([...players, newPlayer]);
    setAdding(false);
    setNickname("");
  }

  function startEdit(player: ProfilePlayer) {
    setAdding(false);
    setEditingId(player.id);
    setNickname(player.name);
    setAvatar(player.avatar ?? "🏃");
    setAvatarColor(player.avatarColor ?? "#FF9BCC");
  }

  function saveChanges(id: string) {
    const name = nickname.trim();
    if (!name || name.length > 24) return;

    const updatedPlayers = players.map((player) =>
      player.id === id
        ? { ...player, name, avatar, avatarColor }
        : player
    );

    onChange(updatedPlayers);
    setEditingId(null);

  }


function requestDelete(id: string) {
  setDeleteId(id);
}

function confirmDelete() {
  if (deleteId === null) return;

  onChange(
    players.filter((player) => player.id !== deleteId)
  );

  if (editingId === deleteId) {
    setEditingId(null);
  }

  setDeleteId(null);
}


  return (
    <section className="w-full max-w-3xl space-y-5 text-black">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-3xl font-black">
          PLAYER PROFILES
        </h2>

        <button
          type="button"
          onClick={() => {
            if (adding) {
              setAdding(false);
            } else {
              startAdd();
            }
          }}

className="border-[3px] border-black bg-black px-5 py-3 font-bold text-white shadow-[4px_4px_0_#FF9BCC] transition-all duration-200 hover:-translate-y-1 hover:bg-teal-300 hover:text-black hover:shadow-[6px_6px_0_#000]"
  >
          {adding ? "CANCEL" : "+ ADD PLAYER"}
        </button>
      </div>

      {adding && (
        <div className="space-y-4 border-[3px] border-black bg-white p-5 shadow-[6px_6px_0_#111]">
          <h3 className="text-xl font-black">CREATE PLAYER</h3>

          <label htmlFor="new-name" className="block font-bold">
            PLAYER NAME
          </label>

          <input
            id="new-name"
            value={nickname}
            maxLength={24}
            onChange={(e) => setNickname(e.target.value)}
            placeholder="Enter player name"
            className="w-full border-2 border-black bg-white p-3"
          />

          <p className="text-sm text-gray-600">
            New players start with 0 points and 0 territories.
          </p>

          <button
            type="button"
            onClick={addPlayer}
            disabled={!nickname.trim()}
            className="border-[3px] border-black bg-yellow-300 px-5 py-3 font-bold disabled:opacity-50"
          >
            CREATE PLAYER
          </button>
        </div>
      )}

      {players.length === 0 && <p>No players yet.</p>}

      {players.map((player) => (
        <div
          key={player.id}
          className="space-y-5 border-[3px] border-black bg-white p-5 shadow-[6px_6px_0_#111]"
        >
          <div className="flex flex-wrap items-center gap-4">
            <div
              className="flex h-16 w-16 items-center justify-center border-2 border-black text-3xl"
              style={{
                backgroundColor: player.avatarColor ?? "#FF9BCC",
              }}
            >
              {player.avatar ?? "🏃"}
            </div>

            <div className="min-w-0 flex-1">
              <p className="break-words text-xl font-black">
                {player.name}
              </p>

              <p className="text-sm text-gray-600">
                {player.score.toLocaleString()} pts
                {" · "}
                {player.territories} territories
              </p>
            </div>

            
<div className="flex flex-wrap gap-3">
  {/* EDIT button — keep existing functionality */}
  <button
    type="button"
    aria-expanded={editingId === player.id}
    onClick={() => {
      if (editingId === player.id) {
        setEditingId(null);
      } else {
        startEdit(player);
      }
    }}
    className="border-[3px] border-black bg-yellow-300 px-5 py-3 font-bold text-black hover:bg-yellow-400"
  >
    {editingId === player.id ? "CLOSE" : "EDIT"}
  </button>

  {/* DELETE button — new */}
  <button
    type="button"
    onClick={() => requestDelete(player.id)}
    className="border-[3px] border-black bg-red-400 px-5 py-3 font-bold text-black transition-colors hover:bg-red-600 hover:text-white"
  >
    DELETE
  </button>
</div>

          </div>

          {editingId === player.id && (
            <div className="space-y-5 border-t-2 border-black pt-5">
              <div className="space-y-2">
                <label
                  htmlFor={`name-${player.id}`}
                  className="block font-bold"
                >
                  NEW NICKNAME
                </label>

                <input
                  id={`name-${player.id}`}
                  value={nickname}
                  maxLength={24}
                  onChange={(e) => setNickname(e.target.value)}
                  className="w-full border-2 border-black bg-white p-3"
                />
              </div>

              <fieldset>
                <legend className="mb-3 font-bold">
                  CHOOSE YOUR AVATAR
                </legend>

                <div className="flex flex-wrap gap-3">
                  {avatars.map((item) => (
                    <button
                      key={item}
                      type="button"
                      aria-label={`Select avatar ${item}`}
                      aria-pressed={avatar === item}
                      onClick={() => setAvatar(item)}
                      className={`h-14 w-14 border-[3px] border-black text-2xl ${
                        avatar === item ? "bg-teal-300" : "bg-white"
                      }`}
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </fieldset>

              <fieldset>
                <legend className="mb-3 font-bold">
                  AVATAR BACKGROUND COLOR
                </legend>

                <div className="flex flex-wrap gap-3">
                  {colors.map((color) => (
                    <button
                      key={color}
                      type="button"
                      aria-label={`Select background color ${color}`}
                      aria-pressed={avatarColor === color}
                      onClick={() => setAvatarColor(color)}
                      style={{ backgroundColor: color }}
                      className="flex h-12 w-12 items-center justify-center border-[3px] border-black font-bold"
                    >
                      {avatarColor === color ? "✓" : ""}
                    </button>
                  ))}
                </div>
              </fieldset>

              <div
                className="flex items-center gap-3 border-2 border-black p-3"
                style={{ backgroundColor: avatarColor }}
              >
                <span className="text-3xl">{avatar}</span>
                <span className="font-bold">AVATAR PREVIEW</span>
              </div>

              <button
                type="button"
                onClick={() => saveChanges(player.id)}
                disabled={!nickname.trim()}
                className="border-[3px] border-black bg-teal-300 px-5 py-3 font-bold disabled:opacity-50"
              >
                SAVE CHANGES
              </button>
            </div>
          )}
        </div>
      ))}


{deleteId !== null && (
  <div
    role="alertdialog"
    aria-modal="true"
    aria-labelledby="delete-title"
    aria-describedby="delete-description"
    className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
  >
    <div className="w-full max-w-md border-[3px] border-black bg-white p-6 text-black shadow-[8px_8px_0_#111]">
      <h3
        id="delete-title"
        className="mb-3 text-2xl font-black"
      >
        DELETE PLAYER?
      </h3>

      <p id="delete-description" className="mb-6">
        Are you sure you want to delete{" "}
        <strong>
          {players.find((player) => player.id === deleteId)?.name}
        </strong>
        ?
      </p>

      <div className="mt-8 flex flex-wrap justify-end gap-3">
        <button
          type="button"
          onClick={() => setDeleteId(null)}
          className="border-[3px] border-black bg-white px-5 py-3 font-bold text-black hover:bg-gray-200"
        >
          CANCEL
        </button>

        <button
          type="button"
          onClick={confirmDelete}
          className="border-[3px] border-black bg-red-500 px-5 py-3 font-bold text-white hover:bg-red-700"
        >
          YES, DELETE
        </button>
      </div>
    </div>
  </div>
)}

    </section>
  );
}
