import React, { useEffect, useState } from "react";
import { fetchApi } from "../lib/api";
import { LearningPathway, LessonNode } from "../components/LearningPathway";
import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

export const PathwayPage: React.FC = () => {
  const [lessons, setLessons] = useState<LessonNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchApi("/content/roadmap/")
      .then((data) => {
        if (data && data.track) {
          setLessons(data.track);
        } else {
          setError("Invalid roadmap data format");
        }
      })
      .catch((err) => {
        console.error(err);
        setError("Failed to load curriculum roadmap");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="pt-24 max-w-7xl mx-auto px-4 flex justify-center items-center h-screen">
        <div className="font-bold text-2xl animate-pulse">
          Loading Pathway...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="pt-24 max-w-7xl mx-auto px-4">
        <div className="p-8 text-center bg-red-100 rounded-2xl border-4 border-black font-bold text-red-800">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="pt-24 max-w-7xl mx-auto px-4 pb-12 flex flex-col h-[calc(100vh-4rem)]">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Link
            to="/dashboard"
            className="p-2 border-2 border-black rounded-full hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-800 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <h1 className="text-3xl font-black">Learning Pathway</h1>
        </div>
        <div className="flex gap-4 items-center text-sm font-bold">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-green-100 border-2 border-green-500 rounded"></div>{" "}
            Completed
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-blue-50 border-2 border-blue-500 rounded"></div>{" "}
            Unlocked
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-gray-100 border-2 border-gray-300 rounded"></div>{" "}
            Locked
          </div>
        </div>
      </div>

      <div className="flex-1 rounded-xl overflow-hidden border-4 border-black shadow-[4px_4px_0_0_rgba(0,0,0,1)]">
        <LearningPathway lessons={lessons} />
      </div>
    </div>
  );
};
