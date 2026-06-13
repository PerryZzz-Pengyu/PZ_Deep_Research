"use client";

import { useId } from "react";

/** The PZ Deep Research prism mark — a gradient-stroked triangle. */
export function BrandMark({ className = "brand-mark" }: { className?: string }) {
  const gradientId = useId();
  return (
    <svg className={className} viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="26" x2="26" y2="0">
          <stop offset="0" stopColor="#00B7FA" />
          <stop offset="0.5" stopColor="#006FEE" />
          <stop offset="1" stopColor="#FF1CF7" />
        </linearGradient>
      </defs>
      <path
        d="M13 2.5 L24 22.5 H2 Z"
        stroke={`url(#${gradientId})`}
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  );
}
