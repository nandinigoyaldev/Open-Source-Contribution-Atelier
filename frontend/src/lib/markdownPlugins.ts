import { InteractiveQuiz } from "../components/ui/plugins/InteractiveQuiz";

export const pluginRegistry: Record<string, React.ComponentType<any>> = {
  "interactive-quiz": InteractiveQuiz,
};
