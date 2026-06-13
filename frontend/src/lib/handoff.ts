import type { ResearchMode } from "@/lib/types";

const HANDOFF_KEY = "pz-deep-research-handoff";

export type ResearchHandoff = {
  query: string;
  mode: ResearchMode;
  autostart: boolean;
};

/** Stash a query + mode from the marketing homepage for the workbench to pick up. */
export function writeHandoff(handoff: ResearchHandoff) {
  try {
    window.localStorage.setItem(HANDOFF_KEY, JSON.stringify(handoff));
  } catch {
    // ignore storage failures
  }
}

/** Read and clear the handoff payload (one-shot). */
export function consumeHandoff(): ResearchHandoff | null {
  try {
    const raw = window.localStorage.getItem(HANDOFF_KEY);
    window.localStorage.removeItem(HANDOFF_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ResearchHandoff>;
    if (typeof parsed.query !== "string") return null;
    const mode: ResearchMode =
      parsed.mode === "quick" || parsed.mode === "deep" || parsed.mode === "expert"
        ? parsed.mode
        : "deep";
    return { query: parsed.query, mode, autostart: Boolean(parsed.autostart) };
  } catch {
    return null;
  }
}
