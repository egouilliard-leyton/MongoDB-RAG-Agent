# CR: MVP Completion - Full Feature Implementation

**Created:** 2026-01-23
**Status:** Draft
**Scope:** Large
**Priority:** P1-High

## Summary

Complete implementation of all MVP features identified from client meeting requirements, including tax office integration, region selection, industry classification via Gemini API, analytics dashboard, exemplar management, and enhanced outcome tracking.

## Problem Statement

The current system has core functionality implemented (document ingestion, Q&A workflow, sessions, projects, stages) but lacks several critical features required for MVP delivery to the client (Qaza). Missing features include:
- Tax office integration with 590 Polish tax offices
- Region (voivodeship) selection and filtering
- Industry classification using Gemini File Search API
- Analytics dashboard with key metrics
- Exemplar management for quality improvement
- Enhanced outcome tracking (successful/partial/negative)

## Current Behavior

### Implemented Features (Working):
- Multi-format document upload & ingestion (PDF, DOCX, PPTX, Excel, HTML, Markdown, Audio)
- Project management with 14-stage workflow state machine
- Session management with junior/senior roles
- Q&A workflow with agentic multi-step search
- Follow-up sessions with parent linking
- Good/bad rating on Q&A pairs
- Basic system health and ingestion statistics

### Missing Features:
- No tax office entity or filtering
- No region selection or geographic scoping
- No automatic industry classification
- No analytics dashboard
- No exemplar management
- Outcome tracking only at session level, not Q&A pair level

## Desired Behavior

### 1. Tax Office Integration
- MongoDB collection `tax_offices` with 590 offices from client Excel
- Tax office selection during project and session creation
- Tax office-based search filtering
- Tax office searchable by name, city, or `kodjednostki` (ID)
- Display tax office info in project/session views

### 2. Region Selection
- 16 Polish voivodeships available for selection
- Region field on projects and sessions (optional, backward compatible)
- Region-based search filtering
- Region selector dropdown in UI

### 3. Industry Classification (Gemini File Search)
- During ingestion: upload document to Gemini, classify industry
- Delete document from Gemini after classification
- Store industry in document metadata
- Manual override capability via checkbox selection
- 18 predefined industries from client list
- Industry-based search filtering with "Select All" option

### 4. Analytics Dashboard
- Dedicated `/dashboard` route
- Metrics: project count, session count, success rates
- Distribution charts: by region, by industry, by tax office
- Trends over time
- Q&A quality metrics (good/bad ratios)

### 5. Exemplar Management
- Threshold-based auto-promotion: good rating + confidence >= 0.8 + citations >= 2 + review verdict "good"
- Exemplar flag on Q&A pairs
- Exemplar filtering for RAG context
- Exemplar management API endpoints

### 6. Enhanced Outcome Tracking
- Outcome status at Q&A pair level (successful/partial/negative)
- Aggregation from Q&A pairs to session level
- Outcome affects future filtering logic

## Affected Areas

| File/Module | Type of Change | Description |
|-------------|----------------|-------------|
| `src/api/models.py` | Modify | Add TaxOffice, Region models; extend Project/Session/QAPair |
| `src/api/routes/tax_offices.py` | Create | CRUD endpoints for tax offices |
| `src/api/routes/regions.py` | Create | Region listing and filtering endpoints |
| `src/api/routes/dashboard.py` | Create | Analytics dashboard endpoints |
| `src/api/routes/projects.py` | Modify | Add tax_office_id, region, industry fields |
| `src/api/routes/sessions.py` | Modify | Add tax_office_id, region fields |
| `src/api/routes/qa_pairs.py` | Modify | Add outcome_status, exemplar flag |
| `src/services/tax_office_storage.py` | Create | Tax office MongoDB operations |
| `src/services/industry_classifier.py` | Create | Gemini-based industry classification |
| `src/services/exemplar_service.py` | Create | Exemplar promotion and filtering logic |
| `src/services/analytics_service.py` | Create | Dashboard statistics aggregation |
| `src/services/qa_storage.py` | Modify | Add outcome tracking, exemplar queries |
| `src/services/project_storage.py` | Modify | Add tax office, region, industry fields |
| `src/ingestion/ingest.py` | Modify | Add Gemini classification during ingestion |
| `src/tools.py` | Modify | Add industry, tax office, region filters to search |
| `frontend/src/components/TaxOfficeSelector.tsx` | Create | Tax office search/select component |
| `frontend/src/components/RegionSelector.tsx` | Create | Region dropdown component |
| `frontend/src/components/IndustrySelector.tsx` | Create | Industry multi-select component |
| `frontend/src/components/Dashboard.tsx` | Create | Main dashboard page |
| `frontend/src/components/DashboardCharts.tsx` | Create | Chart visualizations |
| `frontend/src/contexts/DashboardContext.tsx` | Create | Dashboard state management |
| `scripts/import_tax_offices.py` | Create | Script to import Excel tax office data |
| `scripts/seed_industries.py` | Create | Script to seed industry reference data |

