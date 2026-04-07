"use client";

import * as React from "react";
import { animate, useMotionValue, useTransform } from "framer-motion";

export function AnimatedNumber({
  value,
  format,
  className,
}: {
  value: number;
  format: (n: number) => string;
  className?: string;
}) {
  const motionValue = useMotionValue(value);
  const rounded = useTransform(motionValue, (latest) => latest);
  const [display, setDisplay] = React.useState(() => format(value));

  React.useEffect(() => {
    const controls = animate(motionValue, value, {
      duration: 0.35,
      ease: "easeOut",
    });
    const unsub = rounded.on("change", (latest) => setDisplay(format(latest)));
    return () => {
      controls.stop();
      unsub();
    };
  }, [format, motionValue, rounded, value]);

  return <span className={className}>{display}</span>;
}

