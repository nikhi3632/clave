import { ApiError } from "@/types";
import { ErrorIcon, RefreshIcon, CloseIcon } from "./Icon";
import { errorMessageStyles as styles } from "@/styles/ui/errorMessage";

interface ErrorMessageProps {
  error: ApiError;
  onRetry?: () => void;
  onDismiss: () => void;
  isLoading?: boolean;
  canRetry?: boolean;
}

export function ErrorMessage({
  error,
  onRetry,
  onDismiss,
  isLoading = false,
  canRetry = false,
}: ErrorMessageProps) {
  return (
    <div className={styles.container}>
      <div className={styles.content}>
        <div className={styles.iconWrapper}>
          <ErrorIcon className={styles.icon} />
        </div>
        <div className={styles.textContent}>
          <p className={styles.message}>{error.message}</p>
          {error.code && (
            <p className={styles.code}>Error code: {error.code}</p>
          )}
        </div>
        <button
          onClick={onDismiss}
          className={styles.dismissBtn}
          aria-label="Dismiss error"
        >
          <CloseIcon className="w-4 h-4" />
        </button>
      </div>
      {error.retryable && canRetry && onRetry && (
        <div className={styles.retrySection}>
          <button
            onClick={onRetry}
            disabled={isLoading}
            className={styles.retryBtn}
          >
            <RefreshIcon className="w-4 h-4" />
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
