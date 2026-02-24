import React from 'react';

interface PromptEditorProps {
  value: string;
  onChange: (value: string) => void;
  label: string;
  placeholder?: string;
  rows?: number;
  showResetButton?: boolean;
  defaultValue?: string;
}

export const PromptEditor: React.FC<PromptEditorProps> = ({
  value,
  onChange,
  label,
  placeholder,
  rows = 6,
  showResetButton = false,
  defaultValue,
}) => {
  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1">
        <label className="block text-sm font-medium text-gray-700">{label}</label>
        {showResetButton && defaultValue !== undefined && value !== defaultValue && (
          <button
            type="button"
            onClick={() => onChange(defaultValue)}
            className="text-xs text-blue-600 hover:text-blue-800"
          >
            Reset to default
          </button>
        )}
      </div>
      <textarea
        className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y font-mono text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
      />
      <div className="flex items-center justify-between mt-1">
        <p className="text-xs text-gray-400">
          Use {'{query}'}, {'{context}'}, {'{history}'} as placeholders
        </p>
        <p className="text-xs text-gray-500">{value.length} characters</p>
      </div>
    </div>
  );
};
