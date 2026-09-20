"use client";

import React from "react";

export interface NeuralCubeIconProps extends React.SVGProps<SVGSVGElement> {
  size?: number;
  className?: string;
  accentCore?: boolean;
}

export function NeuralCubeIcon({
  size = 16,
  className = "",
  accentCore = false,
  ...props
}: NeuralCubeIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
      {...props}
    >
      {/* Facet Shading: Top Face (illuminated surface) */}
      <path
        d="M12 2.5L20.5 7.4L12 12.3L3.5 7.4Z"
        fill="currentColor"
        fillOpacity="0.22"
      />
      {/* Facet Shading: Left Face */}
      <path
        d="M3.5 7.4L12 12.3V21.5L3.5 16.6Z"
        fill="currentColor"
        fillOpacity="0.08"
      />
      {/* Facet Shading: Right Face */}
      <path
        d="M12 12.3L20.5 7.4V16.6L12 21.5Z"
        fill="currentColor"
        fillOpacity="0.15"
      />

      {/* Wireframe Outer Bounds */}
      <path
        d="M12 2.5L20.5 7.4V16.6L12 21.5L3.5 16.6V7.4L12 2.5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />

      {/* Wireframe Interior Y-Junction */}
      <path
        d="M12 12.3V21.5M12 12.3L3.5 7.4M12 12.3L20.5 7.4"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Floating Inner Isometric Neural Core */}
      <path
        d="M12 9.2L14.8 10.8V13.8L12 15.4L9.2 13.8V10.8Z"
        fill={accentCore ? "var(--rl-red, #ed1c24)" : "currentColor"}
        fillOpacity={accentCore ? 1 : 0.9}
        stroke={accentCore ? "#ffffff" : "currentColor"}
        strokeWidth="0.8"
        strokeLinejoin="round"
      />

      {/* Central Neural Pulse Node */}
      <circle
        cx="12"
        cy="12.3"
        r="1.2"
        fill={accentCore ? "#ffffff" : "currentColor"}
      />
    </svg>
  );
}

export default NeuralCubeIcon;
