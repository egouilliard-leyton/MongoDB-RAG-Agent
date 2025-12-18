"""Validation helper functions for API."""

import logging
from typing import Optional
from bson import ObjectId
from bson.errors import InvalidId

from src.api.exceptions import ValidationError

logger = logging.getLogger(__name__)


def validate_object_id(id_value: str, resource_name: str = "Resource") -> str:
    """
    Validate that a string is a valid MongoDB ObjectId.
    
    Args:
        id_value: String to validate
        resource_name: Name of the resource (for error messages)
    
    Returns:
        Validated ObjectId string
    
    Raises:
        ValidationError: If ID is invalid
    """
    if not id_value:
        raise ValidationError(f"{resource_name} ID is required")
    
    try:
        ObjectId(id_value)
        return id_value
    except (InvalidId, TypeError):
        raise ValidationError(f"Invalid {resource_name} ID format: {id_value}")


def validate_user_role(user_role: str) -> str:
    """
    Validate that user_role is "junior" or "senior".
    
    Args:
        user_role: User role to validate
    
    Returns:
        Validated user role string
    
    Raises:
        ValidationError: If user_role is invalid
    """
    if not user_role:
        raise ValidationError("User role is required")
    
    user_role_lower = user_role.lower().strip()
    if user_role_lower not in ("junior", "senior"):
        raise ValidationError(
            f"Invalid user role: {user_role}. Must be 'junior' or 'senior'"
        )
    
    return user_role_lower


def validate_outcome_status(outcome_status: Optional[str]) -> Optional[str]:
    """
    Validate that outcome_status is "successful", "unsuccessful", or None.
    
    Args:
        outcome_status: Outcome status to validate
    
    Returns:
        Validated outcome status string or None
    
    Raises:
        ValidationError: If outcome_status is invalid
    """
    if outcome_status is None:
        return None
    
    outcome_status_lower = outcome_status.lower().strip()
    if outcome_status_lower not in ("successful", "unsuccessful"):
        raise ValidationError(
            f"Invalid outcome status: {outcome_status}. "
            f"Must be 'successful', 'unsuccessful', or None"
        )
    
    return outcome_status_lower


def validate_determined_by(determined_by: str) -> str:
    """
    Validate that determined_by is "user" or "auto".
    
    Args:
        determined_by: Determined by value to validate
    
    Returns:
        Validated determined_by string
    
    Raises:
        ValidationError: If determined_by is invalid
    """
    if not determined_by:
        raise ValidationError("determined_by is required")
    
    determined_by_lower = determined_by.lower().strip()
    if determined_by_lower not in ("user", "auto"):
        raise ValidationError(
            f"Invalid determined_by: {determined_by}. Must be 'user' or 'auto'"
        )
    
    return determined_by_lower


def validate_questions_list(questions: list, max_questions: int = 100) -> list:
    """
    Validate a list of questions.
    
    Args:
        questions: List of question strings
        max_questions: Maximum number of questions allowed
    
    Returns:
        Validated list of questions
    
    Raises:
        ValidationError: If questions list is invalid
    """
    if not questions:
        raise ValidationError("Questions list cannot be empty")
    
    if not isinstance(questions, list):
        raise ValidationError("Questions must be a list")
    
    if len(questions) > max_questions:
        raise ValidationError(
            f"Too many questions: {len(questions)}. Maximum allowed: {max_questions}"
        )
    
    validated_questions = []
    for i, question in enumerate(questions):
        if not isinstance(question, str):
            raise ValidationError(f"Question at index {i} must be a string")
        
        question = question.strip()
        if not question:
            raise ValidationError(f"Question at index {i} cannot be empty")
        
        if len(question) > 10000:  # Reasonable max length
            raise ValidationError(
                f"Question at index {i} is too long (max 10000 characters)"
            )
        
        validated_questions.append(question)
    
    return validated_questions

