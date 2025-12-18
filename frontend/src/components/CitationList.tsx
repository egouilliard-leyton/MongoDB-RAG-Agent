import React from 'react';
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

  return (
    <div className={`mt-4 ${className}`}>
      <h4 className="text-sm font-medium text-gray-700 mb-2">Citations:</h4>
      <div className="flex flex-wrap gap-2">
        {citations.map((citation, index) => (
          <a
            key={index}
            href="#"
            className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors"
            onClick={(e) => {
              e.preventDefault();
              // TODO: Implement document viewer or link to document
              console.log('Citation clicked:', citation);
            }}
          >
            <span className="mr-1">[{citation.citation_number}]</span>
            {citation.document_title}
          </a>
        ))}
      </div>
    </div>
  );
};

