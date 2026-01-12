"use client";

import { useState } from "react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { DataQualityModal } from "@/components/DataQualityModal";
import { BarChartIcon } from "@/components/ui/Icon";
import { headerStyles as styles } from "@/styles/header";

function DataQualityIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

export function Header() {
  const [showDataQuality, setShowDataQuality] = useState(false);

  return (
    <>
      <header className={styles.header}>
        <div className={styles.container}>
          <div className={styles.content}>
            <div className={styles.logoSection}>
              <div className={styles.logoIcon}>
                <BarChartIcon className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className={styles.title}>Restaurant Analytics</h1>
                <p className={styles.subtitle}>Ask questions in natural language</p>
              </div>
            </div>
            <div className={styles.actions}>
              <button
                onClick={() => setShowDataQuality(true)}
                className={styles.iconBtn}
                title="Data Quality"
              >
                <DataQualityIcon className="w-5 h-5" />
              </button>
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      {showDataQuality && (
        <DataQualityModal onClose={() => setShowDataQuality(false)} />
      )}
    </>
  );
}
