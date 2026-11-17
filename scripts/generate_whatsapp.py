"""
Generate synthetic WhatsApp export: commandes_clients.txt
ZOBO Hardware Store customer orders with multilingual mix.

The messages are scripted (not random) so that every predefined rule finds
something on the shipped data. Which message feeds which rule:
- ciment 50kg / ciment 50 kg / cement 50 kg: the four spellings of one product
  (r_low_stock, r_payment_received)
- perceuse 500W and tuyau PVC: partial names, shorter than the catalog name
  (r_high_value_order, r_stock_replenish, r_payment_received)
- the 03/11 10:05 message asks for two products at once
- câble, serrure: low stock products that customers ask for (r_stock_replenish)
- the last two messages exercise the parser: a three-line message and a media
  placeholder (flagged `attachment` in the payload)
"""
from pathlib import Path

# (DD/MM/YYYY, HH:MM:SS, author, text); synthetic customers
MESSAGES = [
    ("01/11/2026", "09:24:00", "Client A", "Je veux acheter une perceuse 500W"),
    ("01/11/2026", "16:12:00", "M. Talla", "Il me faut du tuyau PVC diamètre 32mm"),
    ("01/11/2026", "16:18:00", "M. Talla", "Tuyau PPR 20mm vous avez?"),
    ("02/11/2026", "08:10:00", "ZOBO Quincaillerie", "Rupture de stock. Retour lundi"),
    ("02/11/2026", "11:08:00", "Client A", "Bsr. Quel est le prix du ciment 50kg svp?"),
    ("02/11/2026", "11:32:00", "M. Talla", "Avez-vous des vis bois 4x40?"),
    ("02/11/2026", "11:48:00", "Client C", "Marteau rivoir en stock?"),
    ("03/11/2026", "08:48:00", "Client B", "Prix de la peinture blanche 1L?"),
    ("03/11/2026", "09:22:00", "ZOBO Quincaillerie", "En stock. Passez nous voir"),
    ("03/11/2026", "10:05:00", "Mme Nguema", "Bonjour, il me faut du ciment 50 kg et une perceuse 500W svp"),
    ("03/11/2026", "13:38:00", "Client C", "Cadenas laiton 40mm, combien?"),
    ("04/11/2026", "08:01:00", "Client A", "Je cherche des pointes 2.5\" pour mon chantier"),
    ("04/11/2026", "10:42:00", "ZOBO Quincaillerie", "Rupture de stock. Retour lundi"),
    ("04/11/2026", "11:28:00", "M. Talla", "Besoin de câble électrique 2.5mm²"),
    ("04/11/2026", "18:53:00", "Client C", "Rouleau peinture mousse"),
    ("05/11/2026", "09:59:00", "Mme Nguema", "Serrure à mortaiser disponible?"),
    ("06/11/2026", "08:44:00", "ZOBO Quincaillerie", "Oui disponible. Prix 7500 FCFA"),
    ("06/11/2026", "09:01:00", "Client C", "Bonjour, j'ai besoin de ciment 50 kg. C'est disponible?"),
    ("06/11/2026", "09:02:00", "Client B", "Prise double combien ça coûte?"),
    ("06/11/2026", "14:21:00", "Client C", "Ciment-colle 25kg dispo?"),
    ("06/11/2026", "16:05:00", "M. Talla", "Hello, do you have cement 50 kg in stock?"),
    ("07/11/2026", "08:46:00", "Mme Nguema", "Interrupteur va et vient svp"),
    ("07/11/2026", "09:24:00", "Client C", "Scie égoïne 450mm dispo"),
    ("07/11/2026", "12:05:00", "Client B", "Penture acier 30cm la paire"),
    ("07/11/2026", "13:36:00", "Client B", "Raccord coude 90° PVC 32"),
    # Multi-line message (the text keeps its line breaks) and a media placeholder
    ("08/11/2026", "08:15:00", "Mme Nguema", "Bonjour,\nje repasse demain matin.\nPouvez-vous réserver une perceuse 500W ?\nMerci"),
    ("08/11/2026", "08:16:00", "Mme Nguema", "<Médias omis>"),
]


def main() -> None:
    """Write the Android-format export: [DD/MM/YYYY, HH:MM:SS] Author: Message."""
    output_path = Path(__file__).parent.parent / "data" / "commandes_clients.txt"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(f"[{day}, {time}] {author}: {text}\n" for day, time, author, text in MESSAGES)

    print(f"✓ Generated: {output_path}")
    print(f"  Messages: {len(MESSAGES)}")
    print("  Period: 8 days (Nov 1-8, 2026)")
    print("  Format: Android WhatsApp export")


if __name__ == "__main__":
    main()
