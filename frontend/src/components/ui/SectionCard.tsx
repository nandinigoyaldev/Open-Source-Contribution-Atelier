import { PropsWithChildren } from "react";
import clsx from "clsx";

type SectionCardProps = PropsWithChildren<{
  className?: string;
  title?: string;
  eyebrow?: string;
}>;

export function SectionCard({
  children,
  className,
  title,
  eyebrow,
}: SectionCardProps) {
  return (
    <section
      className={clsx(
        "rounded-[24px] border border-outline bg-surface-high/80 p-6 shadow-card backdrop-blur-xl",
        className,
      )}
    >
      {eyebrow ? (
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.24em] text-muted">
          {eyebrow}
        </p>
      ) : null}
      {title ? (
        <h2 className="mt-2  text-2xl font-bold tracking-[-0.02em] text-text">
          {title}
        </h2>
      ) : null}
      <div className="mt-4">{children}</div>
    </section>
  );
}
