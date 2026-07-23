import React from "react";

interface ContinueLearningProps {
  lastLesson: {
    slug: string;
    title: string;
    progress: number;
  } | null;
}

export function ContinueLearning({ lastLesson }: ContinueLearningProps) {
  if (!lastLesson) return null;

  return (
    <div className="continue-learning">
      <h3>📖 Continue Learning</h3>
      <div className="lesson-card">
        <span className="lesson-title">{lastLesson.title}</span>
        <span className="progress">{lastLesson.progress}%</span>
        <a href={`/lessons/${lastLesson.slug}`} className="resume-btn">
          ▶️ Resume
        </a>
      </div>
    </div>
  );
}
