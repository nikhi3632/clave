"use client";

import { MinusIcon } from "@/components/ui/Icon";

export function NoData() {
  return (
    <div className="flex items-center justify-center h-[300px] text-slate-400 dark:text-zinc-500">
      <div className="text-center">
        <MinusIcon className="w-12 h-12 mx-auto mb-2 opacity-50" />
        <p>No data available</p>
      </div>
    </div>
  );
}
