"""
rules.py — Commons regeneration logic for the heterogeneous MASTOC scenario.
"""


def apply_round_events(environment, round_number, config):
    commons = config.get("commons", {})
    stock = environment._get_depot_resource()
    collapse_threshold = commons.get("collapse_threshold", 20)
    max_stock = commons.get("max_stock", 120)
    base_regeneration = commons.get("regeneration_per_round", 12)

    messages = []
    if round_number > 1:
        if stock <= collapse_threshold:
            environment.current_regeneration_rate = 0
            messages.append(
                f"The pasture has collapsed (stock={stock} units). Regeneration is suspended."
            )
        else:
            environment.current_regeneration_rate = base_regeneration
            new_stock = min(stock + environment.current_regeneration_rate, max_stock)
            environment._set_depot_resource(new_stock)
            messages.append(
                f"The pasture regenerates by {environment.current_regeneration_rate} units."
            )

    return messages
