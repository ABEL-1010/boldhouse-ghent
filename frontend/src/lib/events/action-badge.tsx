import { CircleCheck, OctagonAlert, TriangleAlert } from "lucide-react";

import { cn } from "@/lib/utils";

import { ACTION_STYLE } from "./labels";
import type { Action } from "./types";

const ICONS = { ALLOW: CircleCheck, FLAG: TriangleAlert, PAUSE: OctagonAlert } as const;

/** Status is never color alone: icon + label + color. */
export function ActionBadge({ action, className }: { action: Action; className?: string }) {
  const style = ACTION_STYLE[action];
  const Icon = ICONS[action];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        style.badgeClass,
        className,
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      {style.label}
    </span>
  );
}
