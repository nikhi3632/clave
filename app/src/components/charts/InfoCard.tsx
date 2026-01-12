"use client";

import { InfoIcon } from "@/components/ui/Icon";
import { infoCardStyles as styles } from "@/styles/charts/infoCard";

interface InfoCardProps {
  summary?: string;
}

export function InfoCard({ summary }: InfoCardProps) {
  return (
    <div className={styles.container}>
      <div className={styles.iconWrapper}>
        <InfoIcon className={styles.icon} />
      </div>
      <p className={styles.text}>
        {summary || "Ask a question about your restaurant data to get started."}
      </p>
    </div>
  );
}
