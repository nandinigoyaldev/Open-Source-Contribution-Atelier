import React from "react";
import {
  Joyride,
  EventData,
  STATUS,
  Step,
  TooltipRenderProps,
} from "react-joyride";
import { motion } from "framer-motion";
import { X, ChevronRight, ChevronLeft, Sparkles } from "lucide-react";

interface OnboardingTourProps {
  run: boolean;
  onFinish: () => void;
}

function CustomTooltip({
  index,
  step,
  backProps,
  closeProps,
  primaryProps,
  tooltipProps,
  isLastStep,
  size,
}: TooltipRenderProps) {
  const progress = ((index + 1) / size) * 100;

  return (
    <motion.div
      {...tooltipProps}
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className="bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-3xl p-6 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] w-[360px] max-w-full relative overflow-hidden"
    >
      {/* Top Progress Bar */}
      <div className="absolute top-0 left-0 h-2 bg-surface-low dark:bg-[#1f1c18] w-full">
        <motion.div
          className="h-full bg-primary"
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        />
      </div>

      {/* Header */}
      <div className="flex justify-between items-center mb-4 mt-2">
        <div className="flex items-center gap-2">
          <Sparkles className="text-primary w-5 h-5 animate-pulse" />
          <span className="font-black text-[10px] uppercase tracking-widest text-muted dark:text-[#c4bbae]">
            Step {index + 1} of {size}
          </span>
        </div>
        <button
          {...closeProps}
          className="p-1.5 hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900/30 rounded-xl transition-colors border-2 border-transparent hover:border-red-600 outline-none"
          aria-label="Skip Tour"
        >
          <X className="w-4 h-4 text-text dark:text-[#f0ebe2]" />
        </button>
      </div>

      {/* Content */}
      {step.title && (
        <h3 className="text-2xl font-black mb-3 text-text dark:text-[#f0ebe2] leading-tight">
          {step.title}
        </h3>
      )}
      <p className="text-sm font-bold text-muted dark:text-[#c4bbae] mb-8 leading-relaxed">
        {step.content}
      </p>

      {/* Footer Controls */}
      <div className="flex justify-between items-center mt-auto">
        <div className="flex gap-1.5">
          {Array.from({ length: size }).map((_, i) => (
            <div
              key={i}
              className={`h-2 rounded-full border-2 border-black transition-all duration-300 ${
                i === index
                  ? "bg-primary w-6"
                  : "bg-surface-low dark:bg-[#2e2924] w-2"
              }`}
            />
          ))}
        </div>

        <div className="flex gap-2">
          {index > 0 && (
            <button
              {...backProps}
              className="flex items-center justify-center p-2.5 rounded-xl border-2 border-black hover:bg-surface-low dark:hover:bg-[#1f1c18] dark:border-[#2e2924] transition-all outline-none"
              aria-label="Previous step"
            >
              <ChevronLeft className="w-5 h-5 text-text dark:text-[#f0ebe2]" />
            </button>
          )}
          <button
            {...primaryProps}
            className="flex items-center gap-2 bg-primary text-black font-black px-5 py-2.5 rounded-xl border-2 border-black shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] hover:-translate-y-0.5 hover:shadow-[5px_5px_0px_0px_rgba(0,0,0,1)] active:translate-y-0.5 active:shadow-none transition-all outline-none"
          >
            {isLastStep ? "Let's Go!" : "Next"}
            {!isLastStep && <ChevronRight className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </motion.div>
  );
}

export function OnboardingTour({ run, onFinish }: OnboardingTourProps) {
  const steps: Step[] = [
    {
      target: "#tour-welcome",
      title: "Welcome to the Atelier! 🎉",
      content:
        "This is your personal dashboard where you can track your journey through the open-source curriculum.",
      placement: "bottom",
      skipBeacon: true,
    },
    {
      target: "#tour-stats",
      title: "Track Your Progress 📈",
      content:
        "Keep your streak alive, merge PRs, and watch your rank climb! Every contribution counts towards your level.",
      placement: "bottom",
    },
    {
      target: "#tour-fact",
      title: "Daily OSS Facts 💡",
      content:
        "Learn something new every day! We share daily facts about the history and impact of the open-source movement.",
      placement: "top",
    },
    {
      target: "#tour-certificate",
      title: "The Ultimate Goal 🎓",
      content:
        "Complete 100% of the curriculum to unlock your graduation certificate. Show the world what you've learned!",
      placement: "top",
    },
    {
      target: "#tour-learning-queue",
      title: "Resume Learning 🚀",
      content:
        "Ready to learn? Jump right back into your next module from this queue. Happy coding!",
      placement: "top",
    },
  ];

  const handleJoyrideCallback = (data: EventData) => {
    const { status } = data;
    const finishedStatuses: string[] = [STATUS.FINISHED, STATUS.SKIPPED];

    if (finishedStatuses.includes(status)) {
      onFinish();
    }
  };

  return (
    <Joyride
      onEvent={handleJoyrideCallback}
      continuous
      run={run}
      scrollToFirstStep
      steps={steps}
      tooltipComponent={CustomTooltip}
      options={{
        zIndex: 10000,
        overlayColor: "rgba(0, 0, 0, 0.7)",
      }}
    />
  );
}
