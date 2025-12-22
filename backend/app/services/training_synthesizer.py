from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Dict, Any
from ..models import models, knowledge as k_models
from . import llm

def generate_hyper_guide(flow_id: int, db: Session) -> Dict[str, Any]:
    """
    Fuses ProcessFlow with BusinessRules to create a Hyper-Focused Training Guide.
    """
    
    # 1. Fetch Flow
    flow = db.query(models.ProcessFlow).filter(models.ProcessFlow.id == flow_id).first()
    if not flow:
        return {"error": "Flow not found"}
        
    # 2. Fetch All Valid Rules (For now, fetch all active rules from DB)
    # In a huge system, we would do Vector Search per step.
    # For now (Stage 1), we fetch all rules and let LLM pick/apply them (Context Window permitting).
    # Or better: We specifically look for rules linked to Documents that match keywords?
    # Let's try "All Active Rules" strategy first (assuming < 50 rules globally for this demo).
    all_rules = db.query(k_models.BusinessRule).filter(k_models.BusinessRule.is_active == True).all()
    rule_texts = [f"[{r.rule_type}] {r.trigger_context}: {r.rule_description}" for r in all_rules]
    
    guide_steps = []
    
    # 3. Synthesize Each Step
    # We ignore steps that are just "Silence" or "Unknown" if desired, but refine_step usually handles them.
    sorted_steps = sorted(flow.steps, key=lambda s: s.step_number)
    
    for step in sorted_steps:
        # Skip purely silent snippets if they have no action?
        # For now, process all.
        
        # Call LLM Fusion
        # We pass *all* rules. LLM identifies which apply to this specific "Raw Step".
        fusion_result = llm.refine_instruction_with_rules(
            raw_text=step.action_details or "No details", 
            rules=rule_texts
        )
        
        guide_steps.append({
            "step_number": step.step_number,
            "original_timestamp": step.start_ts,
            "video_clip": step.video_clip_path,
            "instruction": fusion_result.get("refined_action", step.action_details),
            "warnings": fusion_result.get("compliance_warnings", []),
            "criticality": fusion_result.get("criticality", "LOW"),
            "screenshot": step.screenshot_path
        })
        
    # 4. Construct Final Artifact
    return {
        "title": f"Hyper-Guide: {flow.title}",
        "total_steps": len(guide_steps),
        "estimated_time": f"{sum(s.duration for s in sorted_steps if s.duration)/60:.1f} mins",
        "modules": guide_steps
    }
