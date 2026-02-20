import React from 'react';

interface StatusBadgeProps {
  status: string | null | undefined;
  type: 'session' | 'outcome' | 'stage';
  className?: string;
}

const statusColors: Record<string, { bg: string; text: string; border: string }> = {
  // Session statuses
  active: { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-300' },
  draft: { bg: 'bg-gray-100', text: 'text-gray-800', border: 'border-gray-300' },
  exported: { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-300' },
  approved: { bg: 'bg-purple-100', text: 'text-purple-800', border: 'border-purple-300' },
  
  // Outcome statuses
  pending: { bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-300' },
  successful: { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-300' },
  unsuccessful: { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-300' },
  
  // Stage statuses
  current: { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-300' },
  completed: { bg: 'bg-gray-100', text: 'text-gray-800', border: 'border-gray-300' },
  available: { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-300' },
  terminal: { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-300' },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, type: _type, className = '' }) => {
  if (!status) return null;

  const normalizedStatus = status.toLowerCase();
  const colors = statusColors[normalizedStatus] || {
    bg: 'bg-gray-100',
    text: 'text-gray-800',
    border: 'border-gray-300',
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border ${colors.bg} ${colors.text} ${colors.border} ${className}`}
    >
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
};

