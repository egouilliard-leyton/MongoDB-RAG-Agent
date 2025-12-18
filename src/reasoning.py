"""Reasoning helpers for multi-step agentic RAG."""

import logging
from typing import List, Dict, Any, Optional
from src.providers import get_llm_model
from src.settings import load_settings
from src.tools import SearchResult
from pydantic_ai import Agent
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Create a simple agent for question analysis
_analysis_agent = Agent(
    get_llm_model(),
    system_prompt="You are a question analysis assistant. Analyze questions to determine complexity and decomposition needs."
)


class QuestionAnalysis(BaseModel):
    """Analysis result for a question."""
    is_complex: bool
    sub_questions: List[str]
    reasoning: str


async def analyze_question_complexity(question: str) -> QuestionAnalysis:
    """
    Analyze a question to determine if it should be decomposed.
    
    Uses heuristics and LLM analysis to detect:
    - Multiple topics (AND/OR conjunctions)
    - Comparison questions
    - Multi-aspect questions
    
    Args:
        question: The user's question
        
    Returns:
        QuestionAnalysis with complexity assessment
    """
    # Heuristic checks
    complex_indicators = [
        ' and ', ' or ', ' vs ', ' versus ', ' compared to ',
        ' both ', ' either ', ' neither ', ' as well as ',
        ' benefits and drawbacks', ' pros and cons',
        ' advantages and disadvantages'
    ]
    
    has_indicators = any(indicator in question.lower() for indicator in complex_indicators)
    
    # Count question marks and topics
    question_count = question.count('?')
    has_multiple_topics = question_count > 1 or has_indicators
    
    # Use LLM for nuanced analysis
    try:
        analysis_prompt = f"""Analyze this question and determine if it should be broken down into sub-questions:

Question: "{question}"

Consider:
1. Does it ask about multiple distinct topics or aspects?
2. Does it require comparing or contrasting different things?
3. Would breaking it down improve search coverage?

Respond in JSON format:
{{
    "is_complex": true/false,
    "sub_questions": ["sub-question 1", "sub-question 2", ...],
    "reasoning": "brief explanation"
}}

If not complex, sub_questions should be empty or contain just the original question."""
        
        result = await _analysis_agent.run(analysis_prompt)
        response_text = str(result.data)
        
        # Try to extract JSON from response
        import json
        import re
        
        # Look for JSON block
        json_match = re.search(r'\{[^{}]*"is_complex"[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return QuestionAnalysis(
                    is_complex=data.get('is_complex', has_multiple_topics),
                    sub_questions=data.get('sub_questions', []),
                    reasoning=data.get('reasoning', '')
                )
            except json.JSONDecodeError:
                pass
        
        # Fallback: use heuristics
        if has_multiple_topics:
            # Simple decomposition based on conjunctions
            sub_questions = []
            if ' and ' in question.lower():
                parts = question.split(' and ', 1)
                if len(parts) == 2:
                    sub_questions = [parts[0].strip(), parts[1].strip()]
            elif ' vs ' in question.lower() or ' versus ' in question.lower():
                parts = re.split(r'\s+vs\.?\s+|\s+versus\s+', question, flags=re.IGNORECASE)
                if len(parts) == 2:
                    sub_questions = [f"information about {parts[0].strip()}", 
                                   f"information about {parts[1].strip()}"]
            
            return QuestionAnalysis(
                is_complex=True,
                sub_questions=sub_questions if sub_questions else [question],
                reasoning="Detected multiple topics or comparison"
            )
        
    except Exception as e:
        logger.warning(f"Error in LLM analysis: {e}, using heuristics")
    
    # Default: not complex
    return QuestionAnalysis(
        is_complex=has_multiple_topics,
        sub_questions=[question] if has_multiple_topics else [],
        reasoning="Heuristic analysis"
    )


def should_decompose(question: str, settings: Optional[Any] = None) -> bool:
    """
    Quick heuristic check if question should be decomposed.
    
    Args:
        question: The user's question
        settings: Optional settings object
        
    Returns:
        True if question likely needs decomposition
    """
    if settings and not settings.enable_question_decomposition:
        return False
    
    complex_indicators = [
        ' and ', ' or ', ' vs ', ' versus ', ' compared to ',
        ' both ', ' either ', ' neither ', ' as well as ',
        ' benefits and drawbacks', ' pros and cons',
        ' advantages and disadvantages'
    ]
    
    return any(indicator in question.lower() for indicator in complex_indicators)


def merge_search_results(all_results: List[List[SearchResult]]) -> List[SearchResult]:
    """
    Merge multiple search result lists, deduplicating by chunk_id.
    
    Args:
        all_results: List of search result lists from different queries
        
    Returns:
        Merged and deduplicated list of results
    """
    seen_chunks = {}
    
    for result_list in all_results:
        for result in result_list:
            if result.chunk_id not in seen_chunks:
                seen_chunks[result.chunk_id] = result
            else:
                # Keep the one with higher similarity score
                if result.similarity > seen_chunks[result.chunk_id].similarity:
                    seen_chunks[result.chunk_id] = result
    
    # Sort by similarity descending
    merged = list(seen_chunks.values())
    merged.sort(key=lambda x: x.similarity, reverse=True)
    
    return merged


def evaluate_results_sufficiency(
    query: str,
    results: List[SearchResult],
    min_results: int = 3
) -> tuple:
    """
    Evaluate if search results are sufficient to answer the query.
    
    Args:
        query: Original query
        results: Search results
        min_results: Minimum number of results needed
        
    Returns:
        Tuple of (is_sufficient, reason)
    """
    if len(results) == 0:
        return False, "No results found"
    
    if len(results) < min_results:
        return False, f"Only {len(results)} results found, may need more"
    
    # Check relevance scores
    high_relevance = sum(1 for r in results if r.similarity > 0.7)
    if high_relevance == 0:
        return False, "No highly relevant results (similarity > 0.7)"
    
    return True, f"Found {len(results)} results with {high_relevance} highly relevant"

