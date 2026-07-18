/**
 * Impact vs Effort matrix visualization.
 *
 * @file ImpactEffortMatrix.tsx
 * @location frontend/src/components/FeatureRequests/ImpactEffortMatrix.tsx
 */

import React, { useMemo } from "react";
import { FeatureRequest } from "../../types/featureRequests";

interface ImpactEffortMatrixProps {
  features: FeatureRequest[];
}

export const ImpactEffortMatrix: React.FC<ImpactEffortMatrixProps> = ({
  features,
}) => {
  const matrixData = useMemo(() => {
    // Group features by impact and effort quadrants
    const quadrants = {
      highImpactLowEffort: [],
      highImpactHighEffort: [],
      lowImpactLowEffort: [],
      lowImpactHighEffort: [],
    };

    features.forEach((feature) => {
      const impact = feature.impact_score || 5;
      const effort = feature.effort_score || 5;

      if (impact > 5 && effort <= 5) {
        quadrants.highImpactLowEffort.push(feature);
      } else if (impact > 5 && effort > 5) {
        quadrants.highImpactHighEffort.push(feature);
      } else if (impact <= 5 && effort <= 5) {
        quadrants.lowImpactLowEffort.push(feature);
      } else {
        quadrants.lowImpactHighEffort.push(feature);
      }
    });

    return quadrants;
  }, [features]);

  const quadrantColors = {
    highImpactLowEffort: "border-green-500 bg-green-500/10",
    highImpactHighEffort: "border-yellow-500 bg-yellow-500/10",
    lowImpactLowEffort: "border-blue-500 bg-blue-500/10",
    lowImpactHighEffort: "border-red-500 bg-red-500/10",
  };

  const quadrantLabels = {
    highImpactLowEffort: "🚀 Quick Wins (High Impact, Low Effort)",
    highImpactHighEffort: "📊 Major Projects (High Impact, High Effort)",
    lowImpactLowEffort: "⚡ Fill-ins (Low Impact, Low Effort)",
    lowImpactHighEffort: "🤔 Thankless Tasks (Low Impact, High Effort)",
  };

  return (
    <div className="bg-dark-800/50 p-6 rounded-xl border border-dark-700">
      <h3 className="text-lg font-semibold text-white mb-4">
        Impact vs Effort Matrix
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(
          Object.entries(matrixData) as [
            keyof typeof matrixData,
            FeatureRequest[],
          ][]
        ).map(([key, items]) => (
          <div
            key={key}
            className={`p-4 rounded-lg border-2 ${quadrantColors[key]} min-h-[120px]`}
          >
            <div className="text-sm font-medium text-gray-300 mb-2">
              {quadrantLabels[key]}
              <span className="ml-2 text-xs text-gray-500">
                ({items.length})
              </span>
            </div>
            <div className="space-y-1">
              {items.slice(0, 5).map((feature) => (
                <div
                  key={feature.id}
                  className="text-sm text-gray-400 truncate"
                >
                  • {feature.title}
                  <span className="ml-2 text-xs text-gray-500">
                    (Impact: {feature.impact_score}, Effort:{" "}
                    {feature.effort_score})
                  </span>
                </div>
              ))}
              {items.length > 5 && (
                <div className="text-xs text-gray-500">
                  +{items.length - 5} more
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
