import React, { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react';
import type { SettingsResponse, SettingsVersion, SettingsUpdateRequest } from '../api/types';
import * as api from '../api/client';

interface SettingsContextType {
  currentSettings: SettingsResponse | null;
  versionHistory: SettingsVersion[];
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  loadSettings: () => Promise<void>;
  saveSettings: (changes: SettingsUpdateRequest) => Promise<void>;
  loadHistory: () => Promise<void>;
  restoreVersion: (version: number) => Promise<void>;
  clearError: () => void;
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export const useSettings = () => {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within a SettingsProvider');
  return ctx;
};

interface SettingsProviderProps {
  children: ReactNode;
}

export const SettingsProvider: React.FC<SettingsProviderProps> = ({ children }) => {
  const [currentSettings, setCurrentSettings] = useState<SettingsResponse | null>(null);
  const [versionHistory, setVersionHistory] = useState<SettingsVersion[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSettings = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const settings = await api.getSettings();
      setCurrentSettings(settings);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load settings';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const saveSettings = useCallback(async (changes: SettingsUpdateRequest) => {
    setIsSaving(true);
    setError(null);
    try {
      const updated = await api.updateSettings(changes);
      setCurrentSettings(updated);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save settings';
      setError(message);
      throw err;
    } finally {
      setIsSaving(false);
    }
  }, []);

  const loadHistory = useCallback(async () => {
    setError(null);
    try {
      const history = await api.getSettingsHistory();
      setVersionHistory(history);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load version history';
      setError(message);
    }
  }, []);

  const restoreVersion = useCallback(async (version: number) => {
    setIsSaving(true);
    setError(null);
    try {
      const restored = await api.restoreSettings(version);
      setCurrentSettings(restored);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to restore version';
      setError(message);
      throw err;
    } finally {
      setIsSaving(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const value: SettingsContextType = {
    currentSettings,
    versionHistory,
    isLoading,
    isSaving,
    error,
    loadSettings,
    saveSettings,
    loadHistory,
    restoreVersion,
    clearError,
  };

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
};
