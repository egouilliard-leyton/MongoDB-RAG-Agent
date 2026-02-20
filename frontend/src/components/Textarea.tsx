import { TextareaHTMLAttributes, forwardRef } from 'react';

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  showCharCount?: boolean;
  maxHeight?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      label,
      error,
      showCharCount = false,
      className = '',
      id,
      value,
      maxLength,
      maxHeight,
      ...props
    },
    ref
  ) => {
    const inputId = id || `textarea-${Math.random().toString(36).substr(2, 9)}`;
    const charCount = typeof value === 'string' ? value.length : 0;
    const maxHeightStyle = maxHeight ? { maxHeight, overflowY: 'auto' as const } : {};

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={inputId}
          className={`w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y ${
            error ? 'border-red-300' : 'border-gray-300'
          } ${maxHeight ? 'overflow-y-auto' : ''} ${className}`}
          style={maxHeightStyle}
          value={value}
          maxLength={maxLength}
          {...props}
        />
        <div className="flex justify-between mt-1">
          {error && <p className="text-sm text-red-600">{error}</p>}
          {showCharCount && (
            <p className={`text-sm ml-auto ${
              maxLength && charCount > maxLength * 0.9 ? 'text-red-600' : 'text-gray-500'
            }`}>
              {charCount}
              {maxLength && ` / ${maxLength}`}
            </p>
          )}
        </div>
      </div>
    );
  }
);

Textarea.displayName = 'Textarea';

