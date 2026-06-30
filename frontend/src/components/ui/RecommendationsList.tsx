import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../../lib/api";
import { Link } from "react-router-dom";
import { ArrowRight, BookOpen, Code, TerminalSquare, X } from "lucide-react";

export interface Recommendation {
  id: number;
  content_type: "lesson" | "challenge" | "quiz";
  content_id: string;
  title: string;
  reason: string;
  priority_score: number;
}

export function RecommendationsList() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery<Recommendation[]>({
    queryKey: ["recommendations"],
    queryFn: () => fetchApi("/recommendations/"),
  });

  const dismissMutation = useMutation({
    mutationFn: (id: number) =>
      fetchApi(`/recommendations/${id}/dismiss/`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  if (isLoading) {
    return (
      <div className="p-8 text-center bg-white rounded-2xl border-4 border-dashed border-black dark:bg-[#151411] dark:border-[#2e2924]">
        <p className="font-bold text-muted dark:text-[#c4bbae]">Loading recommendations...</p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="p-8 text-center bg-white rounded-2xl border-4 border-dashed border-black dark:bg-[#151411] dark:border-[#2e2924]">
        <p className="font-bold text-muted dark:text-[#c4bbae]">No recommendations right now. Keep learning! 🌟</p>
      </div>
    );
  }

  const getIcon = (type: string) => {
    switch (type) {
      case "lesson":
        return <BookOpen size={24} className="text-primary" />;
      case "challenge":
        return <TerminalSquare size={24} className="text-accent" />;
      case "quiz":
        return <Code size={24} className="text-tertiary" />;
      default:
        return <BookOpen size={24} />;
    }
  };

  const getLink = (rec: Recommendation) => {
    switch (rec.content_type) {
      case "lesson":
        return `/lessons/${rec.content_id}`;
      case "challenge":
        return `/challenges/${rec.content_id}`;
      case "quiz":
        return `/quizzes/${rec.content_id}`;
      default:
        return `/`;
    }
  };

  return (
    <div className="space-y-4">
      {data.map((rec) => (
        <div
          key={rec.id}
          className="relative flex flex-col gap-2 p-5 rounded-lg border-4 border-black bg-surface-lowest shadow-card-sm hover:shadow-card hover:-translate-y-1 transition-all dark:bg-[#151411] dark:border-[#2e2924] dark:hover:bg-[#1f1c18]"
        >
          <button
            onClick={() => dismissMutation.mutate(rec.id)}
            className="absolute top-2 right-2 p-1 text-muted hover:text-black dark:hover:text-white transition-colors"
            title="Dismiss recommendation"
          >
            <X size={16} strokeWidth={3} />
          </button>
          
          <div className="flex items-center gap-3 mb-2">
            <div className="bg-white p-2 rounded-lg border-2 border-black shadow-card-sm dark:bg-[#0f0e0c] dark:border-[#2e2924]">
              {getIcon(rec.content_type)}
            </div>
            <div>
              <span className="font-black text-[9px] bg-black text-white px-2 py-0.5 rounded-full uppercase dark:bg-[#2e2924]">
                Suggested {rec.content_type}
              </span>
              <h3 className="font-black text-xl leading-tight mt-1 dark:text-[#f0ebe2] pr-6">
                {rec.title}
              </h3>
            </div>
          </div>
          
          <p className="text-sm font-bold text-muted dark:text-[#c4bbae] mb-2">
            {rec.reason}
          </p>

          <Link
            to={getLink(rec)}
            className="flex items-center justify-between text-xs font-black uppercase tracking-wider text-black group-hover:text-primary transition-colors dark:text-[#f0ebe2] dark:group-hover:text-primary mt-auto"
          >
            Start Now
            <ArrowRight size={16} strokeWidth={3} />
          </Link>
        </div>
      ))}
    </div>
  );
}
