"""
Predefined rules for ChimeraFlow
5 rules as per Roadmap §3, P2 scope
"""
from schemas.rule import RuleCreate, RuleTrigger, RuleJoin, RuleEmit, WhereCondition, Operator


PREDEFINED_RULES = [
    # Rule 1: Low stock alert (demo rule from Roadmap)
    RuleCreate(
        id="r_low_stock",
        natural_language="Quand un client demande un produit sur WhatsApp, montre son stock Access et son prix Excel, et alerte-moi si le stock est inférieur à 10.",
        trigger=RuleTrigger(source="whatsapp", entity="product"),
        joins=[
            RuleJoin(
                source="access",
                table="Articles",
                on={"entity": "product", "field": "designation"},
                where=[WhereCondition(field="qty_stock", op=Operator.lt, value=10)]
            ),
            RuleJoin(
                source="excel",
                sheet="Tarifs",
                on={"entity": "product", "field": "Produit"}
            )
        ],
        window_seconds=604800,  # 7 days
        emit=RuleEmit(
            severity="warning",
            template="⚠️ Stock bas : {product} — stock: {access.qty_stock}, prix: {excel.Prix_Unitaire} FCFA"
        )
    ),
    
    # Rule 2: Payment received confirmation
    RuleCreate(
        id="r_payment_received",
        natural_language="Quand un paiement Mobile Money est reçu, vérifier s'il correspond à une commande WhatsApp récente.",
        trigger=RuleTrigger(source="momo", entity="product"),
        joins=[
            RuleJoin(
                source="whatsapp",
                on={"entity": "product", "field": "text"},
                where=[]
            )
        ],
        window_seconds=86400,  # 1 day
        emit=RuleEmit(
            severity="info",
            template="✅ Paiement reçu : {momo.amount} {momo.currency} pour {product} (commande confirmée)"
        )
    ),
    
    # Rule 3: Price comparison (supplier vs stock)
    RuleCreate(
        id="r_price_comparison",
        natural_language="Comparer le prix d'achat en stock Access avec le tarif fournisseur Excel pour détecter des écarts > 10%.",
        trigger=RuleTrigger(source="access", entity="product"),
        joins=[
            RuleJoin(
                source="excel",
                sheet="Tarifs",
                on={"entity": "product", "field": "Produit"}
            )
        ],
        window_seconds=2592000,  # 30 days
        emit=RuleEmit(
            severity="warning",
            template="💰 Écart de prix : {product} — stock: {access.prix_achat} FCFA, fournisseur: {excel.Prix_Unitaire} FCFA"
        )
    ),
    
    # Rule 4: High-value order tracking
    RuleCreate(
        id="r_high_value_order",
        natural_language="Alerter quand une commande WhatsApp concerne un produit Excel dont le prix > 10000 FCFA.",
        trigger=RuleTrigger(source="whatsapp", entity="product"),
        joins=[
            RuleJoin(
                source="excel",
                sheet="Tarifs",
                on={"entity": "product", "field": "Produit"},
                where=[WhereCondition(field="Prix_Unitaire", op=Operator.gt, value=10000)]
            )
        ],
        window_seconds=604800,  # 7 days
        emit=RuleEmit(
            severity="info",
            template="🎯 Commande importante : {product} — prix: {excel.Prix_Unitaire} FCFA"
        )
    ),
    
    # Rule 5: Stock replenishment recommendation
    RuleCreate(
        id="r_stock_replenish",
        natural_language="Recommander un réapprovisionnement quand le stock Access est < 15 et qu'il y a eu des commandes WhatsApp récentes.",
        trigger=RuleTrigger(source="access", entity="product"),
        joins=[
            RuleJoin(
                source="whatsapp",
                on={"entity": "product", "field": "text"},
                where=[]
            ),
            RuleJoin(
                source="excel",
                sheet="Tarifs",
                on={"entity": "product", "field": "Produit"}
            )
        ],
        window_seconds=259200,  # 3 days
        emit=RuleEmit(
            severity="warning",
            template="📦 Réappro recommandé : {product} — stock actuel: {access.qty_stock}, prix fournisseur: {excel.Prix_Unitaire} FCFA"
        )
    )
]


# Rules whose natural language promises more than the DSL can express today
# (no trigger-side where, no computed gap, join on an entity field). They are
# seeded inactive so that no correlation contradicts its own description.
INACTIVE_PREDEFINED_IDS = frozenset({
    "r_payment_received",
    "r_price_comparison",
    "r_stock_replenish",
})


def get_predefined_rules():
    """Get list of predefined rules"""
    return PREDEFINED_RULES


def get_predefined_rule(rule_id: str) -> RuleCreate:
    """Get specific predefined rule by ID"""
    for rule in PREDEFINED_RULES:
        if rule.id == rule_id:
            return rule
    return None
