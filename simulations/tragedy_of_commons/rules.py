"""
rules.py — Event handlers for the Tragedy of the Commons scenario.
"""

def apply_round_events(environment, round_number, config):
    stock = environment._get_depot_resource()
    if round_number > 1 and stock >= 20:
        new_stock = min(stock + 12, 120)
        environment._set_depot_resource(new_stock)
    return []