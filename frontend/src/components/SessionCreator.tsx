import React, { useState } from 'react';
import { useSession } from '../contexts/SessionContext';
import { Button } from './Button';
import { Input } from './Input';
import { Textarea } from './Textarea';
import { ErrorAlert } from './ErrorAlert';
import { LoadingSpinner } from './LoadingSpinner';
import { UserRoleToggle } from './UserRoleToggle';

interface SessionCreatorProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

export const SessionCreator: React.FC<SessionCreatorProps> = ({
  onSuccess,
  onCancel,
}) => {
  const { createSession, isLoading, error, clearError } = useSession();
  const [sessionName, setSessionName] = useState('');
  const [companyInfo, setCompanyInfo] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    clearError();

    if (!sessionName.trim()) {
      setValidationError('Session name is required');
      return;
    }

    try {
      await createSession(sessionName.trim(), companyInfo.trim() || undefined);
      setSessionName('');
      setCompanyInfo('');
      onSuccess?.();
    } catch (err) {
      // Error is handled by context
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">
        Create New Session
      </h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Session Name *"
          value={sessionName}
          onChange={(e) => setSessionName(e.target.value)}
          placeholder="e.g., Company ABC - Tax Consultation 2025"
          error={validationError || undefined}
          disabled={isLoading}
          required
        />
        <Textarea
          label="Company Information (Optional)"
          value={companyInfo}
          onChange={(e) => setCompanyInfo(e.target.value)}
          placeholder="Enter company details, industry, activities, etc."
          rows={4}
          disabled={isLoading}
        />
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            User Role
          </label>
          <UserRoleToggle />
        </div>
        {error && (
          <ErrorAlert message={error} onDismiss={clearError} />
        )}
        <div className="flex justify-end space-x-3 pt-4">
          {onCancel && (
            <Button
              type="button"
              variant="outline"
              onClick={onCancel}
              disabled={isLoading}
            >
              Cancel
            </Button>
          )}
          <Button type="submit" isLoading={isLoading}>
            Create Session
          </Button>
        </div>
      </form>
    </div>
  );
};

