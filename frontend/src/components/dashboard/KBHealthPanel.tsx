import React from 'react';
import type { KBHealthData } from '../../api/types';

interface KBHealthPanelProps {
  data: KBHealthData | null;
  isLoading: boolean;
}

const formatRelativeTime = (isoDate: string | null): string => {
  if (!isoDate) return 'Never';
  const diff = Date.now() - new Date(isoDate).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return '1 day ago';
  return `${days} days ago`;
};

const getCoverageColor = (coverage: number): { text: string; bg: string; border: string } => {
  if (coverage >= 1.0) return { text: 'text-green-700', bg: 'bg-green-100', border: 'border-green-300' };
  if (coverage >= 0.8) return { text: 'text-yellow-700', bg: 'bg-yellow-100', border: 'border-yellow-300' };
  return { text: 'text-red-700', bg: 'bg-red-100', border: 'border-red-300' };
};

const getCoverageLabel = (coverage: number): string => {
  if (coverage >= 1.0) return 'Full';
  if (coverage >= 0.8) return 'Partial';
  return 'Low';
};

export const KBHealthPanel: React.FC<KBHealthPanelProps> = ({ data, isLoading }) => {
  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="h-5 w-48 bg-gray-200 rounded animate-pulse mb-4" />
        <div className="grid grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Knowledge Base Health</h3>
        <div className="flex items-center justify-center h-[200px] text-gray-400">
          No data available
        </div>
      </div>
    );
  }

  const coverageColors = getCoverageColor(data.embedding_coverage);

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Knowledge Base Health</h3>

      <div className="grid grid-cols-2 gap-3">
        {/* Total Documents */}
        <div className="bg-blue-50 rounded-lg p-3">
          <p className="text-xs font-medium text-blue-600">Total Documents</p>
          <p className="text-xl font-bold text-gray-900">{data.total_documents.toLocaleString()}</p>
        </div>

        {/* Total Chunks */}
        <div className="bg-purple-50 rounded-lg p-3">
          <p className="text-xs font-medium text-purple-600">Total Chunks</p>
          <p className="text-xl font-bold text-gray-900">{data.total_chunks.toLocaleString()}</p>
        </div>

        {/* Avg Chunks/Doc */}
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs font-medium text-gray-600">Avg Chunks/Doc</p>
          <p className="text-xl font-bold text-gray-900">{data.avg_chunks_per_doc.toFixed(1)}</p>
        </div>

        {/* Embedding Coverage */}
        <div className={`${coverageColors.bg} rounded-lg p-3`}>
          <p className={`text-xs font-medium ${coverageColors.text}`}>
            Embedding Coverage
          </p>
          <div className="flex items-center space-x-2">
            <p className="text-xl font-bold text-gray-900">
              {(data.embedding_coverage * 100).toFixed(0)}%
            </p>
            <span
              className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium border ${coverageColors.bg} ${coverageColors.text} ${coverageColors.border}`}
            >
              {getCoverageLabel(data.embedding_coverage)}
            </span>
          </div>
        </div>
      </div>

      {/* Last Ingestion */}
      <div className="mt-3 flex items-center justify-between text-sm text-gray-600 border-t border-gray-100 pt-3">
        <span>Last Ingestion</span>
        <span className="font-medium text-gray-900">{formatRelativeTime(data.last_ingestion)}</span>
      </div>

      {/* Stale document warning */}
      {data.stale_document_count > 0 && (
        <div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
          <span className="font-medium">Warning:</span> {data.stale_document_count} document{data.stale_document_count !== 1 ? 's haven\'t' : ' hasn\'t'} been updated in {data.stale_threshold_days} days
        </div>
      )}
    </div>
  );
};
