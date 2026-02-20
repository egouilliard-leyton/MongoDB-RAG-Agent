import React, { useRef, useState } from 'react';
import { useProject } from '../contexts/ProjectContext';
import { Button } from './Button';
import { ErrorAlert } from './ErrorAlert';

export const ProjectUploads: React.FC = () => {
  const { currentProject, uploadDocument, isLoading, error, clearError } = useProject();
  const inputRef = useRef<HTMLInputElement>(null);
  const [lastMessage, setLastMessage] = useState<string | null>(null);

  if (!currentProject) return null;

  const handlePick = () => inputRef.current?.click();

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    clearError();
    setLastMessage(null);

    const file = e.target.files?.[0];
    if (!file) return;

    try {
      await uploadDocument(currentProject._id, file);
      setLastMessage(`Uploaded and ingested: ${file.name}`);
    } catch {
      // handled by context
    } finally {
      // reset so same file can be selected again
      e.target.value = '';
    }
  };

  return (
    <div className="border-t border-gray-200 pt-4 space-y-3">
      <h3 className="text-sm font-medium text-gray-700">Project Uploads</h3>
      <p className="text-xs text-gray-500">
        Upload a PDF/DOCX/PPTX to add it to this project’s knowledge base.
      </p>

      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept=".pdf,.docx,.pptx"
        onChange={handleChange}
      />

      <Button variant="outline" size="sm" onClick={handlePick} disabled={isLoading}>
        Upload Document
      </Button>

      {lastMessage && <p className="text-xs text-green-700">{lastMessage}</p>}
      {error && <ErrorAlert message={error} onDismiss={clearError} />}
    </div>
  );
};


