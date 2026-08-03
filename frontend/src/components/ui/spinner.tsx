"use client";

import { SpinnerGap } from "@phosphor-icons/react";

type SpinnerProps = {
  size?: number;
  className?: string;
};

export function Spinner({ size = 20, className = "" }: SpinnerProps) {
  return <SpinnerGap aria-hidden="true" className={`animate-spin ${className}`} size={size} />;
}
