import React, { useCallback, useEffect, useState } from 'react';
import { useSettings } from '../../contexts/SettingsContext';
import * as api from '../../api/client';
import type { ParameterSuggestion } from '../../api/types';

export const ParameterSuggestions: React.FC = () => {
  const { loadSettings } = useSettings();
  const [suggestions, setSuggestions] = useState<ParameterSuggestion[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [applyingId, setApplyingId] = useState<string | null>(null);

  const fetchSuggestions = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.getParameterSuggestions();
      setSuggestions(data);
    } catch {
      // silently fail - suggestions are non-critical
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSuggestions();
  }, [fetchSuggestions]);

  const handleApply = async (suggestionId: string) => {
    setApplyingId(suggestionId);
    try {
      await api.applySuggestion(suggestionId);
      setSuggestions((prev) => prev.filter((s) => s.suggestion_id !== suggestionId));
      await loadSettings();
    } catch {
      // error handled by api client
    } finally {
      setApplyingId(null);
    }
  };

  const handleDismiss = (suggestionId: string) => {
    setSuggestions((prev) => prev.filter((s) => s.suggestion_id !== suggestionId));
  };

  if (isLoading) {
    return (
      <div className="flex items-center space-x-2 py-4 text-gray-500 text-sm">
        <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <span>Loading suggestions...</span>
      </div>
    );
  }

  if (suggestions.length === 0) {
    return (
      <div className="py-4 text-center">
        <p className="text-sm text-gray-500">
          No suggestions available. More data needed to generate recommendations.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-semibold text-gray-900">Parameter Suggestions</h4>
      {suggestions.map((s) => (
        <div key={s.suggestion_id} className="border border-gray-200 rounded-lg p-4">
          <div className="flex items-start justify-between mb-2">
            <p className="text-sm font-medium text-gray-900">{s.parameter}</p>
            <div className="flex items-center space-x-2 flex-shrink-0">
              <button
                onClick={() => handleApply(s.suggestion_id)}
                disabled={applyingId === s.suggestion_id}
                className="text-xs px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {applyingId === s.suggestion_id ? 'Applying...' : 'Apply'}
              </button>
              <button
                onClick={() => handleDismiss(s.suggestion_id)}
                className="text-xs px-2 py-1 text-gray-500 hover:text-gray-700"
              >
                Dismiss
              </button>
            </div>
          </div>
          <div className="flex items-center space-x-2 text-sm mb-2">
            <span className="text-gray-500">{String(s.current_value)}</span>
            <span className="text-gray-400">&rarr;</span>
            <span className="font-medium text-blue-700">{String(s.suggested_value)}</span>
          </div>
          <div className="mb-2">
            <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
              <span>Confidence</span>
              <span>{(s.confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all"
                style={{ width: `${s.confidence * 100}%` }}
              />
            </div>
          </div>
          <p className="text-xs text-gray-600">{s.rationale}</p>
        </div>
      ))}
    </div>
  );
};
