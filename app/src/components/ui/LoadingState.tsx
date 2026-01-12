import { Card } from "./Card";
import { loadingStateStyles as styles } from "@/styles/ui/loadingState";

interface LoadingStateProps {
  title?: string;
  description?: string;
}

export function LoadingState({
  title = "Analyzing your question...",
  description = "Generating visualization",
}: LoadingStateProps) {
  return (
    <Card className={styles.card}>
      <div className={styles.content}>
        <div className={styles.spinnerWrapper}>
          <div className={styles.spinnerBg} />
          <div className={styles.spinner} />
        </div>
        <div>
          <p className={styles.title}>{title}</p>
          <p className={styles.description}>{description}</p>
        </div>
      </div>
    </Card>
  );
}
