import React, { useState } from 'react';
import { useProject } from '../contexts/ProjectContext';
import { Button } from './Button';
import { Input } from './Input';
import { ErrorAlert } from './ErrorAlert';
import { TaxOfficeSelector, type TaxOffice } from './TaxOfficeSelector';
import { RegionSelector, type Region } from './RegionSelector';
import { IndustrySelector, type Industry } from './IndustrySelector';

interface ProjectCreatorProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

export const ProjectCreator: React.FC<ProjectCreatorProps> = ({ onSuccess, onCancel }) => {
  const { createProject, isLoading, error, clearError } = useProject();
  const [name, setName] = useState('');
  const [selectedTaxOffice, setSelectedTaxOffice] = useState<TaxOffice | null>(null);
  const [selectedRegion, setSelectedRegion] = useState<Region | null>(null);
  const [selectedIndustries, setSelectedIndustries] = useState<Industry[]>([]);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    clearError();

    if (!name.trim()) {
      setValidationError('Project name is required');
      return;
    }

    try {
      await createProject({
        name: name.trim(),
        tax_office_id: selectedTaxOffice?.kodjednostki ?? null,
        region: selectedRegion?.name ?? null,
        // Use first selected industry code, or null if none selected
        industry: selectedIndustries.length > 0 ? selectedIndustries[0].code : null,
      });
      setName('');
      setSelectedTaxOffice(null);
      setSelectedRegion(null);
      setSelectedIndustries([]);
      onSuccess?.();
    } catch {
      // handled by context
    }
  };

  const handleTaxOfficeChange = (taxOffice: TaxOffice | null) => {
    setSelectedTaxOffice(taxOffice);
    // Auto-set region when tax office is selected
    if (taxOffice && !selectedRegion) {
      // The region selector expects a Region object, but we can set just the name
      // since the RegionSelector will display based on name
      setSelectedRegion({ name: taxOffice.wojewodztwo, display_name: taxOffice.wojewodztwo });
    }
  };

  const handleRegionChange = (region: Region | null) => {
    setSelectedRegion(region);
  };

  const handleIndustryChange = (industries: Industry[]) => {
    setSelectedIndustries(industries);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        label="Project Name *"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="e.g., Company ABC - 2025 VAT Case"
        error={validationError || undefined}
        disabled={isLoading}
        required
      />

      <TaxOfficeSelector
        value={selectedTaxOffice?.kodjednostki ?? null}
        onChange={handleTaxOfficeChange}
        label="Tax Office"
        placeholder="Search by name, city, or ID..."
        disabled={isLoading}
      />

      <RegionSelector
        value={selectedRegion?.name ?? null}
        onChange={handleRegionChange}
        label="Region (Voivodeship)"
        placeholder="Select a region..."
        disabled={isLoading}
        clearable
      />

      <IndustrySelector
        value={selectedIndustries.map((i) => i.code)}
        onChange={handleIndustryChange}
        label="Industry"
        placeholder="Select an industry..."
        disabled={isLoading}
        maxSelections={1}
      />

      {error && <ErrorAlert message={error} onDismiss={clearError} />}

      <div className="flex justify-end space-x-3 pt-4">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
            Cancel
          </Button>
        )}
        <Button type="submit" isLoading={isLoading}>
          Create Project
        </Button>
      </div>
    </form>
  );
};
