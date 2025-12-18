import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useSession } from '../contexts/SessionContext';
import { useQABlocks } from '../contexts/QABlocksContext';
import type { QAPair } from '../api/types';
import { Button } from './Button';
import { Textarea } from './Textarea';
import { CitationList } from './CitationList';

interface QABlockProps {
  qaPair: QAPair;
}

export const QABlock: React.FC<QABlockProps> = ({ qaPair }) => {
  const { userRole } = useSession();
  const { updateAnswer } = useQABlocks();
  const [isEditing, setIsEditing] = useState(false);
  const [editedAnswer, setEditedAnswer] = useState(qaPair.final_answer);
  const [isSaving, setIsSaving] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const saveTimeoutRef = useRef<NodeJS.Timeout>();

  const isSenior = userRole === 'senior';

  useEffect(() => {
    setEditedAnswer(qaPair.final_answer);
  }, [qaPair.final_answer]);

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [isEditing, editedAnswer]);

  const handleSave = useCallback(async () => {
    if (!isSenior) return;

    setIsSaving(true);
    try {
      await updateAnswer(qaPair._id, editedAnswer);
      setIsEditing(false);
    } catch (err) {
      console.error('Failed to save answer:', err);
    } finally {
      setIsSaving(false);
    }
  }, [isSenior, qaPair._id, editedAnswer, updateAnswer]);

  const handleCancel = useCallback(() => {
    setEditedAnswer(qaPair.final_answer);
    setIsEditing(false);
  }, [qaPair.final_answer]);

  const handleBlur = useCallback(() => {
    // Auto-save on blur (debounced)
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    saveTimeoutRef.current = setTimeout(() => {
      if (isEditing && editedAnswer !== qaPair.final_answer) {
        handleSave();
      }
    }, 1000);
  }, [isEditing, editedAnswer, qaPair.final_answer, handleSave]);

  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  const getOutcomeBadge = () => {
    if (qaPair.outcome_status === 'successful') {
      return (
        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
          ✓ Successful
        </span>
      );
    }
    if (qaPair.outcome_status === 'unsuccessful') {
      return (
        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
          ✗ Unsuccessful
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
        Pending
      </span>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200 hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-2">
            <span className="text-sm font-medium text-gray-500">
              Question #{qaPair.question_index + 1}
            </span>
            {getOutcomeBadge()}
          </div>
          <h3 className="text-lg font-semibold text-gray-900">
            {qaPair.question}
          </h3>
        </div>
      </div>

      <div className="mt-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Answer:
        </label>
        {isEditing && isSenior ? (
          <div className="space-y-3">
            <Textarea
              ref={textareaRef}
              value={editedAnswer}
              onChange={(e) => setEditedAnswer(e.target.value)}
              onBlur={handleBlur}
              rows={6}
              showCharCount
              className="font-sans"
            />
            <div className="flex justify-end space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancel}
                disabled={isSaving}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleSave}
                isLoading={isSaving}
              >
                Save
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="prose max-w-none">
              <p className="text-gray-700 whitespace-pre-wrap">
                {qaPair.final_answer}
              </p>
            </div>
            {isSenior && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsEditing(true)}
              >
                Edit Answer
              </Button>
            )}
          </div>
        )}
      </div>

      <CitationList citations={qaPair.citations} />
    </div>
  );
};

