import { useState, useEffect } from "react";
import { fetchApi } from "../lib/api";

export function useExperiment(experimentName: string) {
  const [variant, setVariant] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchVariant = async () => {
      try {
        const data = await fetchApi(
          `/experiments/assignment/?name=${experimentName}`,
        );
        setVariant(data.variant || "control");
      } catch {
        setVariant("control");
      } finally {
        setLoading(false);
      }
    };
    fetchVariant();
  }, [experimentName]);

  const trackEvent = (eventType: string, metadata = {}) => {
    fetchApi("/experiments/event/", {
      method: "POST",
      body: JSON.stringify({
        experiment: experimentName,
        variant,
        event_type: eventType,
        metadata,
      }),
    });
  };

  return { variant, loading, trackEvent };
}
