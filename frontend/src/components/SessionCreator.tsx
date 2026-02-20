import React, { useState } from 'react';
import { useSession } from '../contexts/SessionContext';
import { useProject } from '../contexts/ProjectContext';
import { Button } from './Button';
import { Input } from './Input';
import { Textarea } from './Textarea';
import { ErrorAlert } from './ErrorAlert';
import { UserRoleToggle } from './UserRoleToggle';
import { TaxOfficeSelector, type TaxOffice } from './TaxOfficeSelector';
import { RegionSelector } from './RegionSelector';

interface SessionCreatorProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

export const SessionCreator: React.FC<SessionCreatorProps> = ({
  onSuccess,
  onCancel,
}) => {
  const { createSession, isLoading, error, clearError } = useSession();
  const { currentProject } = useProject();
  const [sessionName, setSessionName] = useState('');
  const [companyInfo, setCompanyInfo] = useState('');
  const [selectedTaxOffice, setSelectedTaxOffice] = useState<TaxOffice | null>(null);
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    clearError();

    if (!sessionName.trim()) {
      setValidationError('Session name is required');
      return;
    }
    if (!currentProject?._id) {
      setValidationError('Please select a project first');
      return;
    }

    try {
      await createSession(sessionName.trim(), {
        companyInfo: companyInfo.trim() || undefined,
        projectId: currentProject._id,
        taxOfficeId: selectedTaxOffice?.kodjednostki ?? null,
        region: selectedRegion ?? null,
      });
      setSessionName('');
      setCompanyInfo('');
      setSelectedTaxOffice(null);
      setSelectedRegion(null);
      onSuccess?.();
    } catch (err) {
      // Error is handled by context
    }
  };

  return (
    <>
      {currentProject && (
        <p className="text-sm text-gray-600 mb-4">
          This session will be linked to project: <span className="font-medium">{currentProject.name}</span>
        </p>
      )}
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
        <TaxOfficeSelector
          label="Tax Office (Optional)"
          value={selectedTaxOffice?.kodjednostki ?? null}
          onChange={(taxOffice) => setSelectedTaxOffice(taxOffice)}
          disabled={isLoading}
          placeholder="Search by name, city, or ID..."
        />
        <RegionSelector
          label="Region (Optional)"
          value={selectedRegion}
          onChange={(region) => setSelectedRegion(region?.name ?? null)}
          disabled={isLoading}
          placeholder="Select a region..."
          clearable
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
    </>
  );
};

