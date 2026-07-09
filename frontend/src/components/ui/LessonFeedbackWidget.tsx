import React, { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Star } from "lucide-react";
import { fetchApi } from "../../lib/api";

interface FeedbackMetrics {
  lessonSlug: string;
  averageRating: number;
  totalCount: number;
  ratingDistribution: Record<string, number>;
}

interface UserFeedback {
  id: number;
  lesson: number;
  rating: number;
  comment: string;
  createdAt: string;
  updatedAt: string;
}

interface LessonFeedbackWidgetProps {
  lessonSlug: string;
  onFeedbackSubmitted?: () => void;
}

export function LessonFeedbackWidget({
  lessonSlug,
  onFeedbackSubmitted,
}: LessonFeedbackWidgetProps) {
  const queryClient = useQueryClient();
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [comment, setComment] = useState("");
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  // Fetch metrics
  const { data: metrics } = useQuery<FeedbackMetrics>({
    queryKey: ["lessonFeedbackMetrics", lessonSlug],
    queryFn: async () => {
      return fetchApi(`/content/lessons/${lessonSlug}/feedback/metrics/`, {
        method: "GET",
        requireAuth: false,
      });
    },
  });

  // Fetch user's existing feedback
  const { data: userFeedback } = useQuery<UserFeedback>({
    queryKey: ["userLessonFeedback", lessonSlug],
    queryFn: async () => {
      return fetchApi(`/content/lessons/${lessonSlug}/feedback/my/`, {
        method: "GET",
      });
    },
    retry: false,
  });

  // Sync local state when user feedback loads
  useEffect(() => {
    if (userFeedback && !("error" in userFeedback)) {
      setRating(userFeedback.rating);
      setComment(userFeedback.comment || "");
      setHasSubmitted(true);
    }
  }, [userFeedback]);

  // Submit feedback mutation
  const submitMutation = useMutation({
    mutationFn: async () => {
      return fetchApi(
      `/content/lessons/${lessonSlug}/feedback/`,
        {
        method: "POST",
        body: JSON.stringify({
          rating,
          comment,
        }),
        },
      );
    },

    onSuccess: () => {
    setHasSubmitted(true);
    setShowSuccess(true);

    queryClient.invalidateQueries({
      queryKey: ["lessonFeedbackMetrics", lessonSlug],
    });

    queryClient.invalidateQueries({
      queryKey: ["userLessonFeedback", lessonSlug],
    });

    onFeedbackSubmitted?.();

    setTimeout(() => setShowSuccess(false), 3000);
    },
  });

  // Update feedback mutation
  const updateMutation = useMutation({
    mutationFn: async () => {
      if (!userFeedback) throw new Error("No feedback to update");
      return fetchApi(`/content/feedback/${userFeedback.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          rating,
          comment,
        }),
      });
    },
    onSuccess: () => {
      setShowSuccess(true);
      queryClient.invalidateQueries({ queryKey: ["lessonFeedbackMetrics", lessonSlug] });
      queryClient.invalidateQueries({ queryKey: ["userLessonFeedback", lessonSlug] });
      onFeedbackSubmitted?.();
      setTimeout(() => setShowSuccess(false), 3000);
    },
  });

  const handleSubmit = () => {
    if (rating === 0) return;
    if (hasSubmitted) {
      updateMutation.mutate();
    } else {
      submitMutation.mutate();
    }
  };

  const isSubmitting = submitMutation.isPending || updateMutation.isPending;

  return (
    <div className="border-t-4 border-black p-6 bg-white dark:bg-[#151411] dark:border-[#2e2924]">
      <div className="max-w-2xl mx-auto">
        <h3 className="text-xl font-black mb-4 flex items-center gap-2">
          <Star className="w-5 h-5 text-yellow-500 fill-yellow-500" />
          Rate this Lesson
        </h3>

        {/* Metrics Display */}
        {metrics && metrics.totalCount > 0 && (
          <div className="mb-4 p-4 bg-gray-50 dark:bg-[#0f0e0c] rounded-lg border-2 border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-4">
              <div className="text-4xl font-black text-yellow-600">
                {metrics.averageRating.toFixed(1)}
              </div>
              <div>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <Star
                      key={star}
                      className={`w-5 h-5 ${
                        star <= Math.round(metrics.averageRating)
                          ? "text-yellow-500 fill-yellow-500"
                          : "text-gray-300 dark:text-gray-600"
                      }`}
                    />
                  ))}
                </div>
                <p className="text-sm text-muted mt-1">
                  Based on {metrics.totalCount}{" "}
                  {metrics.totalCount === 1 ? "rating" : "ratings"}
                </p>
              </div>
            </div>
            {/* Rating Distribution */}
            <div className="mt-3 space-y-1">
              {[5, 4, 3, 2, 1].map((star) => {
                const count = metrics.ratingDistribution[String(star)] || 0;
                const percentage =
                  metrics.totalCount > 0
                    ? (count / metrics.totalCount) * 100
                    : 0;
                return (
                  <div key={star} className="flex items-center gap-2 text-xs">
                    <span className="w-4 font-bold">{star}</span>
                    <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                      <div
                        className="bg-yellow-500 h-2 rounded-full transition-all"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                    <span className="w-8 text-right text-muted">{count}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Star Rating Input */}
        <div className="mb-4">
          <label className="block text-sm font-bold mb-2">Your Rating</label>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                type="button"
                onClick={() => setRating(star)}
                onMouseEnter={() => setHoverRating(star)}
                onMouseLeave={() => setHoverRating(0)}
                className="p-1 transition-transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-primary rounded"
                aria-label={`Rate ${star} stars`}
              >
                <Star
                  className={`w-8 h-8 ${
                    star <= (hoverRating || rating)
                      ? "text-yellow-500 fill-yellow-500"
                      : "text-gray-300 dark:text-gray-600"
                  } transition-colors`}
                />
              </button>
            ))}
          </div>
          {rating > 0 && (
            <p className="text-sm text-muted mt-1">
              {rating === 5 && "Excellent! 🌟"}
              {rating === 4 && "Very Good! 👍"}
              {rating === 3 && "Good 👍"}
              {rating === 2 && "Needs Improvement 📝"}
              {rating === 1 && "Poor 💔"}
            </p>
          )}
        </div>

        {/* Comment Input */}
        <div className="mb-4">
          <label htmlFor="feedback-comment" className="block text-sm font-bold mb-2">
            Feedback (Optional)
          </label>
          <textarea
            id="feedback-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Share your thoughts about this lesson..."
            maxLength={1000}
            rows={3}
            className="w-full px-4 py-2 rounded-lg border-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#151411] text-sm outline-none focus:border-primary transition-colors resize-none"
          />
          <p className="text-xs text-muted mt-1 text-right">
            {comment.length}/1000
          </p>
        </div>

        {/* Submit Button */}
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={rating === 0 || isSubmitting}
            className={`px-6 py-2 font-bold rounded-lg border-4 shadow-card transition-all ${
              rating === 0
                ? "bg-gray-100 text-gray-400 border-gray-300 cursor-not-allowed"
                : "bg-primary text-black border-black hover:-translate-y-0.5 hover:shadow-card-sm active:translate-y-0"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {isSubmitting
              ? "Submitting..."
              : hasSubmitted
                ? "Update Feedback"
                : "Submit Feedback"}
          </button>

          {showSuccess && (
            <span className="text-green-600 font-bold text-sm flex items-center gap-1">
              ✓ Feedback saved!
            </span>
          )}
        </div>

        {hasSubmitted && (
          <p className="text-xs text-muted mt-2">
            You have already submitted feedback for this lesson. You can update
            it anytime.
          </p>
        )}
      </div>
    </div>
  );
}

export default LessonFeedbackWidget;
