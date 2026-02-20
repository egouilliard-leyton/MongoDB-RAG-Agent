import React, { useState, useEffect, useCallback, useRef } from 'react';
import { LoadingSpinner } from './LoadingSpinner';
import { ErrorAlert } from './ErrorAlert';
import type { Industry } from '../api/types';

// Re-export Industry type for convenience
export type { Industry } from '../api/types';

interface IndustrySelectorProps {
  /** Currently selected industry codes */
  value?: string[];
  /** Callback when selection changes */
  onChange: (industries: Industry[]) => void;
  /** Label for the selector */
  label?: string;
  /** Placeholder text when nothing selected */
  placeholder?: string;
  /** Whether the selector is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Error message to display */
  error?: string;
  /** Maximum number of selections (0 = unlimited) */
  maxSelections?: number;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * IndustrySelector component for selecting one or more industries.
 *
 * Features:
 * - Fetches all 19 industries from the API on mount
 * - Multi-select with checkboxes
 * - "Select All" option for convenience
 * - Dropdown with click-outside to close
 * - Shows selected count when collapsed
 * - Loading and error state handling
 */
export const IndustrySelector: React.FC<IndustrySelectorProps> = ({
  value = [],
  onChange,
  label = 'Industries',
  placeholder = 'Select industries...',
  disabled = false,
  className = '',
  error: externalError,
  maxSelections = 0,
}) => {
  const [industries, setIndustries] = useState<Industry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  /**
   * Fetch all industries on component mount.
   */
  useEffect(() => {
    const fetchIndustries = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`${API_BASE_URL}/api/industries`);

        if (!response.ok) {
          throw new Error(`Failed to fetch industries: ${response.statusText}`);
        }

        const data: Industry[] = await response.json();
        setIndustries(data);
      } catch (err) {
        console.error('[IndustrySelector] Error fetching industries:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch industries');
      } finally {
        setIsLoading(false);
      }
    };

    void fetchIndustries();
  }, []);

  /**
   * Handle click outside to close dropdown.
   */
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  /**
   * Check if an industry is selected.
   */
  const isSelected = useCallback(
    (code: string): boolean => {
      return value.includes(code);
    },
    [value]
  );

  /**
   * Check if all industries are selected.
   */
  const allSelected = industries.length > 0 && value.length === industries.length;

  /**
   * Check if some industries are selected (for indeterminate state).
   */
  const someSelected = value.length > 0 && value.length < industries.length;

  /**
   * Toggle selection of a single industry.
   */
  const handleToggle = useCallback(
    (industry: Industry) => {
      const code = industry.code;
      let newSelection: string[];

      if (isSelected(code)) {
        // Remove from selection
        newSelection = value.filter((c) => c !== code);
      } else {
        // Add to selection (check max if set)
        if (maxSelections > 0 && value.length >= maxSelections) {
          return; // Don't add if at max
        }
        newSelection = [...value, code];
      }

      // Map codes back to full Industry objects for callback
      const selectedIndustries = industries.filter((i) => newSelection.includes(i.code));
      onChange(selectedIndustries);
    },
    [value, industries, onChange, isSelected, maxSelections]
  );

  /**
   * Handle "Select All" / "Deselect All" toggle.
   */
  const handleSelectAll = useCallback(() => {
    if (allSelected) {
      // Deselect all
      onChange([]);
    } else {
      // Select all (or up to max if set)
      const toSelect = maxSelections > 0 ? industries.slice(0, maxSelections) : industries;
      onChange(toSelect);
    }
  }, [allSelected, industries, onChange, maxSelections]);

  /**
   * Clear all selections.
   */
  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onChange([]);
    },
    [onChange]
  );

  /**
   * Get display text for the collapsed state.
   */
  const getDisplayText = (): string => {
    if (value.length === 0) {
      return placeholder;
    }

    if (allSelected) {
      return 'All industries selected';
    }

    if (value.length === 1) {
      const selected = industries.find((i) => i.code === value[0]);
      return selected?.name_english || value[0];
    }

    return `${value.length} industries selected`;
  };

  const displayError = externalError || error;

  return (
    <div className={`w-full ${className}`} ref={containerRef}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      )}

      <div className="relative">
        {isLoading ? (
          <div className="flex items-center justify-center py-2 px-3 border border-gray-300 rounded-lg bg-gray-50">
            <LoadingSpinner size="sm" />
            <span className="ml-2 text-sm text-gray-500">Loading industries...</span>
          </div>
        ) : (
          <>
            {/* Toggle button */}
            <button
              type="button"
              onClick={() => !disabled && setIsOpen(!isOpen)}
              disabled={disabled || industries.length === 0}
              className={`w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-left flex items-center justify-between ${
                displayError ? 'border-red-300' : 'border-gray-300'
              } ${disabled ? 'bg-gray-100 cursor-not-allowed' : 'bg-white cursor-pointer'}`}
            >
              <span
                className={`truncate ${value.length === 0 ? 'text-gray-400' : 'text-gray-900'}`}
              >
                {getDisplayText()}
              </span>

              <div className="flex items-center">
                {/* Clear button */}
                {value.length > 0 && !disabled && (
                  <button
                    type="button"
                    onClick={handleClear}
                    className="text-gray-400 hover:text-gray-600 mr-2"
                    aria-label="Clear selection"
                  >
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </button>
                )}

                {/* Dropdown arrow */}
                <svg
                  className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </div>
            </button>

            {/* Dropdown menu */}
            {isOpen && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                {/* Select All option */}
                <label
                  className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer border-b border-gray-200 sticky top-0 bg-white"
                >
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = someSelected;
                    }}
                    onChange={handleSelectAll}
                    className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    disabled={disabled}
                  />
                  <span className="ml-3 text-sm font-medium text-gray-900">
                    {allSelected ? 'Deselect All' : 'Select All'}
                  </span>
                  {maxSelections > 0 && (
                    <span className="ml-auto text-xs text-gray-500">
                      Max: {maxSelections}
                    </span>
                  )}
                </label>

                {/* Industry options */}
                {industries.map((industry) => {
                  const selected = isSelected(industry.code);
                  const atMax = maxSelections > 0 && value.length >= maxSelections && !selected;

                  return (
                    <label
                      key={industry.code}
                      className={`flex items-center px-3 py-2 hover:bg-gray-50 ${
                        atMax ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => handleToggle(industry)}
                        className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                        disabled={disabled || atMax}
                      />
                      <div className="ml-3 flex-1 min-w-0">
                        <span className="text-sm text-gray-900 block truncate">
                          {industry.name_english}
                        </span>
                        <span className="text-xs text-gray-500 block truncate">
                          {industry.name_polish}
                        </span>
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      {/* Selected industries chips */}
      {value.length > 0 && value.length <= 5 && !isLoading && (
        <div className="mt-2 flex flex-wrap gap-1">
          {value.map((code) => {
            const industry = industries.find((i) => i.code === code);
            if (!industry) return null;
            return (
              <span
                key={code}
                className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800"
              >
                {industry.name_english}
                {!disabled && (
                  <button
                    type="button"
                    onClick={() => handleToggle(industry)}
                    className="ml-1 text-purple-600 hover:text-purple-800"
                    aria-label={`Remove ${industry.name_english}`}
                  >
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </button>
                )}
              </span>
            );
          })}
        </div>
      )}

      {/* Error Display */}
      {displayError && <ErrorAlert message={displayError} className="mt-2" />}
    </div>
  );
};

export default IndustrySelector;
