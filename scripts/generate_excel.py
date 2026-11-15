"""
Generate synthetic Excel file: tarifs_fournisseurs.xlsx
ZOBO Hardware Store supplier price list with intentional imperfections.

Date_MAJ values sit within a few days of the stock dates of
generate_access_windows.vbs, so the 3-day window of r_stock_replenish and the
7-day windows of the WhatsApp rules reach the price rows.
"""
import pandas as pd
from pathlib import Path

# ZOBO products: (Produit, Prix_Unitaire, Fournisseur, Date_MAJ)
products = [
    # Pointes et vis
    ("Pointes 2.5\" (boîte 500g)", 150, "Quincaillerie Centrale", "2026-11-01"),
    ("Vis bois 4x40mm (100 pcs)", 850, "Visserie Douala", "2026-11-01"),
    ("Clous tête plate 70mm", 2200, "Quincaillerie Centrale", "2026-11-02"),
    # Tuyaux PVC
    ("Tuyau PVC Ø 32mm (barre 6m)", 4800, "Plastiques du Littoral", "2026-11-02"),
    ("Raccord PVC coude 90° Ø 32", 245, "Plastiques du Littoral", "2026-11-02"),
    ("Tuyau PPR Ø 20mm (barre 4m)", 3500, "Hydro-Tech", "2026-11-02"),
    # Électrique
    ("Câble électrique 2.5mm² (rouleau 100m)", 45000, "Électro-Supply", "2026-11-03"),
    ("Interrupteur va-et-vient", 1250, "Électro-Supply", "2026-11-03"),
    ("Prise de courant double", 2100, "Électro-Supply", "2026-11-03"),
    # Serrurerie
    ("Cadenas laiton 40mm", 3500, "Serrurerie Moderne", "2026-11-03"),
    ("Serrure à mortaiser", 12000, "Serrurerie Moderne", "2026-11-04"),  # stock cost 14000: 14 % gap
    ("Penture acier 30cm (paire)", 4200, "Serrurerie Moderne", "2026-11-04"),
    # Peinture
    ("Peinture satinée blanc 1L", 5500, "Couleurs Cameroun", "2026-11-04"),
    ("Pinceau plat 2\"", 1800, "Couleurs Cameroun", "2026-11-04"),
    ("Rouleau peinture mousse 10cm", 2200, "Couleurs Cameroun", "2026-11-04"),
    # Ciment
    ("Ciment 50 kg", 7500, "Matériaux Wouri", "2026-11-01"),
    ("Ciment-colle 25 kg", 3900, "Matériaux Wouri", "2026-11-01"),
    # Outillage
    ("Marteau rivoir 500g", 5900, "Outils Pro", "2026-11-02"),
    ("Scie égoïne 450mm", 8500, "Outils Pro", "2026-11-02"),
    ("Perceuse électrique 500W", 45000, "Outils Pro", "2026-11-03"),  # stock cost 52000: 13 % gap
]

# Create DataFrame
df = pd.DataFrame(products, columns=["Produit", "Prix_Unitaire", "Fournisseur", "Date_MAJ"])
df["Date_MAJ"] = pd.to_datetime(df["Date_MAJ"])

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