## Implementation Approach

### Phase 1: Data Foundation
1. Create MongoDB collections for reference data (tax_offices, regions, industries)
2. Import tax office data from Excel (590 records)
3. Seed industry data (18 categories)
4. Seed region data (16 voivodeships)

### Phase 2: Backend Models & APIs
1. Define Pydantic models for TaxOffice, Region, Industry
2. Create CRUD routes for tax offices
3. Create region listing route
4. Extend Project and Session models with new fields
5. Add outcome_status to QAPair model
6. Create exemplar service with threshold logic

### Phase 3: Industry Classification
1. Integrate Gemini File Search API
2. Implement document upload to Gemini during ingestion
3. Classify industry from document content
4. Delete document from Gemini after classification
5. Store industry in document metadata
6. Add manual override capability

### Phase 4: Search Filtering Enhancement
1. Extend search_knowledge_base with industry filter
2. Add tax_office filter to search
3. Add region filter to search
4. Update hybrid search pipeline for combined filters

### Phase 5: Analytics Dashboard
1. Create analytics aggregation service
2. Implement dashboard API endpoints
3. Build frontend dashboard page
4. Create chart components for distributions

### Phase 6: Frontend Integration
1. Create TaxOfficeSelector component with search
2. Create RegionSelector dropdown
3. Create IndustrySelector multi-select
4. Integrate selectors into ProjectCreator and SessionCreator
5. Build Dashboard page with charts

### Key Changes

1. **Tax Office System**: Complete tax office entity with 590 offices, searchable dropdown, project/session linking
2. **Region System**: 16 voivodeships with dropdown selector, filtering capability
3. **Industry Classification**: Gemini API integration during ingestion, 18 predefined categories, manual override
4. **Exemplar Management**: Threshold-based auto-promotion (confidence >= 0.8, citations >= 2, good rating, good verdict)
5. **Outcome Tracking**: Q&A pair level outcomes aggregating to session level
6. **Analytics Dashboard**: Dedicated page with metrics, distributions, and trends

## Dependencies

- [ ] Gemini API key must be configured in environment variables
- [ ] Excel file with tax office data (provided: `Data structure, Tax office cooperation 1.xlsx`)
- [ ] Industry list image reference (provided: `obraz.png`)
- [ ] Frontend build system must support new chart library (recharts or similar)

## Breaking Changes

None expected - all new fields are optional for backward compatibility with existing data.

## Testing Plan

### Unit Tests
- [ ] Tax office model validation
- [ ] Region model validation
- [ ] Industry classifier with mock Gemini responses
- [ ] Exemplar threshold logic
- [ ] Outcome aggregation logic
- [ ] Dashboard aggregation queries

### Integration Tests
- [ ] Tax office import from Excel
- [ ] Tax office search API
- [ ] Project creation with tax office/region/industry
- [ ] Session creation with geographic scoping
- [ ] Search filtering with all new filters combined
- [ ] Exemplar promotion flow
- [ ] Dashboard statistics accuracy

### Manual Testing
- [ ] Tax office selector search functionality
- [ ] Region dropdown selection
- [ ] Industry multi-select with "Select All"
- [ ] Dashboard charts render correctly
- [ ] Mobile responsiveness of new components
- [ ] End-to-end: create project with all new fields, upload doc, verify classification

## Rollback Plan

1. New collections (tax_offices, regions, industries) can be dropped without affecting existing data
2. New fields on existing collections are optional - old documents still work
3. Gemini integration is isolated in industry_classifier service - can be disabled via feature flag
4. Dashboard is a new route - can be hidden without affecting other functionality

