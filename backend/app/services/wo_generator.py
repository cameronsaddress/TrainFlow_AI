from typing import List, Dict, Any
from ..models import models

def generate_wo_guide_data(flow: models.ProcessFlow) -> Dict[str, Any]:
    """
    Analyzes a linear ProcessFlow to generate a Cross-System Work Order Creation Guide.
    
    Output Structure:
    {
        "title": str,
        "systems_involved": [str],
        "system_handoffs": [
            {"from": "ERP", "to": "GIS", "step": 5, "reason": "Asset Lookup"}
        ],
        "field_mapping_matrix": [
            {"system": "ERP", "field": "WO Description", "value_source": "User Input", "step": 1},
            {"system": "GIS", "field": "Asset ID", "value_source": "From ERP Step 1", "step": 6}
        ],
        "estimated_sla": "30 mins"
    }
    """
    
    guide = {
        "title": f"WO Creation Guide: {flow.title}",
        "systems_involved": set(),
        "system_handoffs": [],
        "field_mapping_matrix": [],
        "total_steps": len(flow.steps)
    }
    
    sorted_steps = sorted(flow.steps, key=lambda s: s.step_number)
    current_system = None
    
    for i, step in enumerate(sorted_steps):
        sys_name = step.system_name or "Unknown"
        guide["systems_involved"].add(sys_name)
        
        # 1. Detect Handoffs
        if current_system and sys_name != current_system:
            guide["system_handoffs"].append({
                "from": current_system,
                "to": sys_name,
                "step": step.step_number,
                "action": step.action_details
            })
        current_system = sys_name
        
        # 2. Extract Fields (Heuristic: Look for 'Enter', 'Select', 'Type' in action)
        action_lower = step.action_details.lower()
        if any(verb in action_lower for verb in ["enter", "type", "select", "choose", "input"]):
            # Heuristic field extraction: "Enter 'Leak Repair' in 'Description' field"
            # In a real app, we'd use LLM extraction, but here we do basic heuristics or assume 'notes' has it.
            field_name = "Unknown Field"
            if " in " in step.action_details:
                parts = step.action_details.split(" in ")
                if len(parts) > 1:
                    field_name = parts[1].strip('.').strip("'").strip('"')
            
            guide["field_mapping_matrix"].append({
                "step": step.step_number,
                "system": sys_name,
                "field": field_name,
                "action": step.action_details,
                "validation": step.notes or "None"
            })

    guide["systems_involved"] = list(guide["systems_involved"])
    return guide
