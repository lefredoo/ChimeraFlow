"""
Generate synthetic WhatsApp export: commandes_clients.txt
ZOBO Hardware Store customer orders with multilingual mix
"""
from pathlib import Path
from datetime import datetime, timedelta
import random

# Seed for reproducibility
random.seed(42)

# Synthetic customers
customers = ["Client A", "Client B", "Client C", "Mme Nguema", "M. Talla"]

# Product requests with variations
requests = [
    "Bonjour, j'ai besoin de ciment 50 kg. C'est disponible?",
    "Bsr. Quel est le prix du ciment 50kg svp?",
    "Hello, do you have cement 50 kg in stock?",
    "Je cherche des pointes 2.5\" pour mon chantier",
    "Avez-vous des vis bois 4x40?",
    "Il me faut du tuyau PVC diamètre 32mm",
    "Besoin de câble électrique 2.5mm²",
    "Prix de la peinture blanche 1L?",
    "Ciment-colle 25kg dispo?",
    "Marteau rivoir en stock?",
    "Je veux acheter une perceuse 500W",
    "Cadenas laiton 40mm, combien?",
    "Interrupteur va et vient svp",
    "Serrure à mortaiser disponible?",
    "Tuyau PPR 20mm vous avez?",
    "Raccord coude 90° PVC 32",
    "Prise double combien ça coûte?",
    "Penture acier 30cm la paire",
    "Scie égoïne 450mm dispo",
    "Rouleau peinture mousse",
]

# Generate messages over 7 days
start_date = datetime(2026, 11, 1, 8, 0)
messages = []

for i, request in enumerate(requests):
    # Random timestamp over 7 days, business hours
    day_offset = random.randint(0, 6)
    hour = random.randint(8, 18)
    minute = random.randint(0, 59)
    
    timestamp = start_date + timedelta(days=day_offset, hours=hour-8, minutes=minute)
    customer = random.choice(customers)
    
    # Android format: [DD/MM/YYYY, HH:MM:SS] Customer: Message
    messages.append(f"[{timestamp.strftime('%d/%m/%Y, %H:%M:%S')}] {customer}: {request}\n")

# Add some replies from shop (ZOBO)
replies = [
    "Oui disponible. Prix 7500 FCFA",
    "En stock. Passez nous voir",
    "Rupture de stock. Retour lundi",
    "Yes, we have it. 7500 FCFA",
]

for i in [3, 7, 11, 15]:
    if i < len(messages):
        timestamp = start_date + timedelta(days=i//3, hours=i%3, minutes=random.randint(0, 59))
        reply = random.choice(replies)
        messages.insert(i+1, f"[{timestamp.strftime('%d/%m/%Y, %H:%M:%S')}] ZOBO Quincaillerie: {reply}\n")

# Sort by timestamp
messages.sort()

# Save to file
output_path = Path(__file__).parent.parent / "data" / "commandes_clients.txt"
output_path.parent.mkdir(exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    f.writelines(messages)

print(f"✓ Generated: {output_path}")
print(f"  Messages: {len(messages)}")
print(f"  Period: 7 days (Nov 1-7, 2026)")
print(f"  Format: Android WhatsApp export")
