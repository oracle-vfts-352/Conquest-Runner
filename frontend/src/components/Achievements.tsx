
import { useState } from "react";

export type AchievementCategory =
  | "distance"
  | "territory"
  | "consistency"
  | "ranking";

export type Achievement = {
  id: string;
  title: string;
  description: string;
  category: AchievementCategory;
  icon: string;
  progress: number;
  target: number;
  unit: string;
};

type AchievementsProps = {
  achievements: Achievement[];
};

type Filter = "all" | AchievementCategory;

const categories = [
  {
    id: "distance",
    label: "DISTANCE",
    icon: "🏃",
    color: "bg-teal-300",
  },
  {
    id: "territory",
    label: "TERRITORY",
    icon: "🚩",
    color: "bg-pink-300",
  },
  {
    id: "consistency",
    label: "CONSISTENCY",
    icon: "📅",
    color: "bg-yellow-300",
  },
  {
    id: "ranking",
    label: "RANKING",
    icon: "👑",
    color: "bg-purple-300",
  },
] as const;

function isUnlocked(achievement: Achievement) {
  return achievement.progress >= achievement.target;
}

function getPercentage(achievement: Achievement) {
  if (achievement.target <= 0) return 0;

  return Math.min(
    100,
    Math.max(
      0,
      (achievement.progress / achievement.target) * 100
    )
  );
}

export default function Achievements({
  achievements,
}: AchievementsProps) {
  const [filter, setFilter] = useState<Filter>("all");

  const unlockedCount = achievements.filter(isUnlocked).length;

  const overallPercentage =
    achievements.length === 0
      ? 0
      : Math.round(
          (unlockedCount / achievements.length) * 100
        );

  const filteredAchievements =
    filter === "all"
      ? achievements
      : achievements.filter(
          (achievement) => achievement.category === filter
        );

  return (
    <section className="w-full max-w-5xl space-y-6 border-[3px] border-black bg-white p-4 text-black shadow-[6px_6px_0_#111] sm:p-6">

      {/* HEADER */}
      <div className="flex flex-wrap items-center gap-4">
        <span
          aria-hidden="true"
          className="flex h-14 w-14 items-center justify-center border-[3px] border-black bg-yellow-300 text-3xl"
        >
          🏅
        </span>

        <div>
          <h2 className="text-2xl font-black sm:text-3xl">
            ACHIEVEMENTS
          </h2>
          <p className="text-sm text-gray-600">
            Complete challenges and collect badges!
          </p>
        </div>
      </div>

      <p className="text-xs text-gray-600">
        Preview progress — achievement rules are not yet
        connected to the game backend.
      </p>

      {/* OVERALL PROGRESS */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">

        <div className="border-[3px] border-black bg-teal-300 p-4 shadow-[4px_4px_0_#111]">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-black">
              OVERALL PROGRESS
            </h3>

            <span className="font-black">
              {unlockedCount} / {achievements.length}
              {" "}
              ({overallPercentage}%)
            </span>
          </div>

          <div
            role="progressbar"
            aria-label="Overall achievement progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={overallPercentage}
            className="h-5 overflow-hidden border-2 border-black bg-white"
          >
            <div
              className="h-full bg-pink-400 transition-all duration-300"
              style={{ width: `${overallPercentage}%` }}
            />
          </div>
        </div>

        <div className="grid grid-cols-4 gap-2">
          {categories.map((category) => {
            const count = achievements.filter(
              (achievement) =>
                achievement.category === category.id
            ).length;

            return (
              <div
                key={category.id}
                className={`flex flex-col items-center justify-center border-2 border-black p-2 text-center ${category.color}`}
              >
                <span aria-hidden="true" className="text-xl">
                  {category.icon}
                </span>

                <span className="text-lg font-black">
                  {count}
                </span>

                <span className="break-words text-[9px] font-bold leading-tight sm:text-[11px]">
                  {category.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* CATEGORY FILTER */}
      <div
        aria-label="Achievement categories"
        className="flex flex-wrap gap-2"
      >
        <button
          type="button"
          onClick={() => setFilter("all")}
          aria-pressed={filter === "all"}
          className={`border-2 border-black px-3 py-2 text-xs font-black transition-colors ${
            filter === "all"
              ? "bg-teal-300"
              : "bg-white hover:bg-gray-100"
          }`}
        >
          ALL ({achievements.length})
        </button>

        {categories.map((category) => {
          const count = achievements.filter(
            (achievement) =>
              achievement.category === category.id
          ).length;

          return (
            <button
              key={category.id}
              type="button"
              onClick={() => setFilter(category.id)}
              aria-pressed={filter === category.id}
              className={`border-2 border-black px-3 py-2 text-xs font-black transition-colors ${
                filter === category.id
                  ? category.color
                  : "bg-white hover:bg-gray-100"
              }`}
            >
              {category.label} ({count})
            </button>
          );
        })}
      </div>

      {/* ACHIEVEMENT CARDS */}
      {filteredAchievements.length === 0 ? (
        <div className="border-2 border-dashed border-black p-6 text-center">
          <p className="font-bold">
            No achievements found.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {filteredAchievements.map((achievement) => {
            const unlocked = isUnlocked(achievement);
            const percentage = getPercentage(achievement);

            const progress =
  typeof achievement.progress === "number"
    ? achievement.progress
    : 0;

const target =
  typeof achievement.target === "number"
    ? achievement.target
    : 1;

            const category = categories.find(
              (item) => item.id === achievement.category
            );

            return (
              <article
                key={achievement.id}
                className={`flex min-w-0 flex-col gap-4 border-[3px] border-black p-4 shadow-[4px_4px_0_#111] ${
                  unlocked ? "bg-teal-100" : "bg-gray-50"
                }`}
              >
                <div className="flex items-start gap-3">
                  <div
                    aria-hidden="true"
                    className={`flex h-16 w-16 shrink-0 items-center justify-center border-2 border-black text-3xl ${
                      unlocked
                        ? category?.color ?? "bg-yellow-300"
                        : "bg-gray-200"
                    }`}
                  >
                    {unlocked ? achievement.icon : "🔒"}
                  </div>

                  <div className="min-w-0 flex-1">
                    <p className="break-words text-lg font-black">
                      {achievement.title}
                    </p>

                    <p className="mt-1 text-sm text-gray-700">
                      {achievement.description}
                    </p>
                  </div>
                </div>

                {/* PROGRESS */}
                <div className="mt-auto space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-bold text-gray-600">
                      PROGRESS
                    </span>

                    
                    <span className="text-xs font-bold">
                      {Math.min(progress, target).toLocaleString()}
                      {" / "}
                      {target.toLocaleString()}
                      {" "}
                      {achievement.unit}
                    </span>

                  </div>

                  <div
                    role="progressbar"
                    aria-label={`${achievement.title} progress`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={Math.round(percentage)}
                    className="h-3 overflow-hidden border-2 border-black bg-white"
                  >
                    <div
                      className={`h-full transition-all duration-300 ${
                        unlocked
                          ? "bg-green-400"
                          : "bg-teal-300"
                      }`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>

                  <div className="flex justify-end">
                    <span
                      className={`border-2 border-black px-3 py-1 text-xs font-black ${
                        unlocked
                          ? "bg-green-300"
                          : "bg-gray-200"
                      }`}
                    >
                      {unlocked
                        ? "✓ UNLOCKED"
                        : "🔒 LOCKED"}
                    </span>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
