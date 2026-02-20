import React, { useState, useEffect, useCallback, useRef } from 'react';
import { LoadingSpinner } from './LoadingSpinner';
import { ErrorAlert } from './ErrorAlert';
import type { TaxOffice } from '../api/types';

// Re-export TaxOffice type for convenience
export type { TaxOffice } from '../api/types';

interface TaxOfficeSelectorProps {
  /** Currently selected tax office ID (kodjednostki) */
  value?: number | null;
  /** Callback when a tax office is selected */
  onChange: (taxOffice: TaxOffice | null) => void;
  /** Label for the selector */
  label?: string;
  /** Placeholder text for search input */
  placeholder?: string;
  /** Whether the selector is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Error message to display */
  error?: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Debounce function to limit API calls during typing.
 */
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * TaxOfficeSelector component for searching and selecting Polish tax offices.
 *
 * Features:
 * - Debounced search input (300ms)
 * - Dropdown results list with office details
 * - Selected office display with full contact info
 * - Loading and error state handling
 * - Click-outside to close dropdown
 */
export const TaxOfficeSelector: React.FC<TaxOfficeSelectorProps> = ({
  value,
  onChange,
  label = 'Tax Office',
  placeholder = 'Search by name, city, or ID...',
  disabled = false,
  className = '',
  error: externalError,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState<TaxOffice[]>([]);
  const [selectedTaxOffice, setSelectedTaxOffice] = useState<TaxOffice | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isFetchingSelected, setIsFetchingSelected] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const debouncedQuery = useDebounce(searchQuery, 300);

  /**
   * Fetch tax office by ID when value prop changes.
   */
  useEffect(() => {
    const fetchSelectedTaxOffice = async () => {
      if (value === null || value === undefined) {
        setSelectedTaxOffice(null);
        return;
      }

      // If we already have the selected office with matching ID, skip fetch
      if (selectedTaxOffice && selectedTaxOffice.kodjednostki === value) {
        return;
      }

      setIsFetchingSelected(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/tax-offices/${value}`);
        if (!response.ok) {
          if (response.status === 404) {
            setSelectedTaxOffice(null);
            return;
          }
          throw new Error(`Failed to fetch tax office: ${response.statusText}`);
        }
        const taxOffice: TaxOffice = await response.json();
        setSelectedTaxOffice(taxOffice);
      } catch (err) {
        console.error('[TaxOfficeSelector] Error fetching tax office:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch tax office');
      } finally {
        setIsFetchingSelected(false);
      }
    };

    void fetchSelectedTaxOffice();
  }, [value]);

  /**
   * Search tax offices when debounced query changes.
   */
  useEffect(() => {
    const searchTaxOffices = async () => {
      if (!debouncedQuery.trim()) {
        setResults([]);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          q: debouncedQuery.trim(),
          limit: '20',
        });
        const response = await fetch(`${API_BASE_URL}/api/tax-offices/search?${params}`);

        if (!response.ok) {
          throw new Error(`Search failed: ${response.statusText}`);
        }

        const data: TaxOffice[] = await response.json();
        setResults(data);
        setIsDropdownOpen(true);
      } catch (err) {
        console.error('[TaxOfficeSelector] Search error:', err);
        setError(err instanceof Error ? err.message : 'Search failed');
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    };

    void searchTaxOffices();
  }, [debouncedQuery]);

  /**
   * Handle click outside to close dropdown.
   */
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  /**
   * Handle tax office selection from dropdown.
   */
  const handleSelect = useCallback(
    (taxOffice: TaxOffice) => {
      setSelectedTaxOffice(taxOffice);
      setSearchQuery('');
      setResults([]);
      setIsDropdownOpen(false);
      onChange(taxOffice);
    },
    [onChange]
  );

  /**
   * Clear selection.
   */
  const handleClear = useCallback(() => {
    setSelectedTaxOffice(null);
    setSearchQuery('');
    setResults([]);
    onChange(null);
    inputRef.current?.focus();
  }, [onChange]);

  /**
   * Handle input focus.
   */
  const handleFocus = () => {
    if (results.length > 0) {
      setIsDropdownOpen(true);
    }
  };

  /**
   * Format address for display.
   */
  const formatAddress = (taxOffice: TaxOffice): string => {
    return `${taxOffice.ulica} ${taxOffice.nr_budynku}, ${taxOffice.kod_pocztowy} ${taxOffice.miasto}`;
  };

  const displayError = externalError || error;

  return (
    <div className={`w-full ${className}`} ref={containerRef}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      )}

      {/* Selected Tax Office Display */}
      {selectedTaxOffice ? (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-2">
          <div className="flex justify-between items-start">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-blue-900 truncate">
                {selectedTaxOffice.nazwa_urzedu}
              </p>
              <p className="text-xs text-blue-700 mt-1">
                {formatAddress(selectedTaxOffice)}
              </p>
              <div className="flex flex-wrap gap-2 mt-2">
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                  ID: {selectedTaxOffice.kodjednostki}
                </span>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                  {selectedTaxOffice.typ}
                </span>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                  {selectedTaxOffice.wojewodztwo}
                </span>
              </div>
              <div className="mt-2 text-xs text-blue-600">
                <p>{selectedTaxOffice.telefon}</p>
                <p>{selectedTaxOffice.email}</p>
              </div>
            </div>
            {!disabled && (
              <button
                type="button"
                onClick={handleClear}
                className="ml-2 text-blue-800 hover:text-blue-600 flex-shrink-0"
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
        </div>
      ) : isFetchingSelected ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 mb-2">
          <LoadingSpinner size="sm" />
        </div>
      ) : null}

      {/* Search Input */}
      {!selectedTaxOffice && (
        <div className="relative">
          <div className="relative">
            <input
              ref={inputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={handleFocus}
              placeholder={placeholder}
              disabled={disabled}
              className={`w-full px-3 py-2 pr-10 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                displayError ? 'border-red-300' : 'border-gray-300'
              } ${disabled ? 'bg-gray-100 cursor-not-allowed' : ''}`}
            />
            {isLoading && (
              <div className="absolute inset-y-0 right-0 flex items-center pr-3">
                <LoadingSpinner size="sm" />
              </div>
            )}
          </div>

          {/* Dropdown Results */}
          {isDropdownOpen && results.length > 0 && (
            <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto">
              {results.map((taxOffice) => (
                <button
                  key={taxOffice.kodjednostki}
                  type="button"
                  onClick={() => handleSelect(taxOffice)}
                  className="w-full px-3 py-2 text-left hover:bg-blue-50 focus:bg-blue-50 focus:outline-none border-b border-gray-100 last:border-b-0"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {taxOffice.nazwa_urzedu}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {taxOffice.miasto}, {taxOffice.wojewodztwo}
                      </p>
                    </div>
                    <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600 flex-shrink-0">
                      {taxOffice.typ}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* No Results Message */}
          {isDropdownOpen && debouncedQuery.trim() && results.length === 0 && !isLoading && (
            <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg p-3">
              <p className="text-sm text-gray-500 text-center">
                No tax offices found for "{debouncedQuery}"
              </p>
            </div>
          )}
        </div>
      )}

      {/* Error Display */}
      {displayError && <ErrorAlert message={displayError} className="mt-2" />}
    </div>
  );
};

export default TaxOfficeSelector;
