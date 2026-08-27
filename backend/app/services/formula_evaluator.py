import ast
import operator
from typing import Dict, Any, Union

from app.extraction.windscreen_scraper import WindscreenScraper

SYMBOLIC_TOKENS = {
    "statutory_unlimited": "Statutory Unlimited",
    "statutory_limit": "Statutory Limit",
    "100%_waiver": "100% Waiver",
    "100_percent_waiver": "100% Waiver",
    "unlimited": "Unlimited",
    "rebate_percentage": "Up to 30% Rebate",
    "tariff_betterment_scale": "Scale (0% - 40%)"
}

def evaluate_cart_tariff(rate: float, days: float) -> float:
    # Example logic for CART tariff matrix
    return rate * days

def _safe_eval(node, context):
    bin_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Pow: operator.pow,
    }
    un_ops = {
        ast.USub: operator.neg,
    }
    
    if isinstance(node, ast.Constant): # python 3.8+
        return node.value
    elif isinstance(node, ast.Name):
        if node.id in context:
            return context[node.id]
        raise ValueError(f"Unknown variable: {node.id}")
    elif isinstance(node, ast.BinOp):
        left = _safe_eval(node.left, context)
        right = _safe_eval(node.right, context)
        op_type = type(node.op)
        if op_type in bin_ops:
            return bin_ops[op_type](left, right)  # type: ignore
        raise ValueError(f"Unsupported binary operator: {op_type}")
    elif isinstance(node, ast.UnaryOp):
        operand = _safe_eval(node.operand, context)
        op_type = type(node.op)
        if op_type in un_ops:
            return un_ops[op_type](operand)  # type: ignore
        raise ValueError(f"Unsupported unary operator: {op_type}")
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            args = [_safe_eval(arg, context) for arg in node.args]
            if func_name == "min":
                return min(*args)
            elif func_name == "max":
                return max(*args)
            elif func_name == "round":
                return round(*args)
            elif func_name == "evaluate_cart_tariff":
                if len(args) == 2:
                    return evaluate_cart_tariff(args[0], args[1])
                raise ValueError("evaluate_cart_tariff takes 2 arguments: rate, days")
        raise ValueError(f"Unsupported function call in expression")
    else:
        raise ValueError(f"Unsupported AST node type: {type(node)}")

def extract_evaluation_context(draft: Dict[str, Any], extras_list: list | None = None) -> Dict[str, float]:
    """
    Extract relevant variables for mathematical evaluation from a draft/quotation dictionary.
    """
    if extras_list is None:
        extras_list = []
    
    context = {}
    
    # 1. vehicle_sum_insured
    sum_insured_keys = ["vehicle_sum_insured", "sum_insured", "market_value", "agreed_value", "coverage_amount"]
    vsi = 0.0
    for key in sum_insured_keys:
        if key in draft and draft[key] is not None:
            try:
                value_str = draft[key]
                if not isinstance(value_str, str):
                    value_str = str(value_str)
                clean_str = value_str.replace(",", "").replace("RM", "").strip()
                vsi = float(clean_str)
                break
            except ValueError:
                continue
    context["vehicle_sum_insured"] = vsi
    
    # 2. total_seats
    seats = draft.get("total_seats") or draft.get("seating_capacity")
    if seats is not None:
        try:
            context["total_seats"] = float(seats)
        except ValueError:
            context["total_seats"] = 5.0
    else:
        context["total_seats"] = 5.0 # default for private car
        
    # 3. base_tp_premium
    base_tp = draft.get("base_tp_premium") or draft.get("basic_premium")
    if base_tp is not None:
        try:
            context["base_tp_premium"] = float(str(base_tp).replace(",", "").replace("RM", "").strip())
        except ValueError:
            context["base_tp_premium"] = 150.0
    else:
        context["base_tp_premium"] = 150.0
        
    # 4. windscreen_sum_insured
    wsi = draft.get("windscreen_sum_insured")
    
    if wsi is None and extras_list:
        for ex in extras_list:
            if ex.get("concept_key") == "windscreen" and ex.get("coverage_limit"):
                try:
                    wsi = float(str(ex.get("coverage_limit")).replace(",", "").replace("RM", "").strip())
                except ValueError:
                    pass
                break
                
    if wsi is not None:
        try:
            context["windscreen_sum_insured"] = float(str(wsi).replace(",", "").replace("RM", "").strip())
        except ValueError:
            context["windscreen_sum_insured"] = 1000.0
    else:
        # Fallback to scraping if vehicle model is present
        car_model = draft.get("vehicle_model") or draft.get("make_model") or draft.get("vehicle_make_model")
        if car_model and isinstance(car_model, str):
            scraper = WindscreenScraper()
            result = scraper.get_windscreen_pricing(car_model)
            if result and 'sum_insured' in result:
                context["windscreen_sum_insured"] = result['sum_insured']
            else:
                context["windscreen_sum_insured"] = 1000.0
        else:
            context["windscreen_sum_insured"] = 1000.0
        
    # 5. accessories_sum_insured, boom_sum_insured, vehicle_age, period_months
    for key in ["accessories_sum_insured", "boom_sum_insured", "vehicle_age"]:
        val = draft.get(key)
        if val is not None:
            try:
                context[key] = float(str(val).replace(",", "").replace("RM", "").strip())
            except ValueError:
                context[key] = 0.0
        else:
            context[key] = 0.0
            
    pm = draft.get("period_months")
    if pm is not None:
        try:
            context["period_months"] = float(pm)
        except ValueError:
            context["period_months"] = 12.0
    else:
        context["period_months"] = 12.0

    return context

def evaluate_formula(formula: str, context: Dict[str, float]) -> Union[float, str]:
    """
    Evaluate a coverage or cost formula against a given context.
    Returns a string if the formula represents a symbolic token.
    Returns a float if the formula is a math expression.
    """
    if not formula:
        return ""
        
    formula = formula.strip()
    
    if formula in SYMBOLIC_TOKENS:
        return SYMBOLIC_TOKENS[formula]
        
    try:
        node = ast.parse(formula, mode='eval').body
        return float(_safe_eval(node, context))
    except Exception as e:
        # If it fails to evaluate as math, assume it's a literal string
        return formula
