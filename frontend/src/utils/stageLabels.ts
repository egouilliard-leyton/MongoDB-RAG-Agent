// Stage label mapping based on backend project_stages.py STAGES dictionary
export const STAGE_LABELS: Record<string, string> = {
  prep_docs: 'Prepare documents',
  submit_first_instance: 'Submit (1st instance)',
  await_response: 'Await response',
  inquiry_check: 'Inquiry check',
  prepare_answers: 'Prepare answers',
  first_instance_outcome: '1st instance outcome',
  appeal_second_instance: 'Appeal (2nd instance)',
  second_instance_decision: '2nd instance decision',
  complaint_wsa: 'Complaint to WSA',
  wsa_decision: 'WSA decision',
  complaint_nsa: 'Complaint to NSA',
  nsa_decision: 'NSA decision',
  end_refund: 'End: refund',
  end_no_appeal: 'End: no appeal',
  return_reconsideration: 'Return for reconsideration',
};

export const getStageLabel = (stageKey: string | undefined | null): string => {
  if (!stageKey) return 'Unknown stage';
  return STAGE_LABELS[stageKey] || stageKey;
};

