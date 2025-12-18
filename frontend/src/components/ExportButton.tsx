import React, { useState, useCallback } from 'react';
import { useSession } from '../contexts/SessionContext';
import { Button } from './Button';
import * as api from '../api/client';

type ExportFormat = 'markdown' | 'pdf' | 'docx';

interface ExportButtonProps {
  className?: string;
}

export const ExportButton: React.FC<ExportButtonProps> = ({ className = '' }) => {
  const { currentSession } = useSession();
  const [format, setFormat] = useState<ExportFormat>('markdown');
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExport = useCallback(async () => {
    if (!currentSession) {
      setError('No session selected');
      return;
    }

    setIsExporting(true);
    setError(null);

    try {
      const blob = await api.exportSession(currentSession._id, format);
      
      // Create blob URL and trigger download
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // Extract filename from Content-Disposition header if available
      // For now, generate filename based on session name and format
      const sessionName = currentSession.session_name
        .replace(/[^a-z0-9]/gi, '_')
        .toLowerCase();
      const extension = format === 'markdown' ? 'md' : format;
      const timestamp = new Date().toISOString().split('T')[0];
      link.download = `${sessionName}_${timestamp}.${extension}`;
      
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      // Clean up blob URL
      window.URL.revokeObjectURL(url);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to export session';
      setError(message);
      console.error('Export error:', err);
    } finally {
      setIsExporting(false);
    }
  }, [currentSession, format]);

  if (!currentSession) {
    return null;
  }

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center space-x-2">
        <select
          value={format}
          onChange={(e) => setFormat(e.target.value as ExportFormat)}
          disabled={isExporting}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <option value="markdown">Markdown</option>
          <option value="pdf">PDF</option>
          <option value="docx">Word</option>
        </select>
        <Button
          onClick={handleExport}
          isLoading={isExporting}
          disabled={isExporting}
          size="sm"
        >
          Export Session
        </Button>
      </div>
      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
    </div>
  );
};

