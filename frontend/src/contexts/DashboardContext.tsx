import React, { createContext, useCallback, useContext, useState, ReactNode } from 'react';
import type {
  DashboardSummary,
  RegionDistribution,
  IndustryDistribution,
  TaxOfficeDistribution,
  TrendsResponse,
  QualityMetricsResponse,
  StageFunnelResponse,
  QualityTrendResponse,
  KBHealthData,
  SystemMetricsData,
} from '../api/types';
import * as api from '../api/client';

interface DashboardContextType {
  summary: DashboardSummary | null;
  regionDistribution: RegionDistribution | null;
  industryDistribution: IndustryDistribution | null;
  taxOfficeDistribution: TaxOfficeDistribution | null;
  trends: TrendsResponse | null;
  qualityMetrics: QualityMetricsResponse | null;
  stageFunnel: StageFunnelResponse | null;
  qualityTrends: QualityTrendResponse | null;
  kbHealth: KBHealthData | null;
  systemMetrics: SystemMetricsData | null;
  isLoading: boolean;
  isLoadingExtended: boolean;
  error: string | null;
  loadSummary: () => Promise<void>;
  loadRegionDistribution: () => Promise<void>;
  loadIndustryDistribution: () => Promise<void>;
  loadTaxOfficeDistribution: (limit?: number) => Promise<void>;
  loadTrends: (days?: number, granularity?: 'day' | 'week' | 'month') => Promise<void>;
  loadQualityMetrics: () => Promise<void>;
  loadStageFunnel: () => Promise<void>;
  loadQualityTrends: (days?: number, granularity?: 'day' | 'week' | 'month') => Promise<void>;
  loadKBHealth: () => Promise<void>;
  loadSystemMetrics: () => Promise<void>;
  loadAllData: () => Promise<void>;
  clearError: () => void;
}

const DashboardContext = createContext<DashboardContextType | undefined>(undefined);

export const useDashboard = () => {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error('useDashboard must be used within a DashboardProvider');
  return ctx;
};

interface DashboardProviderProps {
  children: ReactNode;
}

export const DashboardProvider: React.FC<DashboardProviderProps> = ({ children }) => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [regionDistribution, setRegionDistribution] = useState<RegionDistribution | null>(null);
  const [industryDistribution, setIndustryDistribution] = useState<IndustryDistribution | null>(null);
  const [taxOfficeDistribution, setTaxOfficeDistribution] = useState<TaxOfficeDistribution | null>(null);
  const [trends, setTrends] = useState<TrendsResponse | null>(null);
  const [qualityMetrics, setQualityMetrics] = useState<QualityMetricsResponse | null>(null);
  const [stageFunnel, setStageFunnel] = useState<StageFunnelResponse | null>(null);
  const [qualityTrends, setQualityTrends] = useState<QualityTrendResponse | null>(null);
  const [kbHealth, setKBHealth] = useState<KBHealthData | null>(null);
  const [systemMetrics, setSystemMetrics] = useState<SystemMetricsData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingExtended, setIsLoadingExtended] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSummary = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getDashboardSummary();
      setSummary(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load dashboard summary';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadRegionDistribution = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getRegionDistribution();
      setRegionDistribution(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load region distribution';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadIndustryDistribution = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getIndustryDistribution();
      setIndustryDistribution(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load industry distribution';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadTaxOfficeDistribution = useCallback(async (limit: number = 20) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getTaxOfficeDistribution(limit);
      setTaxOfficeDistribution(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load tax office distribution';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadTrends = useCallback(async (days: number = 30, granularity: 'day' | 'week' | 'month' = 'day') => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getDashboardTrends(days, granularity);
      setTrends(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load trends';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadQualityMetrics = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getQualityMetrics();
      setQualityMetrics(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load quality metrics';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadStageFunnel = useCallback(async () => {
    setIsLoadingExtended(true);
    try {
      const data = await api.getStageFunnel();
      setStageFunnel(data);
    } catch (err) {
      console.error('Failed to load stage funnel:', err);
    } finally {
      setIsLoadingExtended(false);
    }
  }, []);

  const loadQualityTrends = useCallback(async (days: number = 30, granularity: 'day' | 'week' | 'month' = 'day') => {
    setIsLoadingExtended(true);
    try {
      const data = await api.getQualityTrend(days, granularity);
      setQualityTrends(data);
    } catch (err) {
      console.error('Failed to load quality trends:', err);
    } finally {
      setIsLoadingExtended(false);
    }
  }, []);

  const loadKBHealth = useCallback(async () => {
    setIsLoadingExtended(true);
    try {
      const data = await api.getKBHealth();
      setKBHealth(data);
    } catch (err) {
      console.error('Failed to load KB health:', err);
    } finally {
      setIsLoadingExtended(false);
    }
  }, []);

  const loadSystemMetrics = useCallback(async () => {
    setIsLoadingExtended(true);
    try {
      const data = await api.getSystemMetrics();
      setSystemMetrics(data);
    } catch (err) {
      console.error('Failed to load system metrics:', err);
    } finally {
      setIsLoadingExtended(false);
    }
  }, []);

  const loadAllData = useCallback(async () => {
    setIsLoading(true);
    setIsLoadingExtended(true);
    setError(null);
    try {
      // Load all data in parallel (both original and extended panels)
      const [
        summaryData, regionData, industryData, taxOfficeData, trendsData, qualityData,
        stageFunnelData, qualityTrendsData, kbHealthData, systemMetricsData,
      ] = await Promise.all([
        api.getDashboardSummary(),
        api.getRegionDistribution(),
        api.getIndustryDistribution(),
        api.getTaxOfficeDistribution(20),
        api.getDashboardTrends(30, 'day'),
        api.getQualityMetrics(),
        api.getStageFunnel().catch(() => null),
        api.getQualityTrend(30, 'day').catch(() => null),
        api.getKBHealth().catch(() => null),
        api.getSystemMetrics().catch(() => null),
      ]);

      setSummary(summaryData);
      setRegionDistribution(regionData);
      setIndustryDistribution(industryData);
      setTaxOfficeDistribution(taxOfficeData);
      setTrends(trendsData);
      setQualityMetrics(qualityData);
      setStageFunnel(stageFunnelData);
      setQualityTrends(qualityTrendsData);
      setKBHealth(kbHealthData);
      setSystemMetrics(systemMetricsData);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load dashboard data';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
      setIsLoadingExtended(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const value: DashboardContextType = {
    summary,
    regionDistribution,
    industryDistribution,
    taxOfficeDistribution,
    trends,
    qualityMetrics,
    stageFunnel,
    qualityTrends,
    kbHealth,
    systemMetrics,
    isLoading,
    isLoadingExtended,
    error,
    loadSummary,
    loadRegionDistribution,
    loadIndustryDistribution,
    loadTaxOfficeDistribution,
    loadTrends,
    loadQualityMetrics,
    loadStageFunnel,
    loadQualityTrends,
    loadKBHealth,
    loadSystemMetrics,
    loadAllData,
    clearError,
  };

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
};
