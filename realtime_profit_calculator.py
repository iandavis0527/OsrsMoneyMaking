import argparse
import json
import sys

import requests

# OSRS Wiki API endpoints
MAPPING_URL = "https://prices.runescape.wiki/api/v1/osrs/mapping"
LATEST_PRICES_URL = "https://prices.runescape.wiki/api/v1/osrs/latest"

# Best Practice: The OSRS Wiki API requires a descriptive User-Agent
HEADERS = {"User-Agent": "OSRSProfitCalculator/1.0 (contact@example.com)"}


def fetch_api_data():
    """Fetches mapping and latest price data from the OSRS Wiki API."""
    try:
        print("Fetching item mapping from OSRS Wiki...")
        mapping_res = requests.get(MAPPING_URL, headers=HEADERS)
        mapping_res.raise_for_status()
        mapping_data = mapping_res.json()

        print("Fetching latest prices from OSRS Wiki...")
        prices_res = requests.get(LATEST_PRICES_URL, headers=HEADERS)
        prices_res.raise_for_status()
        prices_data = prices_res.json().get("data", {})

        return mapping_data, prices_data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        sys.exit(1)


def build_name_to_id_map(mapping_data):
    """Creates a case-insensitive dictionary mapping item names to their IDs."""
    name_map = {}
    for item in mapping_data:
        name = item.get("name", "").lower()
        item_id = item.get("id")
        if name and item_id is not None:
            name_map[name] = item_id
    return name_map


def calculate_conversion_profit(
    input_items_dict,
    output_item_name,
    quantity_output_produced,
    mapping_data,
    prices_data,
    name_map,
):
    """
    Calculates profit margin when buying input items and selling/valuing an output item
    using its instant buy (high) price.
    """
    # 1. Evaluate Output Item
    output_key = output_item_name.lower()
    if output_key not in name_map:
        print(
            f"Error: Output item '{output_item_name}' not found in OSRS item database."
        )
        return

    output_id = str(name_map[output_key])
    output_pricing = prices_data.get(output_id)

    if not output_pricing:
        print(f"Error: No price data available for output item '{output_item_name}'.")
        return

    # Updated: Using 'high' price for the instant-buy price of the output item
    output_instant_buy_price = output_pricing.get("high", 0)

    print("\n" + "=" * 50)
    print(f"OUTPUT ITEM: {output_item_name} (ID: {output_id})")
    print(f"  - Instant-Buy Price (High): {output_instant_buy_price:,} gp")
    print("=" * 50)

    # 2. Evaluate Input Items
    total_input_cost = 0
    print("\nINPUT ITEMS BREAKDOWN:")
    print(
        f"{'Item Name':<30} | {'Qty':<6} | {'Buy Price (High)':<18} | {'Total Cost':<15}"
    )
    print("-" * 75)

    for item_name, qty in input_items_dict.items():
        item_key = item_name.lower()
        if item_key not in name_map:
            print(f"Warning: Input item '{item_name}' not found in database. Skipping.")
            continue

        item_id = str(name_map[item_key])
        item_pricing = prices_data.get(item_id)

        if not item_pricing:
            print(
                f"Warning: No price data available for input item '{item_name}'. Skipping."
            )
            continue

        # Buying input items at instant buy (high) price
        buy_price = item_pricing.get("high", 0)
        total_cost = buy_price * qty
        total_input_cost += total_cost

        print(f"{item_name:<30} | {qty:<6} | {buy_price:<18,d} | {total_cost:<15,d}")

    # 3. Calculate Profit Margins
    total_output_revenue = output_instant_buy_price * quantity_output_produced
    profit = total_output_revenue - total_input_cost

    # Calculate margin percentage (avoiding division by zero)
    profit_margin_pct = (profit / total_input_cost * 100) if total_input_cost > 0 else 0

    print("-" * 75)
    print("FINANCIAL SUMMARY:")
    print(f"  Total Input Cost:       {total_input_cost:,} gp")
    print(
        f"  Total Output Value:     {total_output_revenue:,} gp  (Qty: {quantity_output_produced})"
    )
    print("  --------------------------------------------------")
    print(f"  Net Profit / Loss:      {profit:,} gp")
    print(f"  Profit Margin:          {profit_margin_pct:.2f}%")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="OSRS Profit Calculator: Calculate profit margins from a JSON recipe file."
    )
    parser.add_argument(
        "--json",
        default="realtime_profit_inputs.json",
        help="Path to the JSON file containing recipes.",
    )
    args = parser.parse_args()

    # Load and parse JSON file
    try:
        with open(args.json, "r", encoding="utf-8") as f:
            recipes = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file '{args.json}' was not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON file: {e}")
        sys.exit(1)

    if not isinstance(recipes, list):
        print("Error: JSON root element must be an array of recipe objects.")
        sys.exit(1)

    # Fetch API data once for all recipes in the file
    mapping_data, prices_data = fetch_api_data()
    name_map = build_name_to_id_map(mapping_data)

    # Process each recipe
    for index, recipe in enumerate(recipes, start=1):
        print(f"\nProcessing Recipe #{index}...")

        raw_inputs = recipe.get("inputs", [])
        output_data = recipe.get("output", {})

        # Convert input list of objects into a dictionary of {item_name: quantity}
        inputs_dict = {}
        for inp in raw_inputs:
            item_name = inp.get("item")
            qty = inp.get("quantity")
            if item_name and qty is not None:
                inputs_dict[item_name.strip()] = int(qty)

        output_item_name = output_data.get("item")
        output_qty = output_data.get("quantity", 1)

        if not inputs_dict or not output_item_name:
            print(
                f"Warning: Recipe #{index} is missing valid inputs or output. Skipping."
            )
            continue

        calculate_conversion_profit(
            input_items_dict=inputs_dict,
            output_item_name=output_item_name.strip(),
            quantity_output_produced=int(output_qty),
            mapping_data=mapping_data,
            prices_data=prices_data,
            name_map=name_map,
        )
