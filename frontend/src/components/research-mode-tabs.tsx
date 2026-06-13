"use client";

import { Tabs } from "@heroui/react";

import type { ResearchMode } from "@/lib/types";

const MODE_ORDER: ResearchMode[] = ["quick", "deep", "expert"];

export function ResearchModeTabs({
  ariaLabel,
  disabled = false,
  labels,
  mode,
  onModeChange,
}: {
  ariaLabel: string;
  disabled?: boolean;
  labels: Record<ResearchMode, string>;
  mode: ResearchMode;
  onModeChange: (mode: ResearchMode) => void;
}) {
  return (
    <Tabs
      className="research-mode-tabs"
      selectedKey={mode}
      onSelectionChange={(key) => onModeChange(String(key) as ResearchMode)}
    >
      <Tabs.ListContainer>
        <Tabs.List aria-label={ariaLabel}>
          {MODE_ORDER.map((value) => (
            <Tabs.Tab id={value} isDisabled={disabled} key={value}>
              {labels[value]}
              <Tabs.Indicator />
            </Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs.ListContainer>
    </Tabs>
  );
}
