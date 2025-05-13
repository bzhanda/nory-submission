# Data Health Assistant

A tool to check for errors in food inventory and recipe data.

## How to Use
1. Place `items.csv` and `recipes.csv` files in the `data` folder.
2. Run `python data_assistant.py` in your terminal.
3. Check the generated reports (e.g., `duplicates_report.json`).

## Features
- Duplicate Detection: Fuzzy matching for similar item names (e.g., "Tomato" vs "Tomatoes").
- Unit Validation: Checks for valid units (`g`, `kg`, `ml`, `l`, `ea`) and consistency between items and recipes.
- Missing Data Alerts: Flags empty supplier codes, prices, or tax rates.
- Quantity Limits: Warns about unrealistic quantities (e.g., 5000kg of flour).

## Improvements
- Provide data validation parameters for implementation at point of collection
- AI integration (data cleanup)
- Build user friendly UI
- Expand unit support
