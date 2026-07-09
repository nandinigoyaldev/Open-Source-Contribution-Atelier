import { useState, useCallback } from "react";

export interface FeatureRequest {
  id: string;
  title: string;
  description: string;
  status: string;
  priority_score: number;
  total_votes: number;
  impact_score: number;
  created_at: string;
  user_vote?: "upvote" | "downvote" | null;
}

export function useFeatureRequests() {
  const [features, setFeatures] = useState<FeatureRequest[]>([
    {
      id: "1",
      title: "Interactive Git Graph in Sandbox",
      description: "Visualize git history changes in real-time when running git commit, branch, or merge commands.",
      status: "planned",
      priority_score: 85,
      total_votes: 42,
      impact_score: 9,
      created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    },
    {
      id: "2",
      title: "Django API client code generator",
      description: "Automatically generate frontend type-safe API clients from Django REST API schema.",
      status: "in-progress",
      priority_score: 75,
      total_votes: 28,
      impact_score: 8,
      created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  const refetch = useCallback(async () => {
    // Mock refetching
  }, []);

  const vote = useCallback(async (featureId: string, voteType: "upvote" | "downvote") => {
    setFeatures((prev) =>
      prev.map((f) => {
        if (f.id !== featureId) return f;
        const diff = voteType === "upvote" ? 1 : -1;
        return {
          ...f,
          total_votes: f.total_votes + diff,
          user_vote: voteType,
        };
      })
    );
  }, []);

  return {
    features,
    loading,
    error,
    refetch,
    vote,
  };
}
