/**
 * Feature request list with voting and prioritization.
 *
 * @file FeatureRequestList.tsx
 * @location frontend/src/components/FeatureRequests/FeatureRequestList.tsx
 */

import React, { useState, useEffect } from "react";
import { useFeatureRequests } from "../../hooks/useFeatureRequests";
import { FeatureCard } from "./FeatureCard";
import { VotingButton } from "./VotingButton";
import { ImpactEffortMatrix } from "./ImpactEffortMatrix";
import { RoadmapView } from "./RoadmapView";

interface FeatureRequestListProps {
  initialFilter?: string;
}

export const FeatureRequestList: React.FC<FeatureRequestListProps> = ({
  initialFilter = "all",
}) => {
  const [filter, setFilter] = useState(initialFilter);
  const [sortBy, setSortBy] = useState("priority");
  const { features, loading, error, refetch, vote } = useFeatureRequests();

  const getFilteredFeatures = () => {
    let filtered = features || [];

    // Apply filter
    if (filter !== "all") {
      filtered = filtered.filter((f) => f.status === filter);
    }

    // Apply sorting
    switch (sortBy) {
      case "priority":
        filtered.sort((a, b) => b.priority_score - a.priority_score);
        break;
      case "votes":
        filtered.sort((a, b) => b.total_votes - a.total_votes);
        break;
      case "recent":
        filtered.sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        );
        break;
      case "impact":
        filtered.sort((a, b) => b.impact_score - a.impact_score);
        break;
    }

    return filtered;
  };

  const handleVote = async (
    featureId: string,
    voteType: "upvote" | "downvote",
  ) => {
    await vote(featureId, voteType);
    refetch();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="spinner" />
        <span className="ml-3 text-gray-400">Loading features...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12 text-red-400">
        <p>Error loading features: {error.message}</p>
        <button
          onClick={refetch}
          className="mt-4 px-4 py-2 bg-blue-600 rounded-lg"
        >
          Retry
        </button>
      </div>
    );
  }

  const filteredFeatures = getFilteredFeatures();

  return (
    <div className="space-y-6">
      {/* Filters and Sorting */}
      <div className="flex flex-wrap gap-4 items-center justify-between bg-dark-800/50 p-4 rounded-xl border border-dark-700">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setFilter("all")}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === "all"
                ? "bg-blue-600 text-white"
                : "bg-dark-700 text-gray-400 hover:bg-dark-600"
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilter("idea")}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === "idea"
                ? "bg-blue-600 text-white"
                : "bg-dark-700 text-gray-400 hover:bg-dark-600"
            }`}
          >
            Ideas
          </button>
          <button
            onClick={() => setFilter("under_review")}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === "under_review"
                ? "bg-yellow-600 text-white"
                : "bg-dark-700 text-gray-400 hover:bg-dark-600"
            }`}
          >
            Under Review
          </button>
          <button
            onClick={() => setFilter("planned")}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === "planned"
                ? "bg-purple-600 text-white"
                : "bg-dark-700 text-gray-400 hover:bg-dark-600"
            }`}
          >
            Planned
          </button>
          <button
            onClick={() => setFilter("in_progress")}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === "in_progress"
                ? "bg-blue-600 text-white"
                : "bg-dark-700 text-gray-400 hover:bg-dark-600"
            }`}
          >
            In Progress
          </button>
          <button
            onClick={() => setFilter("completed")}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === "completed"
                ? "bg-green-600 text-white"
                : "bg-dark-700 text-gray-400 hover:bg-dark-600"
            }`}
          >
            Completed
          </button>
        </div>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="bg-dark-700 text-gray-300 px-4 py-2 rounded-lg border border-dark-600 focus:outline-none focus:border-blue-500"
        >
          <option value="priority">Sort by Priority</option>
          <option value="votes">Sort by Votes</option>
          <option value="recent">Sort by Recent</option>
          <option value="impact">Sort by Impact</option>
        </select>
      </div>

      {/* Impact vs Effort Matrix */}
      <ImpactEffortMatrix features={features || []} />

      {/* Feature List */}
      <div className="space-y-4">
        {filteredFeatures.map((feature) => (
          <FeatureCard key={feature.id} feature={feature} onVote={handleVote} />
        ))}

        {filteredFeatures.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p>No feature requests found</p>
          </div>
        )}
      </div>

      {/* Roadmap View */}
      <RoadmapView />
    </div>
  );
};
