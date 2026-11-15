#!/usr/bin/env python3
"""
Generate synthetic Mobile Money transactions CSV
For ZOBO Hardware Store demo scenario
100% synthetic data (no real phone numbers or transactions)
"""
import csv
from datetime import datetime, timedelta
import random
from pathlib import Path

# Demo data - 100% synthetic
CUSTOMERS = [
    "Client A",
    "Client B", 
    "Client C",
    "Client D",
    "Client E"
]

PRODUCTS = [
    ("Ciment 50 kg", 5000),
    ("Pointes 2 pouces (1kg)", 1500),
    ("Vis à bois 4x40 (boîte)", 2000),
    ("Tuyau PVC 1/2 (6m)", 3500),
    ("Câble électrique 2x1.5 (rouleau 100m)", 25000),
    ("Peinture mate blanc (10L)", 15000),
    ("Marteau menuisier", 4000),
    ("Perceuse Bosch GSB 13", 45000),
    ("Cadenas Master Lock", 3000),
    ("Serrure porte Yale", 8000)
]

OPERATORS = ["MTN MoMo", "Orange Money"]

def generate_transactions(num_transactions: int = 50) -> list:
    """Generate synthetic Mobile Money transactions"""
    transactions = []
    # Fixed seed: regenerating the CSV always yields the same data
    random.seed(42)
    start_date = datetime(2026, 11, 1)
    
    for i in range(num_transactions):
        # Transaction details
        transaction_id = f"MM{start_date.year}{(i+1):06d}"
        timestamp = start_date + timedelta(
            days=random.randint(0, 12),
            hours=random.randint(8, 18),
            minutes=random.randint(0, 59)
        )
        
        customer = random.choice(CUSTOMERS)
        product, base_price = random.choice(PRODUCTS)
        quantity = random.randint(1, 5)
        amount = base_price * quantity
        
        # Phone number: obviously fake (237 = Cameroon code, then a 00x block that is not assigned)
        phone = f"237{random.choice(['000', '001', '002', '003'])}{random.randint(100000, 999999)}"
        
        operator = random.choice(OPERATORS)
        status = "SUCCESS" if random.random() > 0.05 else "PENDING"
        
        transactions.append({
            "transaction_id": transaction_id,
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "phone": phone,
            "customer_name": customer,
            "operator": operator,
            "amount": amount,
            "currency": "XAF",
            "status": status,
            "reference": product,
            "quantity": quantity
        })
    
    transactions.extend(_scenario_transactions(len(transactions)))

    # Sort by timestamp
    transactions.sort(key=lambda x: x["timestamp"])
    
    return transactions


def _scenario_transactions(already_generated: int) -> list:
    """Scripted payments that match WhatsApp orders of generate_whatsapp.py.

    The same ciment order is paid twice: one SUCCESS (r_payment_received
    correlates it) and one PENDING (the rule ignores it). The other references
    are partial names of the catalog ("Tuyau PVC 32mm", "Perceuse électrique 500W").
    """
    rows = [
        ("2026-11-01 10:05:00", "Client A", "Perceuse électrique 500W", 45000, "SUCCESS", 1),
        ("2026-11-02 09:00:00", "M. Talla", "Tuyau PVC 32mm", 9600, "SUCCESS", 2),
        ("2026-11-06 09:30:00", "Client C", "Ciment 50 kg", 15000, "SUCCESS", 2),
        ("2026-11-06 10:15:00", "Client C", "Ciment 50 kg", 7500, "PENDING", 1),
    ]
    return [
        {
            "transaction_id": f"MM2026{already_generated + index + 1:06d}",
            "timestamp": timestamp,
            "phone": f"2370009{index:05d}",
            "customer_name": customer,
            "operator": "MTN MoMo",
            "amount": amount,
            "currency": "XAF",
            "status": status,
            "reference": reference,
            "quantity": quantity,
        }
        for index, (timestamp, customer, reference, amount, status, quantity) in enumerate(rows)
    ]


def main():
    """Generate and save Mobile Money CSV"""
    output_path = Path(__file__).parent.parent / "data" / "momo_transactions.csv"
    output_path.parent.mkdir(exist_ok=True)
    
    transactions = generate_transactions(50)
    
    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            "transaction_id", "timestamp", "phone", "customer_name",
            "operator", "amount", "currency", "status", "reference", "quantity"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(transactions)
    
    print(f"✓ Generated {len(transactions)} synthetic Mobile Money transactions")
    print(f"  Saved to: {output_path}")
    print(f"\nSample transactions:")
    for tx in transactions[:3]:
        print(f"  {tx['timestamp']} | {tx['customer_name']} | {tx['amount']} XAF | {tx['reference']}")


if __name__ == "__main__":
    main()