## Success Criteria

- [ ] 590 tax offices imported and searchable
- [ ] 16 regions available for selection
- [ ] 18 industries available for classification
- [ ] Documents automatically classified during ingestion
- [ ] Dashboard shows: project count, session count, success rate, distribution charts
- [ ] Exemplars auto-promoted based on threshold criteria
- [ ] Search filtering works with industry + tax office + region combined
- [ ] All tests pass
- [ ] No regressions in existing functionality

---

## Reference Data

### Industries (18 categories from client)

| Industry (Polish) | English Translation |
|-------------------|---------------------|
| Branża produkcji maszyn | Machinery production |
| Branża IT | IT |
| Branża metalurgiczna | Metallurgical |
| Branża budowlana | Construction |
| Branża spożywcza | Food |
| Branża opakowań i tworzyw sztucznych | Packaging & plastics |
| Branża meblowa | Furniture |
| Branża konstrukcji stalowych | Steel construction |
| Branża tekstylna | Textile |
| Branża kosmetyczna, farmaceutyczna, medyczna | Cosmetic, pharmaceutical, medical |
| Branża chemiczna | Chemical |
| Branża poligraficzna | Printing |
| Branża automotive | Automotive |
| Branża energetyczna | Energy |
| Branża HVAC | HVAC |
| Branża architektoniczna | Architectural |
| Branża biotechnologiczna | Biotechnology |
| Branża recyklingowa | Recycling |
| Branża stoczniowa | Shipyard |

### Regions (16 voivodeships)

| Region (Polish) |
|-----------------|
| dolnośląskie |
| kujawsko-pomorskie |
| lubelskie |
| lubuskie |
| łódzkie |
| małopolskie |
| mazowieckie |
| opolskie |
| podkarpackie |
| podlaskie |
| pomorskie |
| śląskie |
| świętokrzyskie |
| warmińsko-mazurskie |
| wielkopolskie |
| zachodniopomorskie |

### Tax Office Data Structure

| Field | Type | Description |
|-------|------|-------------|
| kodjednostki | int | Unique tax office ID |
| nazwa_urzedu | str | Office name |
| typ | str | Type (IAS/US) |
| wojewodztwo | str | Region (voivodeship) |
| miasto | str | City |
| ulica | str | Street |
| nr_budynku | str | Building number |
| kod_pocztowy | str | Postal code |
| telefon | str | Phone number |
| email | str | Email address |
| adres_bip | str | BIP website URL |

---

## Task List

