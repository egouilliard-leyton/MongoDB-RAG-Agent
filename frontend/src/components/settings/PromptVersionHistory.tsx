import React, { useState } from 'react';
import { Modal } from '../Modal';
import type { SettingsVersion } from '../../api/types';

interface PromptVersionHistoryProps {
  versions: SettingsVersion[];
  currentVersion: number;
  onRestore: (version: number) => Promise<void>;
  onClose: () => void;
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export const PromptVersionHistory: React.FC<PromptVersionHistoryProps> = ({
  versions,
  currentVersion,
  onRestore,
  onClose,
}) => {
  const [confirmingVersion, setConfirmingVersion] = useState<number | null>(null);
  const [isRestoring, setIsRestoring] = useState(false);

  const handleRestore = async (version: number) => {
    setIsRestoring(true);
    try {
      await onRestore(version);
      setConfirmingVersion(null);
      onClose();
    } catch {
      // error handled by context
    } finally {
      setIsRestoring(false);
    }
  };

  return (
    <Modal isOpen={true} onClose={onClose} title="Version History" size="lg">
      <div className="space-y-3">
        {versions.length === 0 && (
          <p className="text-sm text-gray-500 text-center py-4">No version history available.</p>
        )}
        {versions.map((v) => (
          <div
            key={v.version}
            className="flex items-start justify-between p-3 border border-gray-200 rounded-lg"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2 mb-1">
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                  v{v.version}
                </span>
                {v.version === currentVersion && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-blue-100 text-blue-800 border-blue-300">
                    Current
                  </span>
                )}
                <span className="text-xs text-gray-500">{formatRelativeTime(v.created_at)}</span>
              </div>
              <p className="text-sm text-gray-700 truncate">{v.summary}</p>
              {v.changed_fields.length > 0 && (
                <p className="text-xs text-gray-400 mt-0.5">
                  Changed: {v.changed_fields.join(', ')}
                </p>
              )}
            </div>
            <div className="ml-3 flex-shrink-0">
              {v.version === currentVersion ? null : confirmingVersion === v.version ? (
                <div className="flex items-center space-x-2">
                  <span className="text-xs text-gray-600">Are you sure?</span>
                  <button
                    onClick={() => handleRestore(v.version)}
                    disabled={isRestoring}
                    className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                  >
                    {isRestoring ? 'Restoring...' : 'Confirm'}
                  </button>
                  <button
                    onClick={() => setConfirmingVersion(null)}
                    className="text-xs px-2 py-1 text-gray-600 hover:text-gray-800"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setConfirmingVersion(v.version)}
                  className="text-xs px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 text-gray-700"
                >
                  Restore
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </Modal>
  );
};
