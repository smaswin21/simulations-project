"""
rules.py — Event handlers for the Tragedy of the Commons scenario.
"""

def apply_round_events(environment, round_number, config):
    stock = environment._get_depot_resource()
    commons = config.get("commons", {})
    max_stock = commons.get("max_stock", 120)
    collapse_threshold = commons.get("collapse_threshold", 20)
    if round_number > 1:
        if stock <= collapse_threshold:
            return [
                f"The pasture has collapsed (stock={stock} units). "
                f"Regeneration is suspended until stock recovers above {collapse_threshold}."
            ]
        new_stock = min(stock + 12, max_stock)
        environment._set_depot_resource(new_stock)
    return []