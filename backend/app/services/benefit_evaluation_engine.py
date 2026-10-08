from typing import Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.tables import CompanyBenefitCondition

MAX_TITLE_LENGTH: int = 50
MAX_DESCRIPTION_LENGTH: int = 120

class EvaluatedBenefit(BaseModel):
    concept_id: str
    display_title: str
    display_description: str
    is_hidden: bool = False
    is_modified: bool = False
    source_condition_id: Optional[str] = None
    trigger_plan_filter_matched: Optional[str] = None

class BenefitEvaluationEngine:
    @staticmethod
    def evaluate_benefits_for_plan(
        db: Session,
        company_id: str,
        profile_id: Optional[str],
        base_benefits: List[EvaluatedBenefit],
        plan_name: str
    ) -> List[EvaluatedBenefit]:
        """
        Takes a list of base benefits and applies the company's condition rules
        (matching the specific plan) to output the final evaluated list of benefits.
        Enforces strict character length bounds to guarantee constant card layout without overflow.
        """
        # Load all active conditions for this company/profile
        query = select(CompanyBenefitCondition).where(
            CompanyBenefitCondition.company_id == company_id,
            CompanyBenefitCondition.is_active == True
        )
        if profile_id:
            query = query.where(CompanyBenefitCondition.profile_id == profile_id)
        else:
            query = query.where(CompanyBenefitCondition.profile_id.is_(None))
            
        conditions = db.execute(query).scalars().all()

        if not conditions:
            for b in base_benefits:
                if b.display_title and len(b.display_title) > MAX_TITLE_LENGTH:
                    b.display_title = b.display_title[:MAX_TITLE_LENGTH].strip()
                if b.display_description and len(b.display_description) > MAX_DESCRIPTION_LENGTH:
                    b.display_description = b.display_description[:MAX_DESCRIPTION_LENGTH].strip()
            return base_benefits

        # Create a lookup for fast access to current active benefits
        active_concepts = {b.concept_id for b in base_benefits if not b.is_hidden}
        
        # We need a mutable list of evaluated benefits
        evaluated_dict: Dict[str, EvaluatedBenefit] = {b.concept_id: b.model_copy() for b in base_benefits}

        for condition in conditions:
            # 1. Check if trigger concept is in the active benefits
            if condition.trigger_concept_id not in active_concepts:
                continue
                
            # 2. Check if plan filter matches (if one exists)
            if condition.trigger_plan_filter:
                filter_term = condition.trigger_plan_filter.lower()
                if filter_term not in plan_name.lower():
                    continue

            # 3. Apply the action to the target concept (if the target concept exists in the plan)
            if condition.target_concept_id in evaluated_dict:
                target_benefit = evaluated_dict[condition.target_concept_id]
                
                if condition.action_type == "hide_target":
                    target_benefit.is_hidden = True
                    target_benefit.is_modified = True
                    target_benefit.source_condition_id = condition.id
                    target_benefit.trigger_plan_filter_matched = condition.trigger_plan_filter
                elif condition.action_type == "replace_description":
                    if condition.replacement_description:
                        target_benefit.display_description = condition.replacement_description[:MAX_DESCRIPTION_LENGTH].strip()
                        target_benefit.is_modified = True
                        target_benefit.source_condition_id = condition.id
                        target_benefit.trigger_plan_filter_matched = condition.trigger_plan_filter
                    # Using getattr in case we are in an environment without the DB migration yet during test
                    replacement_title = getattr(condition, "replacement_title", None)
                    if replacement_title:
                        target_benefit.display_title = str(replacement_title)[:MAX_TITLE_LENGTH].strip()
                        target_benefit.is_modified = True
                        target_benefit.source_condition_id = condition.id
                        target_benefit.trigger_plan_filter_matched = condition.trigger_plan_filter

        # Enforce character bounds across all evaluated items
        for b in evaluated_dict.values():
            if b.display_title and len(b.display_title) > MAX_TITLE_LENGTH:
                b.display_title = b.display_title[:MAX_TITLE_LENGTH].strip()
            if b.display_description and len(b.display_description) > MAX_DESCRIPTION_LENGTH:
                b.display_description = b.display_description[:MAX_DESCRIPTION_LENGTH].strip()
                        
        return list(evaluated_dict.values())
