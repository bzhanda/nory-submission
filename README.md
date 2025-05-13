# Data Health Assistant

A tool to check for errors in food inventory and recipe data.

## How to Use
1. Place `items.csv` and `recipes.csv` files in the `data` folder.
2. Run `python data_assistant.py` in your terminal.
3. Check the generated reports (e.g., `duplicates_report.json`).

## What It Checks
- Duplicate item names
- Invalid units (e.g., "kg" vs "kilo")
- Missing ingredient prices or supplier codes
