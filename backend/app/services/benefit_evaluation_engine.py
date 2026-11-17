from typing import Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, select
from app.models.tables import BenefitConcept, CompanyBenefitCondition, CompanyBenefitProfile

MAX_TITLE_LENGTH: int = 50
MAX_DESCRIPTION_LENGTH: int = 120

class EvaluatedBenefit(BaseModel):
    concept_id: str
    display_title: str
    display_description: str
    display_value: Optional[str] = None
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
        plan_name: str,
        preloaded_conditions: Optional[List[CompanyBenefitCondition]] = None,
    ) -> List[EvaluatedBenefit]:
        """
        Takes a list of base benefits and applies the company's condition rules
        (matching the specific plan) to output the final evaluated list of benefits.
        Enforces strict character length bounds to guarantee constant card layout without overflow.
        """
        if preloaded_conditions is not None:
            conditions = list(preloaded_conditions)
        else:
            # Load all active conditions for this company (active profile + global profile_id IS NULL)
            query = select(CompanyBenefitCondition).where(
                CompanyBenefitCondition.company_id == company_id,
                CompanyBenefitCondition.is_active == True,
            )
            if profile_id:
                query = query.where(
                    or_(
                        CompanyBenefitCondition.profile_id == profile_id,
                        CompanyBenefitCondition.profile_id.is_(None),
                    )
                )
            else:
                active_prof_ids = []
                if hasattr(db, "execute"):
                    res = db.execute(
                        select(CompanyBenefitProfile.id).where(
                            CompanyBenefitProfile.is_active == True,
                        )
                    )
                    if hasattr(res, "scalars"):
                        active_prof_ids = list(res.scalars().all())
                elif hasattr(db, "scalars"):
                    active_prof_ids = list(
                        db.scalars(
                            select(CompanyBenefitProfile.id).where(
                                CompanyBenefitProfile.is_active == True,
                            )
                        ).all()
                    )
                if active_prof_ids:
                    query = query.where(
                        or_(
                            CompanyBenefitCondition.profile_id.in_(active_prof_ids),
                            CompanyBenefitCondition.profile_id.is_(None),
                        )
                    )
                else:
                    query = query.where(CompanyBenefitCondition.profile_id.is_(None))

            if hasattr(db, "execute"):
                res = db.execute(query)
                conditions = list(res.scalars().all() if hasattr(res, "scalars") else res.fetchall())
            elif hasattr(db, "scalars"):
                conditions = list(db.scalars(query).all())
            else:
                conditions = []

        if not conditions:
            for b in base_benefits:
                if b.display_title and len(b.display_title) > MAX_TITLE_LENGTH:
                    b.display_title = b.display_title[:MAX_TITLE_LENGTH].strip()
                if b.display_description and len(b.display_description) > MAX_DESCRIPTION_LENGTH:
                    b.display_description = b.display_description[:MAX_DESCRIPTION_LENGTH].strip()
            return base_benefits

        # Map concept UUIDs <-> concept_keys (and canonical aliases like towing / special_perils / llp)
        concept_id_to_key: Dict[str, str] = {}
        concept_key_to_id: Dict[str, str] = {}
        try:
            for c_row in db.scalars(select(BenefitConcept)).all():
                cid = str(c_row.id)
                ckey = str(c_row.concept_key or "")
                concept_id_to_key[cid] = ckey
                if ckey:
                    concept_key_to_id[ckey] = cid
        except Exception:
            pass

        def _aliases_for(cid_or_key: str) -> set[str]:
            out = {cid_or_key}
            if cid_or_key in concept_id_to_key:
                ck = concept_id_to_key[cid_or_key]
                out.add(ck)
                out.add(ck.replace("-", "_"))
            if cid_or_key in concept_key_to_id:
                out.add(concept_key_to_id[cid_or_key])
            low = cid_or_key.lower()
            if "towing" in low or concept_id_to_key.get(cid_or_key, "") in ("towing", "emergency-towing", "towing-assistance"):
                out.update({"towing", "emergency-towing", "towing-assistance"})
            if "special_perils" in low or "special-perils" in low or concept_id_to_key.get(cid_or_key, "") == "special-perils":
                out.update({"special_perils", "special-perils"})
            if low in ("llp", "legal-liability-to-passengers") or concept_id_to_key.get(cid_or_key, "") == "legal-liability-to-passengers":
                out.update({"llp", "legal-liability-to-passengers"})
            return out

        active_concepts: set[str] = set()
        for b in base_benefits:
            if not b.is_hidden:
                active_concepts.update(_aliases_for(b.concept_id))

        # Sort wildcard rules first so specific trigger_plan_filter rules (e.g. 'Plan 4') win
        conditions.sort(
            key=lambda c: (1 if (c.trigger_plan_filter and str(c.trigger_plan_filter).strip()) else 0)
        )

        # We need a mutable list of evaluated benefits
        evaluated_dict: Dict[str, EvaluatedBenefit] = {b.concept_id: b.model_copy() for b in base_benefits}

        for condition in conditions:
            # 1. Check if trigger concept is in the active benefits
            if not (_aliases_for(condition.trigger_concept_id) & active_concepts):
                continue

            # 2. Check if plan filter matches (if one exists)
            if condition.trigger_plan_filter and str(condition.trigger_plan_filter).strip():
                filter_term = str(condition.trigger_plan_filter).strip().lower()
                haystack = f"{plan_name} {' '.join(f'{b.display_title} {b.display_description}' for b in base_benefits)}".lower()
                if filter_term not in haystack and filter_term.replace("-", " ") not in haystack.replace("-", " "):
                    continue

            # 3. Apply the action to the target concept (matching by direct key or concept alias)
            target_aliases = _aliases_for(condition.target_concept_id)
            matched_keys = [k for k in evaluated_dict.keys() if k in target_aliases or (_aliases_for(k) & target_aliases)]
            for t_key in matched_keys:
                target_benefit = evaluated_dict[t_key]
                
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
                    replacement_value = getattr(condition, "replacement_value", None)
                    if replacement_value:
                        target_benefit.display_value = str(replacement_value)[:120].strip()
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
