import os
import pandas as pd
import json
from rapidfuzz import process, fuzz

class DataHealthAssistant:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.items_path = os.path.join(data_dir, "items.csv")
        self.recipes_path = os.path.join(data_dir, "recipes.csv")
        self.allowed_units = {'g', 'kg', 'ml', 'l', 'ea'}
        self.quantity_limits = {
            'g': 10000,    # Max 10kg
            'kg': 50,      # Max 50kg
            'ml': 20000,   # Max 20L
            'l': 200,      # Max 200L
            'ea': 1000     # Max 1000 units
        }
        
        # Verify files exist
        self._verify_files_exist()
        
        # Load data
        self.items = pd.read_csv(self.items_path)
        self.recipes = pd.read_csv(self.recipes_path)
        
        # Initialize reports
        self.report = {
            'duplicates': [],
            'unit_issues': {'items': [], 'recipes': []},
            'quantity_issues': [],
            'missing_data': [],
            'recipe_issues': [],
            'unit_consistency': []
        }

    def _verify_files_exist(self):
        """Check if required CSV files are present"""
        missing = []
        if not os.path.exists(self.items_path):
            missing.append('items.csv')
        if not os.path.exists(self.recipes_path):
            missing.append('recipes.csv')
        
        if missing:
            raise FileNotFoundError(
                f"Missing files in {self.data_dir}: {', '.join(missing)}\n"
                f"Current directory: {os.getcwd()}\n"
                f"Looking in: {os.path.abspath(self.data_dir)}"
            )

    def clean_data(self):
        """Normalize and clean raw data"""
        # Clean item names and units
        self.items['Item name'] = self.items['Item name'].str.lower().str.strip()
        self.items['Item Unit of Measure'] = (
            self.items['Item Unit of Measure']
            .str.lower()
            .str.strip()
        )
        
        # Convert numeric fields
        self.items['Item size'] = pd.to_numeric(
            self.items['Item size'], errors='coerce'
        )
        self.items['€ Price per unit (excluding VAT)'] = (
            pd.to_numeric(
                self.items['€ Price per unit (excluding VAT)'].astype(str).str.replace(',', ''),
                errors='coerce'
            )
        )
        
        # Clean tax rates (critical fix)
        self.items['Tax rate'] = pd.to_numeric(
            self.items['Tax rate'].astype(str).str.replace(r'[%\s]', '', regex=True),
            errors='coerce'
        )

    def find_duplicates(self, threshold=90):
        """Find potential duplicate items using fuzzy matching"""
        items = self.items['Item name'].unique()
        seen = set()
        
        for item in items:
            if pd.isna(item):
                continue
            if item not in seen:
                matches = process.extract(
                    item, items, 
                    scorer=fuzz.token_sort_ratio,
                    score_cutoff=threshold
                )
                valid_matches = [
                    m for m in matches 
                    if m[0] != item and m[0] not in seen and not pd.isna(m[0])
                ]
                if valid_matches:
                    self.report['duplicates'].append({
                        'original': item,
                        'matches': [m[0] for m in valid_matches],
                        'confidence': [m[1] for m in valid_matches]
                    })
                    seen.update([item] + [m[0] for m in valid_matches])

    def validate_units_and_quantities(self):
        """Validate units and quantities for items and recipes"""
        # Item unit validation
        item_issues = self.items[
            ~self.items['Item Unit of Measure'].isin(self.allowed_units)
        ]
        self.report['unit_issues']['items'] = item_issues.to_dict('records')
        
        # Recipe validation
        item_unit_map = dict(zip(
            self.items['Item name'].str.lower(),
            self.items['Item Unit of Measure'].str.lower()
        ))
        
        recipe_issues = []
        quantity_issues = []
        unit_consistency_issues = []
        
        for _, row in self.recipes.iterrows():
            for i in range(1, 5):
                ingredient = str(row[f'Name (Ingredient {i})']).lower().strip()
                qty = row[f'Qty (Ingredient {i})']
                unit_raw = row[f'Unit (Ingredient {i})']
                unit = str(unit_raw).lower().strip() if pd.notna(unit_raw) else None
                
                # Unit validation
                if unit and unit not in self.allowed_units:
                    recipe_issues.append({
                        'recipe': row['Menu item name'],
                        'ingredient': ingredient,
                        'issue': f'Invalid unit "{unit}"',
                        'type': 'unit'
                    })
                
                # Quantity validation
                try:
                    if pd.notna(qty):
                        qty_val = float(str(qty).replace(',', ''))
                        if unit and unit in self.quantity_limits:
                            if qty_val > self.quantity_limits[unit]:
                                quantity_issues.append({
                                    'recipe': row['Menu item name'],
                                    'ingredient': ingredient,
                                    'quantity': qty_val,
                                    'unit': unit,
                                    'limit': self.quantity_limits[unit]
                                })
                except ValueError:
                    recipe_issues.append({
                        'recipe': row['Menu item name'],
                        'ingredient': ingredient,
                        'issue': f'Non-numeric quantity "{qty}"',
                        'type': 'quantity'
                    })
                
                # Unit consistency check
                if ingredient in item_unit_map and unit:
                    item_unit = item_unit_map[ingredient]
                    if unit != item_unit:
                        unit_consistency_issues.append({
                            'recipe': row['Menu item name'],
                            'ingredient': ingredient,
                            'recipe_unit': unit,
                            'item_unit': item_unit
                        })
        
        self.report['unit_issues']['recipes'] = recipe_issues
        self.report['quantity_issues'] = quantity_issues
        self.report['unit_consistency'] = unit_consistency_issues

    def check_missing_data(self):
        """Identify missing critical fields"""
        missing = self.items[
            self.items[['Supplier code', 'Item size',
                       'Item Unit of Measure', '€ Price per unit (excluding VAT)']]
            .isnull().any(axis=1)
        ]
        
        # Tax rate validation
        tax_rate_issues = self.items[self.items['Tax rate'].isna()]
        
        self.report['missing_data'] = {
            'missing_fields': missing.to_dict('records'),
            'invalid_tax_rates': tax_rate_issues.to_dict('records')
        }

    def validate_recipes(self):
        """Check if recipe ingredients exist in items"""
        valid_items = set(self.items['Item name'])
        issues = []
        
        for _, row in self.recipes.iterrows():
            for i in range(1, 5):
                ingredient_raw = row[f'Name (Ingredient {i})']
                if pd.isna(ingredient_raw):
                    issues.append({
                        'recipe': row['Menu item name'],
                        'missing_ingredient': '[NaN]',
                        'position': f'Ingredient {i}'
                    })
                    continue
                
                ingredient = str(ingredient_raw).lower().strip()
                if not ingredient:
                    issues.append({
                        'recipe': row['Menu item name'],
                        'missing_ingredient': '[empty string]',
                        'position': f'Ingredient {i}'
                    })
                elif ingredient not in valid_items:
                    issues.append({
                        'recipe': row['Menu item name'],
                        'missing_ingredient': ingredient,
                        'position': f'Ingredient {i}'
                    })
        
        self.report['recipe_issues'] = issues

    def generate_report(self):
        """Run all validations and generate reports"""
        self.clean_data()
        self.find_duplicates()
        self.validate_units_and_quantities()
        self.check_missing_data()
        self.validate_recipes()
        
        # Save reports
        with open('duplicates_report.json', 'w') as f:
            json.dump(self.report['duplicates'], f, indent=2)
            
        pd.DataFrame(self.report['unit_issues']['recipes']).to_csv('unit_issues.csv', index=False)
        pd.DataFrame(self.report['quantity_issues']).to_csv('quantity_issues.csv', index=False)
        pd.DataFrame(self.report['unit_consistency']).to_csv('unit_consistency_issues.csv', index=False)
        
        with open('missing_ingredients.txt', 'w') as f:
            for issue in self.report['recipe_issues']:
                f.write(f"{issue['recipe']}: Missing {issue['missing_ingredient']} (Position {issue['position']})\n")
        
        return self.report

