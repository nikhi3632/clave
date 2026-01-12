"use client";

import { useState } from "react";
import { Card } from "./ui/Card";
import {
  QuestionIcon,
  LightningIcon,
  Spinner,
  DollarIcon,
  LocationIcon,
  ClockIcon,
  PieChartIcon,
  TableIcon,
} from "./ui/Icon";
import { queryInputStyles as styles } from "@/styles/queryInput";

interface QueryInputProps {
  onSubmit: (query: string) => void;
  isLoading: boolean;
}

const EXAMPLE_QUERIES = [
  { text: "Total revenue", icon: DollarIcon },
  { text: "Sales by location", icon: LocationIcon },
  { text: "Hourly sales trend", icon: ClockIcon },
  { text: "Channel breakdown", icon: PieChartIcon },
  { text: "All products with sales", icon: TableIcon },
];

export function QueryInput({ onSubmit, isLoading }: QueryInputProps) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onSubmit(query.trim());
      setQuery("");
    }
  };

  return (
    <Card className={styles.card}>
      <form onSubmit={handleSubmit} className={styles.form}>
        <div className={styles.inputWrapper}>
          <div className={styles.inputIcon}>
            <QuestionIcon className="w-5 h-5 text-slate-400 dark:text-zinc-500" />
          </div>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question about your restaurant data..."
            className={styles.input}
            disabled={isLoading}
          />
          <div className={styles.buttonWrapper}>
            <button
              type="submit"
              disabled={!query.trim() || isLoading}
              className={styles.submitBtn}
            >
              {isLoading ? (
                <>
                  <Spinner className="h-4 w-4" />
                  <span>Analyzing</span>
                </>
              ) : (
                <>
                  <LightningIcon className="w-4 h-4" />
                  <span>Ask</span>
                </>
              )}
            </button>
          </div>
        </div>

        <div className={styles.examplesWrapper}>
          <span className={styles.examplesLabel}>Try:</span>
          {EXAMPLE_QUERIES.map((example) => {
            const Icon = example.icon;
            return (
              <button
                key={example.text}
                type="button"
                onClick={() => setQuery(example.text)}
                className={styles.exampleBtn}
              >
                <Icon className="w-3.5 h-3.5" />
                {example.text}
              </button>
            );
          })}
        </div>
      </form>
    </Card>
  );
}
