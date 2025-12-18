import React from 'react';

interface ErrorAlertProps {
  message: string;
  onDismiss?: () => void;
  className?: string;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  message,
  onDismiss,
  className = '',
}) => {
  return (
    <div
      className={`bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded relative ${className}`}
      role="alert"
    >
      <div className="flex items-center justify-between">
        <span className="block sm:inline">{message}</span>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="ml-4 text-red-800 hover:text-red-600"
            aria-label="Dismiss error"
          >
            <svg
              className="w-5 h-5"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
};