if __name__ == "__main__":
    try:
        assistant = DataHealthAssistant()
        report = assistant.generate_report()
        
        print("\n" + "="*50)
        print(" COMPREHENSIVE DATA HEALTH REPORT ".center(50, '='))
        print("="*50)
        print(f"Duplicate items: {len(report['duplicates'])}")  # Fixed parenthesis
        print(f"Invalid/mismatched units: {len(report['unit_issues']['items']) + len(report['unit_issues']['recipes'])}")
        print(f"Excessive quantities: {len(report['quantity_issues'])}")
        print(f"Missing ingredients: {len(report['recipe_issues'])}")
        print(f"Missing/invalid data entries: {len(report['missing_data']['missing_fields']) + len(report['missing_data']['invalid_tax_rates'])}")
        print(f"Unit consistency issues: {len(report['unit_consistency'])}")
        print("\nDetailed reports saved to:")
        print(f"- duplicates_report.json")
        print(f"- unit_issues.csv")
        print(f"- quantity_issues.csv")
        print(f"- unit_consistency_issues.csv")
        print(f"- missing_ingredients.txt")
        
    except Exception as e:
        print("\nERROR:", str(e))
        print("\nTROUBLESHOOTING:")
        print("1. Verify file structure:")
        print("   your_folder/")
        print("   ├── data/")
        print("   │   ├── items.csv")
        print("   │   └── recipes.csv")
        print("   └── script.py")
        print("2. Check file extensions are .csv and .py")
        print("3. Ensure files are not empty")
