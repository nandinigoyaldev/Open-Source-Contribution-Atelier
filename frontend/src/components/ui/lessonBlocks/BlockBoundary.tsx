import React, { Component, type ErrorInfo, type ReactNode } from "react";
import * as Sentry from "@sentry/react";
import { logger } from "../../../lib/logger";

/** Shown in place of a block that could not be rendered. Announced to screen readers. */
export function BlockError() {
  return (
    <div
      role="alert"
      className="p-4 my-4 bg-red-50 border-4 border-red-500 rounded-xl text-red-700 font-bold shadow-card-sm"
    >
      This part of the lesson could not be displayed.
    </div>
  );
}

interface Props {
  /** Changes whenever the block's source changes, so a fixed block is tried again. */
  resetKey: string;
  children: ReactNode;
}

interface State {
  hasError: boolean;
  seenKey: string;
}

/**
 * Keeps a component that throws inside one block (an embedded quiz, a diagram) from taking the
 * whole lesson down: that block shows {@link BlockError} and the rest keeps rendering.
 */
export class BlockBoundary extends Component<Props, State> {
  public state: State = { hasError: false, seenKey: this.props.resetKey };

  public static getDerivedStateFromError(): Partial<State> {
    return { hasError: true };
  }

  public static getDerivedStateFromProps(
    props: Props,
    state: State,
  ): Partial<State> | null {
    // once the source of the block changes (for example while it is being edited) try it again
    return props.resetKey !== state.seenKey
      ? { hasError: false, seenKey: props.resetKey }
      : null;
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    Sentry.captureException(error, {
      extra: { componentStack: errorInfo.componentStack },
    });
    logger.error(error, errorInfo);
  }

  public render() {
    return this.state.hasError ? <BlockError /> : this.props.children;
  }
}
