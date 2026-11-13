"""
Generate synthetic Excel file: tarifs_fournisseurs.xlsx
ZOBO Hardware Store supplier price list with intentional imperfections
"""
import pandas as pd
from pathlib import Path
import random

# Seed for reproducibility
random.seed(42)

# ZOBO products with intentional spelling variations
products = [
    # Pointes et vis
    ("Pointes 2.5\" (boîte 500g)", 150, "Quincaillerie Centrale"),
    ("Vis bois 4x40mm (100 pcs)", 850, "Visserie Douala"),
    ("Clous tête plate 70mm", 2200, "Quincaillerie Centrale"),
    
    # Tuyaux PVC
    ("Tuyau PVC Ø 32mm (barre 6m)", 4800, "Plastiques du Littoral"),
    ("Raccord PVC coude 90° Ø 32", 245, "Plastiques du Littoral"),
    ("Tuyau PPR Ø 20mm (barre 4m)", 3500, "Hydro-Tech"),
    
    # Électrique
    ("Câble électrique 2.5mm² (rouleau 100m)", 45000, "Électro-Supply"),
    ("Interrupteur va-et-vient", 1250, "Électro-Supply"),
    ("Prise de courant double", 2100, "Électro-Supply"),
    
    # Serrurerie
    ("Cadenas laiton 40mm", 3500, "Serrurerie Moderne"),
    ("Serrure à mortaiser", 12000, "Serrurerie Moderne"),
    ("Penture acier 30cm (paire)", 4200, "Serrurerie Moderne"),
    
    # Peinture
    ("Peinture satinée blanc 1L", 5500, "Couleurs Cameroun"),
    ("Pinceau plat 2\"", 1800, "Couleurs Cameroun"),
    ("Rouleau peinture mousse 10cm", 2200, "Couleurs Cameroun"),
    
    # Ciment
    ("Ciment 50 kg", 7500, "Matériaux Wouri"),
    ("Ciment-colle 25 kg", 3900, "Matériaux Wouri"),
    
    # Outillage
    ("Marteau rivoir 500g", 5900, "Outils Pro"),
    ("Scie égoïne 450mm", 8500, "Outils Pro"),
    ("Perceuse électrique 500W", 45000, "Outils Pro"),
]

# Create DataFrame
df = pd.DataFrame(products, columns=["Produit", "Prix_Unitaire", "Fournisseur"])
df["Date_MAJ"] = pd.date_range("2026-10-01", periods=len(products), freq="2D")

# Add intentional variations for same product (test normalization)
variations = [
    ("ciment 50 kg", 7500, "Matériaux Wouri", "2026-11-01"),  # lowercase
    ("Ciment50kg", 7600, "BTP Discount", "2026-11-02"),  # no spaces
    ("cimént 50kg", 7450, "Matériaux Wouri", "2026-11-03"),  # wrong accent
    ("ciment (50kg)", 7550, "Cimenterie Douala", "2026-11-04"),  # parentheses
]

for prod, price, supplier, date in variations:
    df = pd.concat([df, pd.DataFrame([{
        "Produit": prod,
        "Prix_Unitaire": price,
        "Fournisseur": supplier,
        "Date_MAJ": pd.to_datetime(date)
    }])], ignore_index=True)

# Save to Excel
output_path = Path(__file__).parent.parent / "data" / "tarifs_fournisseurs.xlsx"
output_path.parent.mkdir(exist_ok=True)

with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name="Tarifs", index=False)

print(f"✓ Generated: {output_path}")
print(f"  Products: {len(df)} rows")
print(f"  Includes {len(variations)} intentional variations for testing")
