import React, { useState, useEffect, useCallback } from 'react';
import { LoadingSpinner } from './LoadingSpinner';
import { ErrorAlert } from './ErrorAlert';
import type { Region } from '../api/types';

// Re-export Region type for convenience
export type { Region } from '../api/types';

interface RegionSelectorProps {
  /** Currently selected region name */
  value?: string | null;
  /** Callback when a region is selected */
  onChange: (region: Region | null) => void;
  /** Label for the selector */
  label?: string;
  /** Placeholder text for dropdown */
  placeholder?: string;
  /** Whether the selector is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Error message to display */
  error?: string;
  /** Whether to allow clearing selection */
  clearable?: boolean;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * RegionSelector component for selecting Polish voivodeships (regions).
 *
 * Features:
 * - Fetches all 16 Polish regions from the API on mount
 * - Displays regions in a dropdown select
 * - Supports optional clearing of selection
 * - Loading and error state handling
 */
export const RegionSelector: React.FC<RegionSelectorProps> = ({
  value,
  onChange,
  label = 'Region',
  placeholder = 'Select a region...',
  disabled = false,
  className = '',
  error: externalError,
  clearable = true,
}) => {
  const [regions, setRegions] = useState<Region[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Fetch all regions on component mount.
   */
  useEffect(() => {
    const fetchRegions = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`${API_BASE_URL}/api/regions`);

        if (!response.ok) {
          throw new Error(`Failed to fetch regions: ${response.statusText}`);
        }

        const data: Region[] = await response.json();
        setRegions(data);
      } catch (err) {
        console.error('[RegionSelector] Error fetching regions:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch regions');
      } finally {
        setIsLoading(false);
      }
    };

    void fetchRegions();
  }, []);

  /**
   * Handle selection change.
   */
  const handleChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>) => {
      const selectedName = event.target.value;

      if (!selectedName) {
        onChange(null);
        return;
      }

      const selectedRegion = regions.find((r) => r.name === selectedName);
      if (selectedRegion) {
        onChange(selectedRegion);
      }
    },
    [regions, onChange]
  );

  /**
   * Clear selection.
   */
  const handleClear = useCallback(() => {
    onChange(null);
  }, [onChange]);

  const displayError = externalError || error;

  return (
    <div className={`w-full ${className}`}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      )}

      <div className="relative">
        {isLoading ? (
          <div className="flex items-center justify-center py-2 px-3 border border-gray-300 rounded-lg bg-gray-50">
            <LoadingSpinner size="sm" />
            <span className="ml-2 text-sm text-gray-500">Loading regions...</span>
          </div>
        ) : (
          <div className="relative flex items-center">
            <select
              value={value || ''}
              onChange={handleChange}
              disabled={disabled || regions.length === 0}
              className={`w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 appearance-none bg-white ${
                displayError ? 'border-red-300' : 'border-gray-300'
              } ${disabled ? 'bg-gray-100 cursor-not-allowed' : ''} ${
                clearable && value ? 'pr-16' : 'pr-10'
              }`}
            >
              <option value="">{placeholder}</option>
              {regions.map((region) => (
                <option key={region.name} value={region.name}>
                  {region.display_name}
                </option>
              ))}
            </select>

            {/* Dropdown arrow icon */}
            <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
              {clearable && value ? (
                <span className="mr-6" /> // Space for clear button
              ) : null}
              <svg
                className="w-5 h-5 text-gray-400"
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

            {/* Clear button */}
            {clearable && value && !disabled && (
              <button
                type="button"
                onClick={handleClear}
                className="absolute inset-y-0 right-8 flex items-center text-gray-400 hover:text-gray-600"
                aria-label="Clear selection"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Selected region info (optional - shows voivodeship badge) */}
      {value && !isLoading && (
        <div className="mt-1">
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
            {regions.find((r) => r.name === value)?.display_name || value}
          </span>
        </div>
      )}

      {/* Error Display */}
      {displayError && <ErrorAlert message={displayError} className="mt-2" />}
    </div>
  );
};

export default RegionSelector;
