import React from "react";

interface Props {
  name: string;
  xp: number;
  badges: string[];
  modulesCompleted: number;
  avatarUrl?: string;
  coverImageUrl?: string | null;
  maxXP?: number;
  rank?: string;
}

const BADGE_COLOURS: Record<string, string> = {
  "🌟": "bg-yellow-100 text-yellow-800 border-yellow-300",
  "🔥": "bg-orange-100 text-orange-800 border-orange-300",
  "💻": "bg-blue-100 text-blue-800 border-blue-300",
  "🚀": "bg-purple-100 text-purple-800 border-purple-300",
  "🎯": "bg-red-100 text-red-800 border-red-300",
  "🏆": "bg-green-100 text-green-800 border-green-300",
};

const getDefaultBadgeColour = (index: number): string => {
  const colours = [
    "bg-pink-100 text-pink-800 border-pink-300",
    "bg-indigo-100 text-indigo-800 border-indigo-300",
    "bg-teal-100 text-teal-800 border-teal-300",
    "bg-cyan-100 text-cyan-800 border-cyan-300",
  ];
  return colours[index % colours.length];
};

const getRankFromXP = (xp: number) => {
  if (xp >= 5000) return { label: "Legend", colour: "text-yellow-500" };
  if (xp >= 3000) return { label: "Expert", colour: "text-purple-500" };
  if (xp >= 1500) return { label: "Advanced", colour: "text-blue-600" };
  if (xp >= 500) return { label: "Intermediate", colour: "text-green-500" };
  return { label: "Beginner", colour: "text-gray-500" };
};

const getInitials = (name: string) => {
  return name
    .split(" ")
    .map((w) => w[0].toUpperCase())
    .slice(0, 2)
    .join("");
};

const getXPProgress = (xp: number, maxXP: number) => {
  return Math.min((xp / maxXP) * 100, 100);
};

const ContributorProfileCard: React.FC<Props> = ({
  name,
  xp,
  badges = [],
  modulesCompleted = 0,
  avatarUrl,
  coverImageUrl,
  maxXP = 5000,
  rank,
}) => {
  const initials = getInitials(name);
  const xpPercent = getXPProgress(xp, maxXP);
  const rankInfo = getRankFromXP(xp);
  const displayRank = rank ?? rankInfo.label;

  return (
    <article className="w-80 rounded-2xl bg-white shadow-lg border hover:shadow-xl transition">
      {/* HEADER */}
      <div 
        className="h-24 bg-gradient-to-r from-blue-600 to-purple-600 bg-cover bg-center rounded-t-2xl"
        style={coverImageUrl ? { backgroundImage: `url(${coverImageUrl})` } : {}}
      ></div>

      {/* AVATAR */}
      <div className="flex justify-center -mt-10">
        {avatarUrl ? (
          <img
            src={avatarUrl}
            alt="avatar"
            loading="lazy"
            className="w-20 h-20 rounded-full border-4 border-white"
          />
        ) : (
          <div className="w-20 h-20 rounded-full bg-blue-500 flex items-center justify-center text-white text-xl font-bold border-4 border-white">
            {initials}
          </div>
        )}
      </div>

      {/* BODY */}
      <div className="p-4 text-center">
        <h2 className="text-lg font-bold">{name}</h2>

        <p className={`text-sm ${rankInfo.colour}`}>{displayRank}</p>

        {/* XP */}
        <p className="text-sm mt-2">XP: {xp}</p>
        <div className="w-full bg-gray-200 h-2 rounded mt-1">
          <div
            className="bg-blue-500 h-2 rounded"
            style={{ width: `${xpPercent}%` }}
          ></div>
        </div>

        {/* BADGES */}
        <div className="mt-3">
          <p className="text-sm font-semibold">Badges</p>
          <div className="flex justify-center gap-2 mt-1 flex-wrap">
            {badges.map((badge, index) => {
              const colour =
                BADGE_COLOURS[badge] || getDefaultBadgeColour(index);
              return (
                <span
                  key={index}
                  className={`px-2 py-1 text-xs border rounded ${colour}`}
                >
                  {badge}
                </span>
              );
            })}
          </div>
        </div>

        {/* MODULES */}
        <p className="mt-3 text-sm">Modules Completed: {modulesCompleted}</p>
      </div>
    </article>
  );
};

export default ContributorProfileCard;
