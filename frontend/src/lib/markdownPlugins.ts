import { InteractiveQuiz } from "../components/ui/plugins/InteractiveQuiz";
import React from "react";

export const pluginRegistry: Record<
  string,
  React.ComponentType<Record<string, unknown>>
> = {
  "interactive-quiz": InteractiveQuiz,
};
