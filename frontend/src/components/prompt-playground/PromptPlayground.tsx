import React, { useState } from 'react';
import { PromptEditor } from '../settings/PromptEditor';
import * as api from '../../api/client';
import { useSettings } from '../../contexts/SettingsContext';

interface PromptPlaygroundProps {
  initialPrompt?: string;
}

export const PromptPlayground: React.FC<PromptPlaygroundProps> = ({ initialPrompt = '' }) => {
  const { currentSettings } = useSettings();
  const [prompt, setPrompt] = useState(initialPrompt);
  const [testQuestion, setTestQuestion] = useState('');
  const [result, setResult] = useState<{ answer: string; latency_ms: number } | null>(null);
  const [currentResult, setCurrentResult] = useState<{ answer: string; latency_ms: number } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [compareWithCurrent, setCompareWithCurrent] = useState(false);

  const handleTest = async () => {
    if (!prompt.trim() || !testQuestion.trim()) return;
    setIsLoading(true);
    setResult(null);
    setCurrentResult(null);
    try {
      const testResult = await api.testPrompt({ prompt, test_question: testQuestion });
      setResult(testResult);

      if (compareWithCurrent && currentSettings) {
        const currentTestResult = await api.testPrompt({
          prompt: currentSettings.main_system_prompt,
          test_question: testQuestion,
        });
        setCurrentResult(currentTestResult);
      }
    } catch {
      // error handled by api client
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left pane: input */}
      <div className="space-y-4">
        <PromptEditor
          value={prompt}
          onChange={setPrompt}
          label="Test Prompt"
          placeholder="Enter the system prompt to test..."
          rows={8}
        />
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Test Question</label>
          <textarea
            value={testQuestion}
            onChange={(e) => setTestQuestion(e.target.value)}
            placeholder="Enter a question to test against the prompt..."
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
          />
        </div>
        <div className="flex items-center justify-between">
          <label className="flex items-center space-x-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={compareWithCurrent}
              onChange={(e) => setCompareWithCurrent(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span>Compare with current prompt</span>
          </label>
          <button
            onClick={handleTest}
            disabled={isLoading || !prompt.trim() || !testQuestion.trim()}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <span className="flex items-center">
                <svg className="animate-spin h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Testing...
              </span>
            ) : (
              'Test Prompt'
            )}
          </button>
        </div>
      </div>

      {/* Right pane: results */}
      <div className="space-y-4">
        {result ? (
          <div className="space-y-4">
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold text-gray-900">
                  {compareWithCurrent ? 'Test Prompt Response' : 'Response'}
                </h4>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                  {(result.latency_ms / 1000).toFixed(1)}s
                </span>
              </div>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{result.answer}</p>
            </div>

            {compareWithCurrent && currentResult && (
              <div className="border border-blue-200 rounded-lg p-4 bg-blue-50">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-semibold text-blue-900">Current Prompt Response</h4>
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
                    {(currentResult.latency_ms / 1000).toFixed(1)}s
                  </span>
                </div>
                <p className="text-sm text-blue-800 whitespace-pre-wrap">{currentResult.answer}</p>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full min-h-[200px] border border-dashed border-gray-300 rounded-lg">
            <p className="text-sm text-gray-400">
              {isLoading ? 'Running test...' : 'Enter a prompt and question, then click "Test Prompt"'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
