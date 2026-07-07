import { useState, useCallback, useEffect } from "react";

export interface TraceEvent {
  step: number;
  line: number;
  event: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  locals: Record<string, any>;
  stdout: string;
  error?: string;
}

export function useTimelineEngine() {
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([]);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(500); // ms per step

  const loadTrace = useCallback((events: TraceEvent[]) => {
    setTraceEvents(events);
    setCurrentStepIndex(0);
    setIsPlaying(false);
  }, []);

  const clearTrace = useCallback(() => {
    setTraceEvents([]);
    setCurrentStepIndex(0);
    setIsPlaying(false);
  }, []);

  const stepForward = useCallback(() => {
    setCurrentStepIndex((prev) => Math.min(prev + 1, traceEvents.length - 1));
  }, [traceEvents.length]);

  const stepBackward = useCallback(() => {
    setCurrentStepIndex((prev) => Math.max(prev - 1, 0));
  }, []);

  const jumpToStep = useCallback((index: number) => {
    if (index >= 0 && index < traceEvents.length) {
      setCurrentStepIndex(index);
    }
  }, [traceEvents.length]);

  const togglePlayback = useCallback(() => {
    if (currentStepIndex >= traceEvents.length - 1) {
      // If at end, restart
      setCurrentStepIndex(0);
      setIsPlaying(true);
    } else {
      setIsPlaying((prev) => !prev);
    }
  }, [currentStepIndex, traceEvents.length]);

  // Handle auto-playback
  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    if (isPlaying && currentStepIndex < traceEvents.length - 1) {
      intervalId = setInterval(() => {
        setCurrentStepIndex((prev) => {
          if (prev >= traceEvents.length - 2) {
            setIsPlaying(false); // Auto pause at end
            return traceEvents.length - 1;
          }
          return prev + 1;
        });
      }, playbackSpeed);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isPlaying, currentStepIndex, traceEvents.length, playbackSpeed]);

  const currentEvent = traceEvents[currentStepIndex] || null;

  return {
    traceEvents,
    currentStepIndex,
    currentEvent,
    isPlaying,
    playbackSpeed,
    loadTrace,
    clearTrace,
    stepForward,
    stepBackward,
    jumpToStep,
    togglePlayback,
    setPlaybackSpeed,
  };
}
