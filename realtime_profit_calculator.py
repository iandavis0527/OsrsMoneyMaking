import argparse
import sys

import requests

# OSRS Wiki API endpoints
MAPPING_URL = "https://prices.runescape.wiki/api/v1/osrs/mapping"
LATEST_PRICES_URL = "https://prices.runescape.wiki/api/v1/osrs/latest"

# Best Practice: The OSRS Wiki API requires a descriptive User-Agent
# identifying your application so you don't get rate-limited or blocked.
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
    input_items_dict, output_item_name, quantity_output_produced=1
):
    """
    Calculates profit margin when buying input items and selling an output item.

    :param input_items_dict: Dict of {item_name: quantity_needed}
    :param output_item_name: Name of the resulting output item
    :param quantity_output_produced: How many of the output item are produced per batch
    """
    mapping_data, prices_data = fetch_api_data()
    name_map = build_name_to_id_map(mapping_data)

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

    # When selling an item on the Grand Exchange instantly, you receive the 'low' price
    output_sell_price = output_pricing.get("low", 0)

    print("\n" + "=" * 50)
    print(f"OUTPUT ITEM: {output_item_name} (ID: {output_id})")
    print(f"  - Instant-Sell Price (Low): {output_sell_price:,} gp")
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

        # When buying an item on the Grand Exchange instantly, you pay the 'high' price
        buy_price = item_pricing.get("high", 0)
        total_cost = buy_price * qty
        total_input_cost += total_cost

        print(f"{item_name:<30} | {qty:<6} | {buy_price:<18,d} | {total_cost:<15,d}")

    # 3. Calculate Profit Margins
    total_output_revenue = output_sell_price * quantity_output_produced
    profit = total_output_revenue - total_input_cost

    # Calculate margin percentage (avoiding division by zero)
    profit_margin_pct = (profit / total_input_cost * 100) if total_input_cost > 0 else 0

    print("-" * 75)
    print("\nFINANCIAL SUMMARY:")
    print(f"  Total Input Cost:       {total_input_cost:,} gp")
    print(
        f"  Total Output Revenue:   {total_output_revenue:,} gp  (Qty: {quantity_output_produced})"
    )
    print("  --------------------------------------------------")
    print(f"  Net Profit / Loss:      {profit:,} gp")
    print(f"  Profit Margin:          {profit_margin_pct:.2f}%")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="OSRS Profit Calculator: Calculate profit margins for item conversions."
    )
    parser.add_argument(
        "--input",
        nargs="+",
        help="Input items and quantities in the format ItemName:Quantity",
        required=True,
    )
    parser.add_argument(
        "--output_item",
        help="Name of the output item produced from the input items.",
        required=True,
    )
    parser.add_argument(
        "--output_quantity",
        default=1,
        type=int,
        help="Quantity of the output item produced per batch.",
    )
    args = parser.parse_args()

    inputs = {}

    for input_str in args.input:
        try:
            item_name, qty_str = input_str.split(":")
            qty = int(qty_str)
            if qty <= 0:
                raise ValueError
            inputs[item_name.strip()] = qty
        except ValueError:
            print(
                f"Error: Invalid input format '{input_str}'. Use 'ItemName:Quantity' with a positive integer."
            )
            sys.exit(1)

    output_item = args.output_item.strip()
    output_qty = args.output_quantity

    calculate_conversion_profit(
        input_items_dict=inputs,
        output_item_name=output_item,
        quantity_output_produced=output_qty,
    )
