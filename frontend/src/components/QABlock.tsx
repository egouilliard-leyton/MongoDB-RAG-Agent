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
  const { updateAnswer, updateRating } = useQABlocks();
  const [isEditing, setIsEditing] = useState(false);
  const [editedAnswer, setEditedAnswer] = useState(qaPair.final_answer);
  const [isSaving, setIsSaving] = useState(false);
  const [isRatingSaving, setIsRatingSaving] = useState(false);
  const [showReview, setShowReview] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const saveTimeoutRef = useRef<NodeJS.Timeout>();

  const isSenior = userRole === 'senior';

  const uniqueSourceDocCount = React.useMemo(() => {
    const ids = new Set(
      (qaPair.citations ?? []).map((c) => c?.document_id).filter(Boolean)
    );
    return ids.size;
  }, [qaPair.citations]);

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
      const qaPairId = qaPair._id || qaPair.qa_pair_id;
      if (!qaPairId) return;
      await updateAnswer(qaPairId, editedAnswer);
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

  const getReviewBadge = () => {
    if (!qaPair.review) return null;
    const verdict = qaPair.review.verdict;
    if (verdict === 'good') {
      return (
        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
          Review: good
        </span>
      );
    }
    if (verdict === 'risk') {
      return (
        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
          Review: risk
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
        Review: needs info
      </span>
    );
  };

  const handleToggleRating = useCallback(
    async (next: boolean) => {
      if (!isSenior) return;
      const qaPairId = qaPair._id || qaPair.qa_pair_id;
      if (!qaPairId) return;

      const current = qaPair.rating_good ?? null;
      const nextValue = current === next ? null : next;

      setIsRatingSaving(true);
      try {
        await updateRating(qaPairId, nextValue);
      } catch (err) {
        console.error('Failed to update rating:', err);
      } finally {
        setIsRatingSaving(false);
      }
    },
    [isSenior, qaPair._id, qaPair.qa_pair_id, qaPair.rating_good, updateRating]
  );

  return (
    <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200 hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-2">
            <span className="text-sm font-medium text-gray-500">
              Question #{qaPair.question_index + 1}
            </span>
            {getOutcomeBadge()}
            {getReviewBadge()}
            {(qaPair.was_edited || false) && (
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
                Edited
              </span>
            )}
          </div>
          <h3 className="text-lg font-semibold text-gray-900">
            {qaPair.question}
          </h3>
        </div>
        {isSenior && (
          <div className="ml-4 flex items-center space-x-2">
            <button
              type="button"
              onClick={() => handleToggleRating(true)}
              disabled={isRatingSaving}
              className={[
                "px-2 py-1 rounded-full text-xs font-medium border transition-colors",
                (qaPair.rating_good ?? null) === true
                  ? "bg-green-100 text-green-800 border-green-200"
                  : "bg-white text-gray-700 border-gray-200 hover:bg-gray-50",
                isRatingSaving ? "opacity-60 cursor-not-allowed" : "",
              ].join(" ")}
              title="Mark as good (click again to clear)"
            >
              Good
            </button>
            <button
              type="button"
              onClick={() => handleToggleRating(false)}
              disabled={isRatingSaving}
              className={[
                "px-2 py-1 rounded-full text-xs font-medium border transition-colors",
                (qaPair.rating_good ?? null) === false
                  ? "bg-red-100 text-red-800 border-red-200"
                  : "bg-white text-gray-700 border-gray-200 hover:bg-gray-50",
                isRatingSaving ? "opacity-60 cursor-not-allowed" : "",
              ].join(" ")}
              title="Mark as bad (click again to clear)"
            >
              Bad
            </button>
          </div>
        )}
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

      {qaPair.review && (
        <div className="mt-4 border-t border-gray-200 pt-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-gray-700">Review</p>
            <button
              type="button"
              className="text-sm text-blue-600 hover:text-blue-800 underline"
              onClick={() => setShowReview((v) => !v)}
            >
              {showReview ? 'Hide' : 'Show'}
            </button>
          </div>
          {showReview && (
            <div className="mt-2 text-sm text-gray-700 space-y-2">
              <p>{qaPair.review.summary}</p>
              {qaPair.review.missing_info?.length ? (
                <div>
                  <p className="text-xs font-medium text-gray-600">Missing info to ask for:</p>
                  <ul className="list-disc pl-5 mt-1 space-y-1">
                    {qaPair.review.missing_info.slice(0, 8).map((mi, idx) => (
                      <li key={idx}>{mi}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          )}
        </div>
      )}

      <div className="mt-4">
        {uniqueSourceDocCount === 0 ? (
          <p className="text-xs text-gray-500">No sources found in knowledge base</p>
        ) : (
          <p className="text-xs text-gray-500">
            Sources used: {uniqueSourceDocCount} document{uniqueSourceDocCount === 1 ? '' : 's'}
          </p>
        )}
      </div>
      <CitationList citations={qaPair.citations} />
    </div>
  );
};

