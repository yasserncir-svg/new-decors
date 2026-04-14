#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migration pour mettre à jour la base sans perte de données
"""

import sqlite3
import os

def get_db_connection():
    """Retourne une connexion à la base de données"""
    return sqlite3.connect('new_decors.db')

def column_exists(cursor, table, column):
    """Vérifie si une colonne existe dans une table"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cursor.fetchall()]
    return column in columns

def table_exists(cursor, table):
    """Vérifie si une table existe"""
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None

def migrate_database():
    """Applique les migrations nécessaires"""
    if not os.path.exists('new_decors.db'):
        print("❌ Base de données non trouvée")
        return False
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    migrations_applied = []
    
    # ========== MIGRATIONS ==========
    
    # 1. Ajouter colonne stock_deducted à orders si elle n'existe pas
    if table_exists(cursor, 'orders') and not column_exists(cursor, 'orders', 'stock_deducted'):
        cursor.execute("ALTER TABLE orders ADD COLUMN stock_deducted INTEGER DEFAULT 0")
        migrations_applied.append("Ajout colonne stock_deducted à orders")
    
    # 2. Ajouter colonne seller_id à stock_out
    if table_exists(cursor, 'stock_out') and not column_exists(cursor, 'stock_out', 'seller_id'):
        cursor.execute("ALTER TABLE stock_out ADD COLUMN seller_id INTEGER")
        migrations_applied.append("Ajout colonne seller_id à stock_out")
    
    # 3. Ajouter colonne seller_name à stock_out
    if table_exists(cursor, 'stock_out') and not column_exists(cursor, 'stock_out', 'seller_name'):
        cursor.execute("ALTER TABLE stock_out ADD COLUMN seller_name TEXT")
        migrations_applied.append("Ajout colonne seller_name à stock_out")
    
    # 4. Ajouter colonne commentaire à sorties
    if table_exists(cursor, 'sorties') and not column_exists(cursor, 'sorties', 'commentaire'):
        cursor.execute("ALTER TABLE sorties ADD COLUMN commentaire TEXT")
        migrations_applied.append("Ajout colonne commentaire à sorties")
    
    # 5. Ajouter colonne commentaire à entrees
    if table_exists(cursor, 'entrees') and not column_exists(cursor, 'entrees', 'commentaire'):
        cursor.execute("ALTER TABLE entrees ADD COLUMN commentaire TEXT")
        migrations_applied.append("Ajout colonne commentaire à entrees")
    
    # 6. Ajouter colonne active à products
    if table_exists(cursor, 'products') and not column_exists(cursor, 'products', 'active'):
        cursor.execute("ALTER TABLE products ADD COLUMN active INTEGER DEFAULT 1")
        migrations_applied.append("Ajout colonne active à products")
    
    # ========== FIN DES MIGRATIONS ==========
    
    conn.commit()
    conn.close()
    
    if migrations_applied:
        print("✅ Migrations appliquées :")
        for migration in migrations_applied:
            print(f"   - {migration}")
    else:
        print("✅ Base de données déjà à jour")
    
    return True

def check_database_integrity():
    """Vérifie l'intégrité de la base de données"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchone()
    
    conn.close()
    
    if result and result[0] == 'ok':
        print("✅ Intégrité de la base vérifiée")
        return True
    else:
        print("❌ Problème d'intégrité détecté")
        return False

if __name__ == '__main__':
    print("🔧 Migration de la base de données...")
    migrate_database()
    check_database_integrity()