```json
[
  {
    "id": "CR-MVP-1",
    "category": "setup",
    "description": "Create reference data MongoDB collections and models",
    "steps": [
      "Create TaxOffice Pydantic model in src/api/models.py",
      "Create Region Pydantic model in src/api/models.py",
      "Create Industry Pydantic model in src/api/models.py",
      "Add collection constants to settings.py",
      "Create tax_office_storage.py service with CRUD operations"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-2",
    "category": "setup",
    "description": "Import tax office data from Excel into MongoDB",
    "steps": [
      "Create scripts/import_tax_offices.py script",
      "Read Excel file using pandas",
      "Map columns to TaxOffice model fields",
      "Insert 590 records into tax_offices collection",
      "Add indexes on kodjednostki, nazwa_urzedu, wojewodztwo",
      "Verify import with count check"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-3",
    "category": "setup",
    "description": "Seed industry and region reference data",
    "steps": [
      "Create scripts/seed_reference_data.py script",
      "Define 18 industries with Polish and English names",
      "Define 16 regions (voivodeships)",
      "Insert into industries and regions collections",
      "Add indexes for querying"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-4",
    "category": "feature",
    "description": "Create tax office API routes",
    "steps": [
      "Create src/api/routes/tax_offices.py",
      "GET /api/tax-offices - list with pagination",
      "GET /api/tax-offices/search?q= - search by name/city/id",
      "GET /api/tax-offices/{id} - get by kodjednostki",
      "GET /api/tax-offices/regions - list tax offices grouped by region",
      "Register router in main.py"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-5",
    "category": "feature",
    "description": "Create region API routes",
    "steps": [
      "Create src/api/routes/regions.py",
      "GET /api/regions - list all 16 regions",
      "GET /api/regions/{name}/tax-offices - get tax offices in region",
      "Register router in main.py"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-6",
    "category": "feature",
    "description": "Create industry API routes",
    "steps": [
      "Create src/api/routes/industries.py",
      "GET /api/industries - list all 18 industries",
      "Register router in main.py"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-7",
    "category": "feature",
    "description": "Extend Project model with new fields",
    "steps": [
      "Add tax_office_id: Optional[int] to Project model",
      "Add region: Optional[str] to Project model",
      "Add industry: Optional[str] to Project model",
      "Update ProjectCreateRequest with new optional fields",
      "Update project_storage.py to handle new fields",
      "Update create_project route to accept new fields"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-8",
    "category": "feature",
    "description": "Extend Session model with new fields",
    "steps": [
      "Add tax_office_id: Optional[int] to Session model",
      "Add region: Optional[str] to Session model",
      "Update SessionCreateRequest with new optional fields",
      "Update qa_storage.py to handle new fields",
      "Update create_session route to accept new fields"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-9",
    "category": "feature",
    "description": "Implement Gemini industry classification service",
    "steps": [
      "Add GEMINI_API_KEY to settings.py",
      "Create src/services/industry_classifier.py",
      "Implement upload_to_gemini() function",
      "Implement classify_industry() using Gemini File Search",
      "Implement delete_from_gemini() cleanup function",
      "Add classification prompt with 18 industry options",
      "Handle classification errors gracefully"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-10",
    "category": "feature",
    "description": "Integrate industry classification into ingestion pipeline",
    "steps": [
      "Import industry_classifier in ingest.py",
      "After document conversion, upload to Gemini",
      "Call classify_industry() to get classification",
      "Delete document from Gemini after classification",
      "Store industry in document metadata",
      "Add --skip-classification flag for manual override",
      "Handle Gemini API rate limits with retry"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-11",
    "category": "feature",
    "description": "Add outcome_status to QAPair model",
    "steps": [
      "Add outcome_status: Optional[str] field (successful/partial/negative)",
      "Add outcome field validator for allowed values",
      "Create PUT /api/qa-pairs/{id}/outcome endpoint",
      "Update qa_storage.py with set_outcome() method"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-12",
    "category": "feature",
    "description": "Implement exemplar service with threshold logic",
    "steps": [
      "Create src/services/exemplar_service.py",
      "Define exemplar threshold criteria (confidence >= 0.8, citations >= 2, good rating, good verdict)",
      "Implement check_exemplar_eligibility() function",
      "Implement promote_to_exemplar() function",
      "Add is_exemplar: bool field to QAPair model",
      "Create auto-promotion trigger when QA pair is rated good"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-13",
    "category": "feature",
    "description": "Extend search filtering with industry, tax office, region",
    "steps": [
      "Add industry: Optional[str] parameter to search_knowledge_base()",
      "Add tax_office_id: Optional[int] parameter to search_knowledge_base()",
      "Add region: Optional[str] parameter to search_knowledge_base()",
      "Update MongoDB aggregation pipeline with $match filters",
      "Update hybrid search to include new filters",
      "Test combined filtering (industry + tax office + region)"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-14",
    "category": "feature",
    "description": "Create analytics service",
    "steps": [
      "Create src/services/analytics_service.py",
      "Implement get_project_count() aggregation",
      "Implement get_session_count() aggregation",
      "Implement get_success_rate() calculation",
      "Implement get_distribution_by_region() aggregation",
      "Implement get_distribution_by_industry() aggregation",
      "Implement get_distribution_by_tax_office() aggregation",
      "Implement get_qa_quality_metrics() (good/bad ratios)",
      "Implement get_trends_over_time() with date grouping"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-15",
    "category": "feature",
    "description": "Create dashboard API routes",
    "steps": [
      "Create src/api/routes/dashboard.py",
      "GET /api/dashboard/summary - overall statistics",
      "GET /api/dashboard/distribution/region - regional breakdown",
      "GET /api/dashboard/distribution/industry - industry breakdown",
      "GET /api/dashboard/distribution/tax-office - tax office breakdown",
      "GET /api/dashboard/trends - time-based trends",
      "GET /api/dashboard/quality - Q&A quality metrics",
      "Register router in main.py"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-16",
    "category": "frontend",
    "description": "Create TaxOfficeSelector component",
    "steps": [
      "Create frontend/src/components/TaxOfficeSelector.tsx",
      "Implement search input with debounce",
      "Call /api/tax-offices/search API",
      "Display results in dropdown list",
      "Show selected tax office details",
      "Handle loading and error states"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-17",
    "category": "frontend",
    "description": "Create RegionSelector component",
    "steps": [
      "Create frontend/src/components/RegionSelector.tsx",
      "Fetch regions from /api/regions",
      "Display as dropdown select",
      "Handle selection change callback"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-18",
    "category": "frontend",
    "description": "Create IndustrySelector component",
    "steps": [
      "Create frontend/src/components/IndustrySelector.tsx",
      "Fetch industries from /api/industries",
      "Display as multi-select with checkboxes",
      "Add 'Select All' option",
      "Handle selection change callback"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-19",
    "category": "frontend",
    "description": "Integrate new selectors into ProjectCreator",
    "steps": [
      "Import TaxOfficeSelector, RegionSelector, IndustrySelector",
      "Add selectors to project creation form",
      "Update form state to include new fields",
      "Pass new fields to create project API call"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-20",
    "category": "frontend",
    "description": "Integrate new selectors into SessionCreator",
    "steps": [
      "Import TaxOfficeSelector, RegionSelector",
      "Add selectors to session creation form",
      "Update form state to include new fields",
      "Pass new fields to create session API call"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-21",
    "category": "frontend",
    "description": "Create Dashboard page",
    "steps": [
      "Create frontend/src/pages/Dashboard.tsx",
      "Create frontend/src/contexts/DashboardContext.tsx",
      "Add /dashboard route to App.tsx",
      "Create dashboard layout with summary cards",
      "Display key metrics (projects, sessions, success rate)"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-22",
    "category": "frontend",
    "description": "Create Dashboard chart components",
    "steps": [
      "Install recharts or chart.js library",
      "Create frontend/src/components/DashboardCharts.tsx",
      "Create RegionDistributionChart component",
      "Create IndustryDistributionChart component",
      "Create TrendsChart component (line chart)",
      "Create QualityMetricsChart component (pie/bar)"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-23",
    "category": "testing",
    "description": "Write unit tests for new services",
    "steps": [
      "Create test_scripts/test_tax_office_storage.py",
      "Create test_scripts/test_industry_classifier.py (with mocks)",
      "Create test_scripts/test_exemplar_service.py",
      "Create test_scripts/test_analytics_service.py",
      "Ensure all threshold logic is covered"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-24",
    "category": "testing",
    "description": "Write integration tests for new APIs",
    "steps": [
      "Create test_scripts/test_tax_office_api.py",
      "Create test_scripts/test_dashboard_api.py",
      "Test search filtering with combined filters",
      "Test exemplar promotion flow end-to-end"
    ],
    "passes": true
  },
  {
    "id": "CR-MVP-25",
    "category": "documentation",
    "description": "Update API documentation",
    "steps": [
      "Document new endpoints in API docs",
      "Update README with new features",
      "Add configuration instructions for Gemini API key"
    ],
    "passes": true
  }
]
```

---

## Implementation Notes

### Gemini API Usage
- Use `google.generativeai` library for Gemini integration
- File Search API: Upload document, create query, delete document
- Important: Always delete uploaded files after classification to avoid storage costs
- Handle rate limits with exponential backoff

### MongoDB Aggregation for Analytics
- Use `$facet` for computing multiple metrics in single query
- Use `$group` with `$dateToString` for time-based trends
- Create indexes on frequently queried fields (region, industry, tax_office_id)

### Exemplar Threshold Logic
```python
def check_exemplar_eligibility(qa_pair: QAPair) -> bool:
    return (
        qa_pair.rating_good == True and
        qa_pair.review and qa_pair.review.get("verdict") == "good" and
        qa_pair.review.get("confidence", 0) >= 0.8 and
        len(qa_pair.citations or []) >= 2
    )
```

### Search Filter Combination
- Filters are additive (AND logic)
- Empty/None filter values are ignored
- "Select All" for industry = no industry filter applied

## References

- [Gemini File Search API Documentation](https://ai.google.dev/gemini-api/docs/file-search)
- Client-provided Excel: `Data structure, Tax office cooperation 1.xlsx`
- Client-provided image: `obraz.png` (industry list)
- Meeting notes from client discussion
