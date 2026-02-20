import React, { useCallback, useState } from 'react';
import type { Citation } from '../api/types';

interface CitationListProps {
  citations: Citation[];
  className?: string;
}

export const CitationList: React.FC<CitationListProps> = ({
  citations,
  className = '',
}) => {
  if (citations.length === 0) {
    return null;
  }

  const [showDetails, setShowDetails] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const formatObjectId = useCallback((value: string) => {
    const v = String(value ?? '');
    if (v.length <= 18) return v;
    return `${v.slice(0, 8)}…${v.slice(-8)}`;
  }, []);

  const copyToClipboard = useCallback(async (text: string) => {
    const value = String(text ?? '');
    if (!value) return;

    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // Fallback for older browsers / insecure contexts
      const el = document.createElement('textarea');
      el.value = value;
      el.setAttribute('readonly', 'true');
      el.style.position = 'fixed';
      el.style.top = '-1000px';
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
    }
  }, []);

  const similarityBadge = useCallback((similarity?: number) => {
    if (similarity === undefined || similarity === null || Number.isNaN(similarity)) return null;

    const value = Math.max(0, Math.min(1, similarity));
    const label = value.toFixed(2);

    const color =
      value >= 0.85
        ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
        : value >= 0.7
          ? 'bg-green-100 text-green-800 border-green-200'
          : value >= 0.55
            ? 'bg-yellow-100 text-yellow-800 border-yellow-200'
            : 'bg-red-100 text-red-800 border-red-200';

    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${color}`}
        title="Vector similarity score (0 to 1)"
      >
        Similarity {label}
      </span>
    );
  }, []);

  return (
    <div className={`mt-4 ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium text-gray-700">Citations:</h4>
        <button
          type="button"
          className="text-sm text-blue-600 hover:text-blue-800 underline"
          onClick={() => setShowDetails((v) => !v)}
        >
          {showDetails ? 'Hide details' : 'Show details'}
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {citations.map((citation, index) => (
          <button
            type="button"
            key={index}
            className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors"
            title="Source document"
          >
            <span className="mr-1">[{citation.citation_number}]</span>
            {citation.document_title}
          </button>
        ))}
      </div>

      {showDetails && (
        <div className="mt-3 space-y-2">
          {citations.map((citation, index) => {
            const key = `${citation.document_id}-${citation.chunk_id ?? ''}-${citation.citation_number}-${index}`;
            const canCopy = Boolean(citation.document_id);
            const copied = copiedKey === key;

            return (
              <div
                key={key}
                className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      [{citation.citation_number}] {citation.document_title}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      {similarityBadge(citation.similarity)}
                      {citation.source ? (
                        <span
                          className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 border border-gray-200"
                          title="Document source / filename"
                        >
                          Source {citation.source}
                        </span>
                      ) : null}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span
                      className="font-mono text-xs text-gray-700"
                      title={citation.document_id}
                    >
                      {formatObjectId(citation.document_id)}
                    </span>
                    <button
                      type="button"
                      disabled={!canCopy}
                      className={[
                        'px-2 py-1 rounded text-xs font-medium border transition-colors',
                        canCopy
                          ? 'bg-white text-gray-800 border-gray-200 hover:bg-gray-50'
                          : 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed',
                      ].join(' ')}
                      onClick={async () => {
                        if (!citation.document_id) return;
                        await copyToClipboard(citation.document_id);
                        setCopiedKey(key);
                        window.setTimeout(() => setCopiedKey((v) => (v === key ? null : v)), 1500);
                      }}
                      title="Copy MongoDB document_id"
                    >
                      {copied ? 'Copied' : 'Copy id'}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

