#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEW DECORS - SITE E-COMMERCE COMPLET
Toutes les fonctionnalités: produits, catégories, panier, commandes, admin, fournisseurs, clients, stock, promotions, slider, avis
"""

import sqlite3
import hashlib
import json
import os
import uuid
from datetime import datetime
from functools import wraps

try:
    from flask import Flask, render_template_string, render_template, request, jsonify, session, redirect, url_for, send_from_directory
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'flask'])
    from flask import Flask, render_template_string, render_template, request, jsonify, session, redirect, url_for, send_from_directory

try:
    from PIL import Image
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'Pillow'])
    from PIL import Image

# ==================== AJOUTER LE CODE SUPABASE ICI ====================
from supabase import create_client

# Configuration Supabase (à partir des variables d'environnement)
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
USE_SUPABASE = SUPABASE_URL and SUPABASE_KEY

if USE_SUPABASE:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase connecté")
else:
    supabase = None
    print("⚠️ Supabase non configuré, utilisation de SQLite")

# ==================== AJOUTEZ LA FONCTION ICI ====================
def upload_to_supabase(file, filename):
    """Upload une image vers Supabase Storage"""
    if not USE_SUPABASE or not supabase:
        return None
    
    try:
        # Lire le fichier
        file.seek(0)
        file_content = file.read()
        
        # Upload vers Supabase Storage
        supabase.storage.from_('product-images').upload(
            filename,
            file_content,
            {'content-type': 'image/jpeg'}
        )
        
        # Récupérer l'URL publique
        public_url = supabase.storage.from_('product-images').get_public_url(filename)
        print(f"✅ Image uploadée vers Supabase: {filename}")
        return public_url
    except Exception as e:
        print(f"❌ Erreur upload vers Supabase: {e}")
        return None

# ==================== CONFIGURATION BASE DE DONNÉES ====================
if os.environ.get('RENDER'):
    # Sur Render: utiliser le répertoire local de l'application
    # Créer un dossier 'data' dans le répertoire de l'application
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(DATA_DIR, exist_ok=True)
    DATABASE = os.path.join(DATA_DIR, 'new_decors.db')
    print(f"✅ Mode Render - Dossier data: {DATA_DIR}")
    print(f"✅ Mode Render - Base de données: {DATABASE}")
else:
    DATABASE = 'new_decors.db'
    print(f"✅ Mode local - Base de données: {DATABASE}")

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'new_decors_secret_key_2024')
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Créer les dossiers d'upload (ceux-ci sont déjà des chemins relatifs, donc OK)
for folder in ['static/uploads', 'static/uploads/medium', 'static/uploads/slider']:
    os.makedirs(folder, exist_ok=True)

# ==================== FONCTION DE CONVERSION ====================

def dict_factory(cursor, row):
    """Convertit une ligne SQLite en dictionnaire"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d
    
def execute_query(cursor, query, params=None):
    """Exécute une requête compatible PostgreSQL et SQLite"""
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if params is None:
        params = []
    
    if DATABASE_URL:
        # PostgreSQL : remplacer ? par %s
        query = query.replace('?', '%s')
    
    if params:
        return cursor.execute(query, params)
    else:
        return cursor.execute(query)
        
# ==================== FONCTION GET_DB (UNE SEULE VERSION) ====================

def get_db():
    """Retourne une connexion (PostgreSQL sur Render ou SQLite en local)"""
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = dict_factory
        return conn
def init_postgres_tables():
    """Crée les tables dans PostgreSQL"""
    import psycopg2
    import psycopg2.extras
    import time
    
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        print("⚠️ Pas de DATABASE_URL, skip PostgreSQL")
        return
    
    # Attendre que la DB soit disponible (max 30 secondes)
    for i in range(6):
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            print("✅ Connexion PostgreSQL établie")
            break
        except Exception as e:
            print(f"Tentative {i+1}/6: Connexion échouée, attente 5s... ({e})")
            time.sleep(5)
            conn = None
    
    if not conn:
        print("❌ Impossible de se connecter à PostgreSQL")
        return
    
    cursor = conn.cursor()
    
    # Utilisateurs
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            fullname TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            role TEXT DEFAULT 'client',
            active INTEGER DEFAULT 1,
            last_login TIMESTAMP,
            avatar TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # user_logs
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS user_logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            ip_address TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # order_logs
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS order_logs (
            id SERIAL PRIMARY KEY,
            order_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            old_status TEXT NOT NULL,
            new_status TEXT NOT NULL,
            action_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT
        )
    ''')
    
    # Catégories
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT,
            icon TEXT,
            order_position INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # Sous-catégories
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS subcategories (
            id SERIAL PRIMARY KEY,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT
        )
    ''')
    
    # Produits
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            reference TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT,
            short_description TEXT,
            subcategory_id INTEGER,
            prix_achat REAL DEFAULT 0,
            prix_vente REAL DEFAULT 0,
            prix_promo REAL,
            stock INTEGER DEFAULT 0,
            stock_min INTEGER DEFAULT 5,
            image TEXT,
            featured INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # product_images
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS product_images (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL,
            image TEXT NOT NULL,
            order_position INTEGER DEFAULT 0
        )
    ''')
    
    # Commandes
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            order_number TEXT UNIQUE NOT NULL,
            client_name TEXT NOT NULL,
            client_phone TEXT NOT NULL,
            client_email TEXT NOT NULL,
            client_address TEXT NOT NULL,
            items TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            stock_deducted INTEGER DEFAULT 0
        )
    ''')
    
    # Fournisseurs
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS suppliers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            company TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            contact_person TEXT,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # stock_in
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS stock_in (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL,
            supplier_id INTEGER,
            quantity INTEGER NOT NULL,
            purchase_price REAL NOT NULL,
            total REAL NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    ''')
    
    # stock_out
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS stock_out (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            client_phone TEXT NOT NULL,
            client_email TEXT,
            client_address TEXT,
            quantity INTEGER NOT NULL,
            sale_price REAL NOT NULL,
            total REAL NOT NULL,
            profit REAL NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            sale_type TEXT DEFAULT 'direct',
            order_number TEXT,
            seller_id INTEGER,
            seller_name TEXT
        )
    ''')
    
    # Clients
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS clients (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT UNIQUE,
            email TEXT,
            address TEXT,
            total_achats REAL DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            last_order DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Sliders
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS sliders (
            id SERIAL PRIMARY KEY,
            title TEXT,
            subtitle TEXT,
            image TEXT,
            button_text TEXT,
            button_link TEXT,
            order_position INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # Newsletter
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS newsletter (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Promotions
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS promotions (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            description TEXT,
            discount_type TEXT DEFAULT 'percentage',
            discount_value REAL NOT NULL,
            min_purchase REAL DEFAULT 0,
            start_date DATE,
            end_date DATE,
            usage_limit INTEGER,
            used_count INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # Reviews
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            client_email TEXT,
            rating INTEGER NOT NULL,
            comment TEXT,
            approved INTEGER DEFAULT 1,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Team members
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS team_members (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            position TEXT NOT NULL,
            bio TEXT,
            image TEXT,
            email TEXT,
            order_position INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # Settings
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
        # Admin par défaut
    admin_pass = hashlib.sha256('admin123'.encode()).hexdigest()
    execute_query(cursor, """
        INSERT INTO users (username, password, fullname, role, active) 
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (username) DO NOTHING
    """, ('admin', admin_pass, 'Administrateur', 'admin', 1))
    
    # Catégories
    categories = [
        ('Revetements Muraux', 'revetements-muraux', 'Papiers peints, panneaux PVC', '📄', 1),
        ('Decoration', 'decoration', 'Miroirs, horloges, cadres', '🖼️', 2),
        ('Luminaires', 'luminaires', 'Lampes, suspensions', '💡', 3),
        ('Textiles', 'textiles', 'Coussins, rideaux', '🛋️', 4),
    ]
    for cat in categories:
        execute_query(cursor, """
            INSERT INTO categories (name, slug, description, icon, order_position) 
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO NOTHING
        """, cat)
    
    # Sous-catégories
    subcategories = [
        (1, 'Papiers Peints', 'papiers-peints', 'Collection exclusive'),
        (1, 'Panneaux PVC', 'panneaux-pvc', 'Panneaux PVC - Shibord'),
        (2, 'Miroirs', 'miroirs', 'Miroirs decoratifs'),
        (2, 'Horloges', 'horloges', 'Horloges murales'),
        (3, 'Suspensions', 'suspensions', 'Suspensions modernes'),
        (4, 'Coussins', 'coussins', 'Coussins decoratifs'),
    ]
    for sub in subcategories:
        execute_query(cursor, """
            INSERT INTO subcategories (category_id, name, slug, description) 
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (slug) DO NOTHING
        """, sub)
    
    # Produits
    products = [
        ('PVC001', 'Panneau Shibord Blanc', 'panneau-shibord-blanc', 'Panneau PVC blanc mat', '', 2, 45, 89.90, None, 50, 5, '', 1),
        ('PVC002', 'Panneau Shibord Bois', 'panneau-shibord-bois', 'Panneau PVC effet bois', '', 2, 48, 95.90, 85.90, 30, 5, '', 1),
        ('WP001', 'Papier Peint Tropical', 'papier-peint-tropical', 'Papier peint tropical', '', 1, 35, 79.90, 69.90, 40, 5, '', 1),
        ('MIR001', 'Miroir Rond Doré', 'miroir-rond-dore', 'Miroir rond finition dorée', '', 3, 120, 299.90, 249.90, 15, 3, '', 1),
        ('HOR001', 'Horloge Murale', 'horloge-murale', 'Horloge design moderne', '', 4, 45, 89.90, None, 20, 5, '', 0),
        ('LAM001', 'Suspension Industrielle', 'suspension-industrielle', 'Suspension style industriel', '', 5, 65, 149.90, 129.90, 10, 3, '', 1),
        ('COU001', 'Coussin Velours', 'coussin-velours', 'Coussin velours bleu', '', 6, 25, 49.90, 39.90, 100, 10, '', 1),
    ]
    for p in products:
        execute_query(cursor, """
            INSERT INTO products (reference, name, slug, description, short_description, 
                                  subcategory_id, prix_achat, prix_vente, prix_promo, 
                                  stock, stock_min, image, featured) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (reference) DO NOTHING
        """, p)
    
    # Paramètres
    settings = [
        ('site_name', 'New Decors'),
        ('site_description', 'Decoration d interieur de qualite'),
        ('contact_phone', '+216 70 000 000'),
        ('contact_email', 'contact@newdecors.tn'),
        ('contact_address', 'Tunis, Tunisie'),
        ('about_text', 'New Decors est votre specialiste de la decoration d interieur en Tunisie.'),
        ('hours_monday_friday', '9h - 18h'),
        ('hours_saturday', '10h - 16h'),
        ('hours_sunday', 'Fermé'),
    ]
    for key, value in settings:
        execute_query(cursor, """
            INSERT INTO settings (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO NOTHING
        """, (key, value))
    
    # Code promo
    execute_query(cursor, """
        INSERT INTO promotions (code, description, discount_type, discount_value, min_purchase, active) 
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (code) DO NOTHING
    """, ('BIENVENUE10', '10% sur votre premiere commande', 'percentage', 10, 50, 1))
    conn.commit()
    conn.close()
    print("✅ Tables PostgreSQL créées")

# ==================== FONCTIONS UTILITAIRES ====================

def save_image(file, folder='medium', size=(800, 800)):
    if not file or file.filename == '':
        return None
    
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
    filename = str(uuid.uuid4()) + '.' + ext
    
    # Traitement de l'image
    img = Image.open(file)
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    img.thumbnail(size, Image.Resampling.LANCZOS)
    
    # Si Supabase est configuré, uploader vers Storage
    if USE_SUPABASE and supabase:
        # Sauvegarder temporairement
        temp_path = os.path.join('/tmp', filename)
        img.save(temp_path, 'JPEG', quality=85)
        
        try:
            # Upload vers Supabase
            with open(temp_path, 'rb') as f:
                supabase.storage.from_('product-images').upload(filename, f)
            os.remove(temp_path)
            print(f"✅ Image uploadée vers Supabase: {filename}")
            # Retourner l'URL publique
            return supabase.storage.from_('product-images').get_public_url(filename)
        except Exception as e:
            print(f"❌ Erreur upload Supabase: {e}")
            # Fallback : sauvegarde locale
            img.save(os.path.join(app.config['UPLOAD_FOLDER'], folder, filename), 'JPEG', quality=85)
            return filename
    else:
        # Fallback : sauvegarde locale
        img.save(os.path.join(app.config['UPLOAD_FOLDER'], folder, filename), 'JPEG', quality=85)
        return filename

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ==================== MIGRATIONS ====================

def migrate_orders():
    conn = get_db()
    cursor = conn.cursor()
    try:
        execute_query(cursor,"ALTER TABLE orders ADD COLUMN stock_deducted INTEGER DEFAULT 0")
        conn.commit()
        print("✅ Migration: stock_deducted ajoutée")
    except:
        pass
    try:
        execute_query(cursor,"ALTER TABLE stock_out ADD COLUMN seller_id INTEGER")
        conn.commit()
        print("✅ Migration: seller_id ajoutée")
    except:
        pass
    try:
        execute_query(cursor,"ALTER TABLE stock_out ADD COLUMN seller_name TEXT")
        conn.commit()
        print("✅ Migration: seller_name ajoutée")
    except:
        pass
    conn.close()


# ==================== BASE DE DONNÉES ====================

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Utilisateurs
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            fullname TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            role TEXT DEFAULT 'client',
            active INTEGER DEFAULT 1,
            last_login TIMESTAMP,
            avatar TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table user_logs
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS user_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            ip_address TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Table order_logs (NOUVEAU - AJOUTER ICI)
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS order_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            old_status TEXT NOT NULL,
            new_status TEXT NOT NULL,
            action_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')


    # Catégories
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT,
            icon TEXT,
            order_position INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # Sous-catégories
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS subcategories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
        )
    ''')
    
    # Produits
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT,
            short_description TEXT,
            subcategory_id INTEGER,
            prix_achat REAL DEFAULT 0,
            prix_vente REAL DEFAULT 0,
            prix_promo REAL,
            stock INTEGER DEFAULT 0,
            stock_min INTEGER DEFAULT 5,
            image TEXT,
            featured INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subcategory_id) REFERENCES subcategories(id) ON DELETE SET NULL
        )
    ''')
    # Images des produits (galerie)
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS product_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            image TEXT NOT NULL,
            order_position INTEGER DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    ''')
    # Commandes
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            client_name TEXT NOT NULL,
            client_phone TEXT NOT NULL,
            client_email TEXT NOT NULL,
            client_address TEXT NOT NULL,
            items TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Fournisseurs
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            contact_person TEXT,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # Entrées stock (achats)
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS stock_in (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            supplier_id INTEGER,
            quantity INTEGER NOT NULL,
            purchase_price REAL NOT NULL,
            total REAL NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
    ''')
    
    # Sorties stock (ventes)
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS stock_out (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            client_phone TEXT NOT NULL,
            client_email TEXT,
            client_address TEXT,
            quantity INTEGER NOT NULL,
            sale_price REAL NOT NULL,
            total REAL NOT NULL,
            profit REAL NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            sale_type TEXT DEFAULT 'direct',
            order_number TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')
    try:
        execute_query(cursor,"ALTER TABLE stock_out ADD COLUMN notes TEXT")
    except:
        pass
    try:
        execute_query(cursor,"ALTER TABLE stock_out ADD COLUMN order_number TEXT")
    except:
        pass
    try:
        execute_query(cursor,"ALTER TABLE stock_out ADD COLUMN seller_id     INTEGER")
    except:
        pass

    try:
        execute_query(cursor,"ALTER TABLE stock_out ADD COLUMN seller_name TEXT")
    except:
        pass
    
    # Clients
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT UNIQUE,
            email TEXT,
            address TEXT,
            total_achats REAL DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            last_order DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Slider
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS sliders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            subtitle TEXT,
            image TEXT,
            button_text TEXT,
            button_link TEXT,
            order_position INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # Newsletter
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS newsletter (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Promotions
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS promotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            description TEXT,
            discount_type TEXT DEFAULT 'percentage',
            discount_value REAL NOT NULL,
            min_purchase REAL DEFAULT 0,
            start_date DATE,
            end_date DATE,
            usage_limit INTEGER,
            used_count INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # Avis
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            client_email TEXT,
            rating INTEGER NOT NULL,
            comment TEXT,
            approved INTEGER DEFAULT 1,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    ''')
   # Équipe
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            position TEXT NOT NULL,
            bio TEXT,
            image TEXT,
            email TEXT,
            order_position INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    ''') 

    # Paramètres
    execute_query(cursor,'''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Admin par défaut
    admin_pass = hashlib.sha256('admin123'.encode()).hexdigest()
    try:
        execute_query(cursor,"INSERT INTO users (username, password, fullname, role) VALUES (?, ?, ?, ?)", 
                      ('admin', admin_pass, 'Administrateur', 'admin'))
    except:
        pass
    
    # Catégories
    categories = [
        ('Revetements Muraux', 'revetements-muraux', 'Papiers peints, panneaux PVC', '📄', 1),
        ('Decoration', 'decoration', 'Miroirs, horloges, cadres', '🖼️', 2),
        ('Luminaires', 'luminaires', 'Lampes, suspensions', '💡', 3),
        ('Textiles', 'textiles', 'Coussins, rideaux', '🛋️', 4),
    ]
    for cat in categories:
        try:
            execute_query(cursor,"INSERT INTO categories (name, slug, description, icon, order_position) VALUES (?, ?, ?, ?, ?)", cat)
        except:
            pass
    
    # Sous-catégories
    subcategories = [
        (1, 'Papiers Peints', 'papiers-peints', 'Collection exclusive'),
        (1, 'Panneaux PVC', 'panneaux-pvc', 'Panneaux PVC - Shibord'),
        (2, 'Miroirs', 'miroirs', 'Miroirs decoratifs'),
        (2, 'Horloges', 'horloges', 'Horloges murales'),
        (3, 'Suspensions', 'suspensions', 'Suspensions modernes'),
        (4, 'Coussins', 'coussins', 'Coussins decoratifs'),
    ]
    for sub in subcategories:
        try:
            execute_query(cursor,"INSERT INTO subcategories (category_id, name, slug, description) VALUES (?, ?, ?, ?)", sub)
        except:
            pass
    
    # Produits
    products = [
        ('PVC001', 'Panneau Shibord Blanc', 'panneau-shibord-blanc', 'Panneau PVC blanc mat', '', 2, 45, 89.90, None, 50, 5, '', 1),
        ('PVC002', 'Panneau Shibord Bois', 'panneau-shibord-bois', 'Panneau PVC effet bois', '', 2, 48, 95.90, 85.90, 30, 5, '', 1),
        ('WP001', 'Papier Peint Tropical', 'papier-peint-tropical', 'Papier peint tropical', '', 1, 35, 79.90, 69.90, 40, 5, '', 1),
        ('MIR001', 'Miroir Rond Doré', 'miroir-rond-dore', 'Miroir rond finition dorée', '', 3, 120, 299.90, 249.90, 15, 3, '', 1),
        ('HOR001', 'Horloge Murale', 'horloge-murale', 'Horloge design moderne', '', 4, 45, 89.90, None, 20, 5, '', 0),
        ('LAM001', 'Suspension Industrielle', 'suspension-industrielle', 'Suspension style industriel', '', 5, 65, 149.90, 129.90, 10, 3, '', 1),
        ('COU001', 'Coussin Velours', 'coussin-velours', 'Coussin velours bleu', '', 6, 25, 49.90, 39.90, 100, 10, '', 1),
    ]
    for p in products:
        try:
            execute_query(cursor,"INSERT INTO products (reference, name, slug, description, short_description, subcategory_id, prix_achat, prix_vente, prix_promo, stock, stock_min, image, featured) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", p)
        except:
            pass
    
    # Fournisseurs
    suppliers = [
        ('Deco Import', 'Deco Import SARL', '98765432', 'contact@decoimport.com', 'Tunis', 'Mohamed Ali'),
        ('Art Mural', 'Art Mural Tunisie', '99887766', 'info@artmural.tn', 'La Marsa', 'Sonia Ben'),
    ]
    for s in suppliers:
        try:
            execute_query(cursor,"INSERT INTO suppliers (name, company, phone, email, address, contact_person) VALUES (?, ?, ?, ?, ?, ?)", s)
        except:
            pass
    
    # Paramètres
    settings = [
        ('site_name', 'New Decors'),
        ('site_description', 'Decoration d interieur de qualite'),
        ('contact_phone', '+216 70 000 000'),
        ('contact_email', 'contact@newdecors.tn'),
        ('contact_address', 'Tunis, Tunisie'),
        ('about_text', 'New Decors est votre specialiste de la decoration d interieur en Tunisie.'),
        ('hours_monday_friday', '9h - 18h'),
        ('hours_saturday', '10h - 16h'),
        ('hours_sunday', 'Fermé'),
    ]
    for key, value in settings:
        try:
            execute_query(cursor,"INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
        except:
            pass
    
    # Code promo
    try:
        execute_query(cursor,"INSERT INTO promotions (code, description, discount_type, discount_value, min_purchase, active) VALUES (?, ?, ?, ?, ?, ?)",
                      ('BIENVENUE10', '10% sur votre premiere commande', 'percentage', 10, 50, 1))
    except:
        pass
    
    conn.commit()
    conn.close()
    print("✅ Base de donnees initialisee")

def migrate_orders():
    conn = get_db()
    cursor = conn.cursor()
    try:
        execute_query(cursor,"ALTER TABLE orders ADD COLUMN stock_deducted INTEGER DEFAULT 0")
        conn.commit()
        print("✅ Migration ajoutée")
    except:
        pass
    conn.close()
def role_required(allowed_roles):
    """Décorateur pour restreindre l'accès selon le rôle"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'logged_in' not in session:
                return redirect(url_for('login'))
            if session.get('role') not in allowed_roles:
                return "Accès non autorisé - Droits insuffisants", 403
            return f(*args, **kwargs)
        return decorated
    return decorator

def admin_required(f):
    """Décorateur pour les actions réservées à l'admin"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return jsonify({'success': False, 'error': 'Action réservée à l\'administrateur'}), 403
        return f(*args, **kwargs)
    return decorated

# ==================== TEMPLATE log ====================
HTML_LOGIN = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connexion Administration - New Decors</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary: #2C1810;
            --primary-dark: #1a0f0a;
            --secondary: #C6A43F;
            --secondary-light: #D4B86A;
            --dark: #1a1a2e;
            --gray: #6c757d;
            --light: #f8f9fa;
            --white: #ffffff;
            --shadow: 0 10px 30px rgba(0,0,0,0.08);
            --shadow-hover: 0 15px 40px rgba(0,0,0,0.12);
            --transition: all 0.3s ease;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .login-container {
            width: 100%;
            max-width: 450px;
        }

        .login-card {
            background: var(--white);
            border-radius: 24px;
            padding: 40px;
            box-shadow: var(--shadow-hover);
            animation: fadeInUp 0.6s ease;
        }

        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .logo {
            text-align: center;
            margin-bottom: 30px;
        }

        .logo h1 {
            font-size: 28px;
            font-weight: 800;
            color: var(--primary);
            margin-bottom: 5px;
        }

        .logo p {
            font-size: 11px;
            color: var(--gray);
            letter-spacing: 3px;
        }

        .login-icon {
            text-align: center;
            margin-bottom: 20px;
        }

        .login-icon i {
            font-size: 60px;
            color: var(--secondary);
        }

        .login-title {
            text-align: center;
            margin-bottom: 30px;
        }

        .login-title h2 {
            font-size: 24px;
            font-weight: 700;
            color: var(--dark);
            margin-bottom: 8px;
        }

        .login-title p {
            font-size: 14px;
            color: var(--gray);
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            font-size: 13px;
            color: var(--dark);
        }

        .input-group {
            position: relative;
            display: flex;
            align-items: center;
        }

        .input-group i {
            position: absolute;
            left: 15px;
            color: var(--gray);
            font-size: 16px;
        }

        .input-group input {
            width: 100%;
            padding: 14px 15px 14px 45px;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            font-size: 14px;
            transition: var(--transition);
            font-family: inherit;
        }

        .input-group input:focus {
            outline: none;
            border-color: var(--secondary);
            box-shadow: 0 0 0 3px rgba(198, 164, 63, 0.1);
        }

        .toggle-password {
            position: absolute;
            right: 15px;
            left: auto !important;
            cursor: pointer;
            color: var(--gray);
        }

        .btn-login {
            width: 100%;
            padding: 14px;
            background: var(--secondary);
            color: var(--white);
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: var(--transition);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }

        .btn-login:hover {
            background: var(--secondary-light);
            transform: translateY(-2px);
        }

        .alert {
            padding: 12px 16px;
            border-radius: 12px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 14px;
        }

        .alert-danger {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }

        .alert-danger i {
            color: #721c24;
        }

        .alert-info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }

        .info-box {
            margin-top: 20px;
            padding: 15px;
            background: var(--light);
            border-radius: 12px;
        }

        .info-box p {
            font-size: 12px;
            color: var(--gray);
            margin-bottom: 8px;
        }

        .info-box .demo-credentials {
            font-family: monospace;
            font-size: 11px;
            color: var(--secondary);
        }

        .back-to-site {
            text-align: center;
            margin-top: 20px;
        }

        .back-to-site a {
            color: rgba(255,255,255,0.8);
            text-decoration: none;
            font-size: 14px;
            transition: var(--transition);
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .back-to-site a:hover {
            color: var(--secondary);
        }

        @media (max-width: 480px) {
            .login-card {
                padding: 30px 20px;
            }
            
            .login-title h2 {
                font-size: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-card">
            <div class="logo">
                <h1>NEW DECORS</h1>
                <p>ADMINISTRATION</p>
            </div>
            
            <div class="login-icon">
                <i class="fas fa-shield-alt"></i>
            </div>
            
            <div class="login-title">
                <h2>Espace Administration</h2>
                <p>Connectez-vous pour accéder au tableau de bord</p>
            </div>
            
            {% if error %}
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle"></i>
                {{ error }}
            </div>
            {% endif %}
            
            <form method="POST" action="/login">
                <div class="form-group">
                    <label>Nom d'utilisateur</label>
                    <div class="input-group">
                        <i class="fas fa-user"></i>
                        <input type="text" name="username" placeholder="Entrez votre nom d'utilisateur" required autofocus>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Mot de passe</label>
                    <div class="input-group">
                        <i class="fas fa-lock"></i>
                        <input type="password" name="password" id="password" placeholder="Entrez votre mot de passe" required>
                        <i class="fas fa-eye toggle-password" onclick="togglePassword()" style="cursor: pointer;"></i>
                    </div>
                </div>
                
                <button type="submit" class="btn-login">
                    <i class="fas fa-sign-in-alt"></i> Se connecter
                </button>
            </form>
            
            <div class="info-box">
                <p><i class="fas fa-info-circle"></i> Accès par rôle :</p>
                <p>👑 <strong>Administrateur</strong> : Accès total à toutes les fonctionnalités</p>
                <p>🛒 <strong>Vendeur</strong> : Accès limité (ventes, stock, commandes)</p>
                <hr style="margin: 10px 0; border-color: #e9ecef;">
                <p class="demo-credentials">Demo Admin: admin / admin123</p>
            </div>
        </div>
        
        <div class="back-to-site">
            <a href="/">
                <i class="fas fa-arrow-left"></i> Retour au site
            </a>
        </div>
    </div>
    
    <script>
        function togglePassword() {
            const passwordInput = document.getElementById('password');
            const toggleIcon = document.querySelector('.toggle-password');
            
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                toggleIcon.classList.remove('fa-eye');
                toggleIcon.classList.add('fa-eye-slash');
            } else {
                passwordInput.type = 'password';
                toggleIcon.classList.remove('fa-eye-slash');
                toggleIcon.classList.add('fa-eye');
            }
        }
    </script>
</body>
</html>
'''
# ==================== TEMPLATE ACCUEIL ====================
HTML_ABOUT = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>À propos - {{ settings.site_name }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary: #2C1810;
            --primary-dark: #1a0f0a;
            --secondary: #C6A43F;
            --secondary-light: #D4B86A;
            --dark: #1a1a2e;
            --gray: #6c757d;
            --light: #f8f9fa;
            --white: #ffffff;
            --shadow: 0 10px 30px rgba(0,0,0,0.08);
            --shadow-hover: 0 15px 40px rgba(0,0,0,0.12);
            --transition: all 0.3s ease;
        }

        body {
            font-family: 'Inter', sans-serif;
            color: var(--dark);
            line-height: 1.6;
            background: var(--white);
        }

        /* Top Bar */
        .top-bar {
            background: var(--primary-dark);
            color: var(--white);
            padding: 10px 0;
            font-size: 13px;
        }

        .top-bar .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            flex-wrap: wrap;
            gap: 10px;
        }

        .top-bar a {
            color: var(--white);
            text-decoration: none;
            margin-left: 20px;
            transition: var(--transition);
        }

        .top-bar a:hover {
            color: var(--secondary);
        }

        /* Main Header */
        .main-header {
            background: var(--white);
            padding: 15px 0;
            box-shadow: var(--shadow);
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .main-header .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            flex-wrap: wrap;
            gap: 15px;
        }

        .logo h1 {
            font-size: 24px;
            font-weight: 700;
            color: var(--primary);
        }

        .logo p {
            font-size: 10px;
            color: var(--gray);
            letter-spacing: 2px;
        }

        /* Navigation */
        .nav-menu {
            display: flex;
            gap: 25px;
            list-style: none;
        }

        .nav-item {
            position: relative;
        }

        .nav-item > a {
            text-decoration: none;
            color: var(--dark);
            font-weight: 500;
            padding: 10px 0;
            display: block;
            transition: var(--transition);
        }

        .nav-item > a:hover {
            color: var(--secondary);
        }

        .submenu {
            position: absolute;
            top: 100%;
            left: 0;
            background: var(--white);
            min-width: 220px;
            box-shadow: var(--shadow);
            border-radius: 12px;
            opacity: 0;
            visibility: hidden;
            transform: translateY(-10px);
            transition: all 0.3s ease;
            z-index: 100;
            list-style: none;
            padding: 10px 0;
        }

        .nav-item:hover .submenu {
            opacity: 1;
            visibility: visible;
            transform: translateY(0);
        }

        .submenu li a {
            display: block;
            padding: 10px 20px;
            text-decoration: none;
            color: var(--dark);
            font-size: 14px;
            transition: var(--transition);
        }

        .submenu li a:hover {
            background: var(--light);
            color: var(--secondary);
            padding-left: 25px;
        }

        .menu-toggle {
            display: none;
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: var(--primary);
        }

        .header-actions {
            display: flex;
            gap: 20px;
            align-items: center;
        }

        .cart-icon {
            position: relative;
            cursor: pointer;
            font-size: 24px;
            color: var(--primary);
        }

        .cart-count {
            position: absolute;
            top: -8px;
            right: -12px;
            background: var(--secondary);
            color: var(--white);
            font-size: 11px;
            font-weight: bold;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* Page Header */
        .page-header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: var(--white);
            padding: 80px 0;
            text-align: center;
            position: relative;
            overflow: hidden;
        }

        .page-header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 320"><path fill="rgba(255,255,255,0.05)" d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,154.7C960,171,1056,181,1152,165.3C1248,149,1344,107,1392,85.3L1440,64L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z"></path></svg>') repeat-x bottom;
            background-size: cover;
            opacity: 0.1;
        }

        .page-header h1 {
            font-size: 48px;
            margin-bottom: 15px;
            position: relative;
        }

        .page-header p {
            font-size: 18px;
            opacity: 0.9;
            position: relative;
        }

        /* About Content */
        .about-content {
            padding: 80px 0;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }

        .about-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 60px;
            align-items: center;
        }

        .about-text h2 {
            font-size: 36px;
            margin-bottom: 20px;
            color: var(--primary);
            position: relative;
            display: inline-block;
        }

        .about-text h2::after {
            content: '';
            position: absolute;
            bottom: -10px;
            left: 0;
            width: 60px;
            height: 3px;
            background: var(--secondary);
        }

        .about-text p {
            color: var(--gray);
            margin-bottom: 20px;
            line-height: 1.8;
        }

        .about-image {
            background: linear-gradient(135deg, var(--light) 0%, #fff 100%);
            border-radius: 20px;
            overflow: hidden;
            box-shadow: var(--shadow);
            text-align: center;
            padding: 40px;
        }

        .about-image i {
            font-size: 200px;
            color: var(--secondary);
        }

        /* Values Section */
        .values-section {
            background: var(--light);
            padding: 80px 0;
        }

        .section-title {
            text-align: center;
            font-size: 36px;
            margin-bottom: 15px;
            color: var(--primary);
        }

        .section-subtitle {
            text-align: center;
            color: var(--gray);
            margin-bottom: 50px;
        }

        .values-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 30px;
        }

        .value-card {
            background: var(--white);
            padding: 40px 30px;
            border-radius: 20px;
            text-align: center;
            box-shadow: var(--shadow);
            transition: var(--transition);
        }

        .value-card:hover {
            transform: translateY(-8px);
            box-shadow: var(--shadow-hover);
        }

        .value-icon {
            font-size: 48px;
            color: var(--secondary);
            margin-bottom: 20px;
        }

        .value-card h3 {
            font-size: 20px;
            margin-bottom: 15px;
        }

        .value-card p {
            color: var(--gray);
            font-size: 14px;
        }

        /* Team Section */
        .team-section {
            padding: 80px 0;
        }

        .team-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 40px;
        }

        .team-card {
            text-align: center;
            transition: var(--transition);
        }

        .team-card:hover {
            transform: translateY(-5px);
        }

        .team-image {
            width: 180px;
            height: 180px;
            background: linear-gradient(135deg, var(--light) 0%, #fff 100%);
            border-radius: 50%;
            margin: 0 auto 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            box-shadow: var(--shadow);
        }

        .team-image img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .team-image i {
            font-size: 80px;
            color: var(--secondary);
        }

        .team-card h4 {
            font-size: 20px;
            margin-bottom: 5px;
            color: var(--primary);
        }

        .team-card p {
            color: var(--gray);
            font-size: 14px;
        }

        /* CTA Section */
        .cta-section {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            padding: 60px 0;
            text-align: center;
            color: var(--white);
        }

        .cta-section h2 {
            font-size: 32px;
            margin-bottom: 15px;
        }

        .cta-section p {
            margin-bottom: 30px;
            opacity: 0.9;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 12px 30px;
            border-radius: 40px;
            text-decoration: none;
            font-weight: 600;
            transition: var(--transition);
            border: none;
            cursor: pointer;
        }

        .btn-primary {
            background: var(--secondary);
            color: var(--white);
        }

        .btn-primary:hover {
            background: var(--secondary-light);
            transform: translateY(-2px);
        }

        .btn-outline {
            border: 2px solid var(--secondary);
            color: var(--secondary);
            background: transparent;
        }

        .btn-outline:hover {
            background: var(--secondary);
            color: var(--white);
        }

        /* Footer */
        .footer {
            background: var(--primary-dark);
            color: var(--white);
            padding: 60px 0 20px;
        }

        .footer-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 40px;
            max-width: 1200px;
            margin: 0 auto 40px;
            padding: 0 20px;
        }

        .footer-col h4 {
            margin-bottom: 20px;
            font-size: 18px;
        }

        .footer-col a {
            color: rgba(255,255,255,0.7);
            text-decoration: none;
            display: block;
            margin-bottom: 10px;
            transition: var(--transition);
        }

        .footer-col a:hover {
            color: var(--secondary);
            transform: translateX(5px);
        }

        .social-links {
            display: flex;
            gap: 15px;
            margin-top: 15px;
        }

        .social-links a {
            width: 40px;
            height: 40px;
            background: rgba(255,255,255,0.1);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: var(--transition);
        }

        .social-links a:hover {
            background: var(--secondary);
            transform: translateY(-3px);
        }

        .footer-bottom {
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.1);
            font-size: 12px;
        }

        /* Cart Sidebar */
        .cart-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 2000;
            display: none;
        }

        .cart-sidebar {
            position: fixed;
            top: 0;
            right: -400px;
            width: 400px;
            height: 100%;
            background: var(--white);
            z-index: 2001;
            transition: right 0.3s ease;
            display: flex;
            flex-direction: column;
            box-shadow: -5px 0 30px rgba(0,0,0,0.1);
        }

        .cart-sidebar.open {
            right: 0;
        }

        .cart-header {
            padding: 20px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .cart-header button {
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
        }

        .cart-items {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }

        .cart-footer {
            padding: 20px;
            border-top: 1px solid #eee;
        }

        .cart-total {
            display: flex;
            justify-content: space-between;
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 20px;
        }

        /* Toast */
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #27ae60;
            color: white;
            padding: 12px 20px;
            border-radius: 10px;
            z-index: 2004;
            animation: slideIn 0.3s ease;
        }

        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        /* Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 2002;
        }

        .auth-modal {
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: var(--white);
            padding: 30px;
            border-radius: 20px;
            width: 90%;
            max-width: 420px;
            z-index: 2003;
        }

        .auth-modal.open {
            display: block;
        }

        .modal-overlay.open {
            display: block;
        }

        .form-group {
            margin-bottom: 18px;
        }

        .form-group label {
            display: block;
            margin-bottom: 6px;
            font-weight: 500;
            font-size: 13px;
        }

        .form-group input {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .menu-toggle {
                display: block;
            }

            .nav-menu {
                display: none;
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: var(--white);
                flex-direction: column;
                padding: 20px;
                gap: 15px;
                box-shadow: var(--shadow);
            }

            .nav-menu.active {
                display: flex;
            }

            .submenu {
                position: static;
                box-shadow: none;
                padding-left: 20px;
                opacity: 1;
                visibility: visible;
                transform: none;
                display: none;
            }

            .nav-item.active .submenu {
                display: block;
            }

            .about-grid {
                grid-template-columns: 1fr;
                gap: 40px;
            }

            .page-header h1 {
                font-size: 32px;
            }

            .section-title {
                font-size: 28px;
            }

            .cart-sidebar {
                width: 100%;
                right: -100%;
            }

            .values-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>

<!-- Top Bar -->
<div class="top-bar">
    <div class="container">
        <div>✨ Livraison gratuite dès 200 DNT</div>
        <div>
            <a href="/about">À propos</a>
            <a href="/contact">Contact</a>
            {% if session.client_logged_in %}
            <a href="/compte"><i class="fas fa-user-circle"></i> {{ session.client_name }}</a>
            <a href="/logout/client"><i class="fas fa-sign-out-alt"></i> Déconnexion</a>
            {% else %}
            <a href="#" onclick="showLoginModal(); return false;"><i class="fas fa-user"></i> Connexion</a>
            <a href="#" onclick="showRegisterModal(); return false;"><i class="fas fa-user-plus"></i> Inscription</a>
            {% endif %}
        </div>
    </div>
</div>

<!-- Main Header -->
<header class="main-header">
    <div class="container">
        <div class="logo">
            <h1>{{ settings.site_name }}</h1>
            <p>DÉCORATION D'INTÉRIEUR</p>
        </div>
        
        <button class="menu-toggle" onclick="toggleMobileMenu()">
            <i class="fas fa-bars"></i>
        </button>

        <ul class="nav-menu" id="navMenu">
            <li class="nav-item">
                <a href="/">Accueil</a>
            </li>
            {% for cat in categories %}
            <li class="nav-item">
                <a href="/category/{{ cat.slug }}">{{ cat.icon }} {{ cat.name }}</a>
                {% if cat.subcategories and cat.subcategories|length > 0 %}
                <ul class="submenu">
                    {% for sub in cat.subcategories %}
                    <li><a href="/subcategory/{{ sub.slug }}">{{ sub.name }}</a></li>
                    {% endfor %}
                </ul>
                {% endif %}
            </li>
            {% endfor %}
            <li class="nav-item">
                <a href="/promotions"><i class="fas fa-tag"></i> Promos</a>
            </li>
        </ul>

        <div class="header-actions">
            <div class="cart-icon" onclick="toggleCart()">
                <i class="fas fa-shopping-bag"></i>
                <span class="cart-count" id="cartCount">0</span>
            </div>
        </div>
    </div>
</header>

<!-- Page Header -->
<section class="page-header">
    <div class="container">
        <h1>À propos de nous</h1>
        <p>Découvrez notre histoire et nos valeurs</p>
    </div>
</section>

<!-- About Content -->
<section class="about-content">
    <div class="container">
        <div class="about-grid">
            <div class="about-text">
                <h2>Notre histoire</h2>
                <p>{{ about_text }}</p>
                <p>Depuis notre création, nous n'avons cessé d'innover et de proposer des produits de qualité supérieure pour embellir votre intérieur. Notre équipe passionnée sélectionne chaque pièce avec soin pour vous offrir le meilleur de la décoration.</p>
                <p>Nous croyons que chaque espace mérite d'être unique et refléter la personnalité de ses occupants. C'est pourquoi nous travaillons avec les meilleurs artisans et designers pour vous apporter des collections exclusives.</p>
            </div>
            <div class="about-image">
                <i class="fas fa-store"></i>
            </div>
        </div>
    </div>
</section>

<!-- Values Section -->
<section class="values-section">
    <div class="container">
        <h2 class="section-title">Nos valeurs</h2>
        <p class="section-subtitle">Ce qui nous anime au quotidien</p>
        <div class="values-grid">
            <div class="value-card">
                <div class="value-icon"><i class="fas fa-gem"></i></div>
                <h3>Qualité premium</h3>
                <p>Des produits sélectionnés avec soin pour leur excellence et leur durabilité</p>
            </div>
            <div class="value-card">
                <div class="value-icon"><i class="fas fa-leaf"></i></div>
                <h3>Éco-responsabilité</h3>
                <p>Engagés pour une décoration durable et respectueuse de l'environnement</p>
            </div>
            <div class="value-card">
                <div class="value-icon"><i class="fas fa-heart"></i></div>
                <h3>Passion</h3>
                <p>Amoureux de la décoration, nous partageons notre passion avec vous</p>
            </div>
            <div class="value-card">
                <div class="value-icon"><i class="fas fa-headset"></i></div>
                <h3>Service client</h3>
                <p>Une équipe dédiée à votre écoute et à votre satisfaction</p>
            </div>
        </div>
    </div>
</section>

<!-- Team Section -->
{% if team_members %}
<section class="team-section">
    <div class="container">
        <h2 class="section-title">Notre équipe</h2>
        <p class="section-subtitle">Des passionnés à votre service</p>
        <div class="team-grid">
            {% for member in team_members %}
            <div class="team-card">
                <div class="team-image">
                    {% if member.image %}
                    <img src="/uploads/medium/{{ member.image }}" alt="{{ member.name }}">
                    {% else %}
                    <i class="fas fa-user-circle"></i>
                    {% endif %}
                </div>
                <h4>{{ member.name }}</h4>
                <p>{{ member.position }}</p>
                {% if member.bio %}
                <p style="font-size: 12px; color: var(--gray); margin-top: 10px;">{{ member.bio }}</p>
                {% endif %}
                {% if member.email %}
                <small><a href="mailto:{{ member.email }}" style="color: var(--secondary); text-decoration: none;"><i class="fas fa-envelope"></i> {{ member.email }}</a></small>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
</section>
{% endif %}

<!-- CTA Section -->
<section class="cta-section">
    <div class="container">
        <h2>Prêt à transformer votre intérieur ?</h2>
        <p>Découvrez notre collection exclusive et laissez-vous inspirer</p>
        <a href="/products" class="btn btn-primary">Découvrir nos produits <i class="fas fa-arrow-right"></i></a>
    </div>
</section>

<!-- Footer -->
<footer class="footer">
    <div class="footer-grid">
        <div class="footer-col">
            <h4>{{ settings.site_name }}</h4>
            <p>{{ settings.site_description }}</p>
            <div class="social-links">
                <a href="#"><i class="fab fa-facebook-f"></i></a>
                <a href="#"><i class="fab fa-instagram"></i></a>
                <a href="#"><i class="fab fa-pinterest"></i></a>
            </div>
        </div>
        <div class="footer-col">
            <h4>Liens rapides</h4>
            <a href="/">Accueil</a>
            <a href="/products">Tous les produits</a>
            <a href="/promotions">Promotions</a>
            <a href="/about">À propos</a>
            <a href="/contact">Contact</a>
        </div>
        <div class="footer-col">
            <h4>Contact</h4>
            <a href="tel:{{ settings.contact_phone }}"><i class="fas fa-phone"></i> {{ settings.contact_phone }}</a>
            <a href="mailto:{{ settings.contact_email }}"><i class="fas fa-envelope"></i> {{ settings.contact_email }}</a>
            <p><i class="fas fa-map-marker-alt"></i> {{ settings.contact_address }}</p>
        </div>
    </div>
    <div class="footer-bottom">
        <p>&copy; 2025 {{ settings.site_name }}. Tous droits réservés.</p>
    </div>
</footer>

<!-- Cart Sidebar -->
<div class="cart-overlay" id="cartOverlay" onclick="toggleCart()"></div>
<div class="cart-sidebar" id="cartSidebar">
    <div class="cart-header">
        <h3>Mon panier</h3>
        <button onclick="toggleCart()">&times;</button>
    </div>
    <div class="cart-items" id="cartItems">
        <div style="text-align:center;padding:40px">Panier vide</div>
    </div>
    <div class="cart-footer">
        <div class="cart-total">
            <span>Total</span>
            <span id="cartTotal">0 DNT</span>
        </div>
        <button class="btn btn-primary" onclick="showCheckout()" style="width:100%">Commander</button>
    </div>
</div>

<!-- Login Modal -->
<div class="modal-overlay" id="loginOverlay" onclick="closeLoginModal()"></div>
<div class="auth-modal" id="loginModal">
    <h2 style="text-align:center;margin-bottom:20px">Connexion</h2>
    <div class="form-group">
        <label>Nom d'utilisateur</label>
        <input type="text" id="login_username">
    </div>
    <div class="form-group">
        <label>Mot de passe</label>
        <input type="password" id="login_password">
    </div>
    <button class="btn btn-primary" onclick="handleLogin()" style="width:100%">Se connecter</button>
    <p style="text-align:center;margin-top:15px">Pas de compte ? <a href="#" onclick="showRegisterModal();return false">S'inscrire</a></p>
</div>

<!-- Register Modal -->
<div class="modal-overlay" id="registerOverlay" onclick="closeRegisterModal()"></div>
<div class="auth-modal" id="registerModal">
    <h2 style="text-align:center;margin-bottom:20px">Inscription</h2>
    <div class="form-group">
        <label>Nom d'utilisateur</label>
        <input type="text" id="reg_username">
    </div>
    <div class="form-group">
        <label>Nom complet</label>
        <input type="text" id="reg_fullname">
    </div>
    <div class="form-group">
        <label>Email</label>
        <input type="email" id="reg_email">
    </div>
    <div class="form-group">
        <label>Téléphone</label>
        <input type="tel" id="reg_phone">
    </div>
    <div class="form-group">
        <label>Mot de passe</label>
        <input type="password" id="reg_password">
    </div>
    <div class="form-group">
        <label>Confirmer</label>
        <input type="password" id="reg_password2">
    </div>
    <button class="btn btn-primary" onclick="handleRegister()" style="width:100%">S'inscrire</button>
    <p style="text-align:center;margin-top:15px">Déjà un compte ? <a href="#" onclick="showLoginModal();return false">Se connecter</a></p>
</div>

<script>
let cart = [];

function loadCart() {
    let saved = localStorage.getItem('newdecors_cart');
    if (saved) cart = JSON.parse(saved);
    updateCartUI();
}

function saveCart() {
    localStorage.setItem('newdecors_cart', JSON.stringify(cart));
    updateCartUI();
}

function addToCart(id, name, price) {
    let existing = cart.find(item => item.id === id);
    if (existing) existing.quantity++;
    else cart.push({id: id, name: name, price: price, quantity: 1});
    saveCart();
    showToast(name + ' ajouté au panier');
}

function updateCartUI() {
    let count = cart.reduce((s,i) => s + i.quantity, 0);
    let cartCountElem = document.getElementById('cartCount');
    if (cartCountElem) cartCountElem.innerText = count;
    
    if (cart.length === 0) {
        document.getElementById('cartItems').innerHTML = '<div style="text-align:center;padding:40px">Panier vide</div>';
        document.getElementById('cartTotal').innerHTML = '0 DNT';
        return;
    }
    
    let total = 0;
    let html = '';
    for (let item of cart) {
        total += item.price * item.quantity;
        html += '<div class="cart-item">' +
            '<div class="cart-item-details">' +
            '<div class="cart-item-title">' + item.name + '</div>' +
            '<div class="cart-item-price">' + item.price.toFixed(2) + ' DNT</div>' +
            '<div class="cart-item-quantity">' +
            '<button class="quantity-btn" onclick="updateQuantity(' + item.id + ', -1)">-</button>' +
            '<span>' + item.quantity + '</span>' +
            '<button class="quantity-btn" onclick="updateQuantity(' + item.id + ', 1)">+</button>' +
            '<button onclick="removeItem(' + item.id + ')" style="margin-left:auto; background:none; border:none; color:#e74c3c"><i class="fas fa-trash"></i></button>' +
            '</div></div></div>';
    }
    document.getElementById('cartItems').innerHTML = html;
    document.getElementById('cartTotal').innerHTML = total.toFixed(2) + ' DNT';
}

function updateQuantity(id, delta) {
    let item = cart.find(i => i.id === id);
    if (item) {
        item.quantity += delta;
        if (item.quantity <= 0) cart = cart.filter(i => i.id !== id);
        saveCart();
    }
}

function removeItem(id) {
    cart = cart.filter(i => i.id !== id);
    saveCart();
}

function toggleCart() {
    document.getElementById('cartSidebar').classList.toggle('open');
    document.getElementById('cartOverlay').classList.toggle('open');
}

function showCheckout() {
    if (cart.length === 0) { showToast('Panier vide'); return; }
    window.location.href = '/products';
}

function showToast(msg) {
    let toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = '<i class="fas fa-check-circle"></i> ' + msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function toggleMobileMenu() {
    document.getElementById('navMenu').classList.toggle('active');
}

// Modal functions
function showLoginModal() {
    document.getElementById('loginModal').classList.add('open');
    document.getElementById('loginOverlay').classList.add('open');
}
function closeLoginModal() {
    document.getElementById('loginModal').classList.remove('open');
    document.getElementById('loginOverlay').classList.remove('open');
}
function showRegisterModal() {
    document.getElementById('registerModal').classList.add('open');
    document.getElementById('registerOverlay').classList.add('open');
}
function closeRegisterModal() {
    document.getElementById('registerModal').classList.remove('open');
    document.getElementById('registerOverlay').classList.remove('open');
}

// Auth handlers
async function handleLogin() {
    let username = document.getElementById('login_username').value;
    let password = document.getElementById('login_password').value;
    if (!username || !password) { alert('Veuillez remplir tous les champs'); return; }
    let res = await fetch('/api/client/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: username, password: password})
    });
    let data = await res.json();
    if (data.success) { location.reload(); }
    else { alert(data.error || 'Erreur de connexion'); }
}

async function handleRegister() {
    let username = document.getElementById('reg_username').value;
    let fullname = document.getElementById('reg_fullname').value;
    let email = document.getElementById('reg_email').value;
    let phone = document.getElementById('reg_phone').value;
    let password = document.getElementById('reg_password').value;
    let password2 = document.getElementById('reg_password2').value;
    if (!username || !fullname || !email || !password) { alert('Veuillez remplir tous les champs'); return; }
    if (password !== password2) { alert('Les mots de passe ne correspondent pas'); return; }
    let res = await fetch('/api/client/register', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: username, fullname: fullname, email: email, phone: phone, password: password})
    });
    let data = await res.json();
    if (data.success) {
        alert('Inscription réussie ! Connectez-vous');
        closeRegisterModal();
        showLoginModal();
    } else {
        alert(data.error || 'Erreur');
    }
}

loadCart();
</script>

<style>
.cart-item {
    display: flex;
    gap: 12px;
    padding: 12px 0;
    border-bottom: 1px solid #eee;
}
.cart-item-details {
    flex: 1;
}
.cart-item-title {
    font-weight: 600;
    font-size: 14px;
    margin-bottom: 4px;
}
.cart-item-price {
    color: var(--secondary);
    font-size: 14px;
    font-weight: 600;
}
.cart-item-quantity {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
}
.quantity-btn {
    width: 26px;
    height: 26px;
    border: 1px solid #ddd;
    background: white;
    border-radius: 5px;
    cursor: pointer;
}
</style>
</body>
</html>
'''
HTML_CHECKOUT  = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>Validation commande - {{ settings.site_name }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary: #2C1810;
            --primary-dark: #1a0f0a;
            --secondary: #C6A43F;
            --secondary-light: #D4B86A;
            --dark: #1a1a2e;
            --gray: #6c757d;
            --light: #f8f9fa;
            --white: #ffffff;
            --shadow: 0 10px 30px rgba(0,0,0,0.08);
            --shadow-hover: 0 15px 40px rgba(0,0,0,0.12);
            --transition: all 0.3s ease;
        }

        body {
            font-family: 'Inter', sans-serif;
            color: var(--dark);
            line-height: 1.6;
            background: var(--light);
        }

        /* Top Bar */
        .top-bar {
            background: var(--primary-dark);
            color: var(--white);
            padding: 10px 0;
            font-size: 13px;
        }

        .top-bar .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            flex-wrap: wrap;
            gap: 10px;
        }

        .top-bar a {
            color: var(--white);
            text-decoration: none;
            margin-left: 20px;
            transition: var(--transition);
        }

        .top-bar a:hover {
            color: var(--secondary);
        }

        /* Main Header */
        .main-header {
            background: var(--white);
            padding: 15px 0;
            box-shadow: var(--shadow);
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .main-header .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            flex-wrap: wrap;
            gap: 15px;
        }

        .logo h1 {
            font-size: 24px;
            font-weight: 700;
            color: var(--primary);
        }

        .logo p {
            font-size: 10px;
            color: var(--gray);
            letter-spacing: 2px;
        }

        .nav-menu {
            display: flex;
            gap: 25px;
            list-style: none;
        }

        .nav-item {
            position: relative;
        }

        .nav-item > a {
            text-decoration: none;
            color: var(--dark);
            font-weight: 500;
            padding: 10px 0;
            display: block;
            transition: var(--transition);
        }

        .nav-item > a:hover {
            color: var(--secondary);
        }

        .submenu {
            position: absolute;
            top: 100%;
            left: 0;
            background: var(--white);
            min-width: 220px;
            box-shadow: var(--shadow);
            border-radius: 12px;
            opacity: 0;
            visibility: hidden;
            transform: translateY(-10px);
            transition: all 0.3s ease;
            z-index: 100;
            list-style: none;
            padding: 10px 0;
        }

        .nav-item:hover .submenu {
            opacity: 1;
            visibility: visible;
            transform: translateY(0);
        }

        .submenu li a {
            display: block;
            padding: 10px 20px;
            text-decoration: none;
            color: var(--dark);
            font-size: 14px;
            transition: var(--transition);
        }

        .submenu li a:hover {
            background: var(--light);
            color: var(--secondary);
            padding-left: 25px;
        }

        .menu-toggle {
            display: none;
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: var(--primary);
        }

        .header-actions {
            display: flex;
            gap: 20px;
            align-items: center;
        }

        .cart-icon {
            position: relative;
            cursor: pointer;
            font-size: 24px;
            color: var(--primary);
        }

        .cart-count {
            position: absolute;
            top: -8px;
            right: -12px;
            background: var(--secondary);
            color: var(--white);
            font-size: 11px;
            font-weight: bold;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* Page Header */
        .page-header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: var(--white);
            padding: 60px 0;
            text-align: center;
        }

        .page-header h1 {
            font-size: 36px;
            margin-bottom: 10px;
        }

        .page-header p {
            font-size: 16px;
            opacity: 0.9;
        }

        /* Checkout Content */
        .checkout-content {
            padding: 60px 0;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }

        .checkout-grid {
            display: grid;
            grid-template-columns: 1fr 1.2fr;
            gap: 40px;
        }

        /* Order Summary */
        .order-summary {
            background: var(--white);
            border-radius: 20px;
            padding: 30px;
            box-shadow: var(--shadow);
            position: sticky;
            top: 100px;
        }

        .order-summary h2 {
            font-size: 22px;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid var(--secondary);
            color: var(--primary);
        }

        .summary-items {
            max-height: 400px;
            overflow-y: auto;
            margin-bottom: 20px;
        }

        .summary-item {
            display: flex;
            gap: 15px;
            padding: 15px 0;
            border-bottom: 1px solid #eee;
        }

        .summary-item-image {
            width: 60px;
            height: 60px;
            background: var(--light);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }

        .summary-item-image i {
            font-size: 24px;
            color: #ccc;
        }

        .summary-item-details {
            flex: 1;
        }

        .summary-item-name {
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 5px;
        }

        .summary-item-price {
            color: var(--secondary);
            font-size: 13px;
            font-weight: 600;
        }

        .summary-item-quantity {
            color: var(--gray);
            font-size: 12px;
        }

        .summary-totals {
            border-top: 2px solid #eee;
            padding-top: 20px;
        }

        .total-line {
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
            font-size: 14px;
        }

        .total-line.grand-total {
            font-size: 20px;
            font-weight: 700;
            color: var(--secondary);
            margin-top: 15px;
            padding-top: 15px;
            border-top: 2px solid var(--secondary);
        }

        /* Checkout Form */
        .checkout-form {
            background: var(--white);
            border-radius: 20px;
            padding: 30px;
            box-shadow: var(--shadow);
        }

        .checkout-form h2 {
            font-size: 22px;
            margin-bottom: 10px;
            color: var(--primary);
        }

        .form-subtitle {
            color: var(--gray);
            margin-bottom: 25px;
            font-size: 14px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            font-size: 14px;
        }

        .form-group input,
        .form-group textarea {
            width: 100%;
            padding: 12px 15px;
            border: 1px solid #ddd;
            border-radius: 10px;
            font-family: inherit;
            transition: var(--transition);
            font-size: 14px;
        }

        .form-group input:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: var(--secondary);
            box-shadow: 0 0 0 3px rgba(198, 164, 63, 0.1);
        }

        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }

        /* Promo Code */
        .promo-section {
            margin: 20px 0;
            padding: 15px;
            background: var(--light);
            border-radius: 12px;
        }

        .promo-input-group {
            display: flex;
            gap: 10px;
        }

        .promo-input-group input {
            flex: 1;
            padding: 10px 12px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
        }

        .btn-sm {
            padding: 10px 20px;
            font-size: 13px;
        }

        /* Payment Methods */
        .payment-methods {
            margin: 20px 0;
        }

        .payment-method {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 10px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: var(--transition);
        }

        .payment-method:hover {
            border-color: var(--secondary);
            background: var(--light);
        }

        .payment-method.selected {
            border-color: var(--secondary);
            background: rgba(198, 164, 63, 0.05);
        }

        .payment-method input {
            width: auto;
            margin: 0;
        }

        .payment-method label {
            margin: 0;
            cursor: pointer;
            flex: 1;
        }

        /* Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 14px 30px;
            border-radius: 40px;
            text-decoration: none;
            font-weight: 600;
            transition: var(--transition);
            border: none;
            cursor: pointer;
        }

        .btn-primary {
            background: var(--secondary);
            color: var(--white);
            width: 100%;
        }

        .btn-primary:hover {
            background: var(--secondary-light);
            transform: translateY(-2px);
        }

        .btn-outline {
            border: 2px solid var(--secondary);
            color: var(--secondary);
            background: transparent;
        }

        .btn-outline:hover {
            background: var(--secondary);
            color: var(--white);
        }

        /* Success Modal */
        .success-modal {
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: var(--white);
            padding: 40px;
            border-radius: 20px;
            text-align: center;
            z-index: 2003;
            max-width: 90%;
            width: 450px;
        }

        .success-modal.open {
            display: block;
        }

        .success-icon {
            font-size: 70px;
            color: #27ae60;
            margin-bottom: 20px;
        }

        .success-modal h3 {
            font-size: 24px;
            margin-bottom: 10px;
        }

        .success-modal p {
            color: var(--gray);
            margin-bottom: 20px;
        }

        .order-number {
            background: var(--light);
            padding: 10px;
            border-radius: 10px;
            font-family: monospace;
            font-size: 18px;
            font-weight: bold;
            margin: 15px 0;
        }

        /* Footer */
        .footer {
            background: var(--primary-dark);
            color: var(--white);
            padding: 60px 0 20px;
        }

        .footer-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 40px;
            max-width: 1200px;
            margin: 0 auto 40px;
            padding: 0 20px;
        }

        .footer-col h4 {
            margin-bottom: 20px;
            font-size: 18px;
        }

        .footer-col a {
            color: rgba(255,255,255,0.7);
            text-decoration: none;
            display: block;
            margin-bottom: 10px;
            transition: var(--transition);
        }

        .footer-col a:hover {
            color: var(--secondary);
            transform: translateX(5px);
        }

        .footer-bottom {
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.1);
            font-size: 12px;
        }

        /* Toast */
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #e74c3c;
            color: white;
            padding: 12px 20px;
            border-radius: 10px;
            z-index: 2004;
            animation: slideIn 0.3s ease;
        }

        .toast.success {
            background: #27ae60;
        }

        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        /* Responsive */
        @media (max-width: 768px) {
            .menu-toggle {
                display: block;
            }

            .nav-menu {
                display: none;
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: var(--white);
                flex-direction: column;
                padding: 20px;
                gap: 15px;
                box-shadow: var(--shadow);
            }

            .nav-menu.active {
                display: flex;
            }

            .submenu {
                position: static;
                box-shadow: none;
                padding-left: 20px;
                opacity: 1;
                visibility: visible;
                transform: none;
                display: none;
            }

            .nav-item.active .submenu {
                display: block;
            }

            .checkout-grid {
                grid-template-columns: 1fr;
                gap: 30px;
            }

            .order-summary {
                position: static;
                order: 2;
            }

            .checkout-form {
                order: 1;
            }

            .form-row {
                grid-template-columns: 1fr;
                gap: 0;
            }

            .page-header h1 {
                font-size: 28px;
            }
        }
    </style>
</head>
<body>

<!-- Top Bar -->
<div class="top-bar">
    <div class="container">
        <div>✨ Livraison gratuite dès 200 DNT</div>
        <div>
            <a href="/about">À propos</a>
            <a href="/contact">Contact</a>
            {% if session.client_logged_in %}
            <a href="/compte"><i class="fas fa-user-circle"></i> {{ session.client_name }}</a>
            <a href="/logout/client"><i class="fas fa-sign-out-alt"></i> Déconnexion</a>
            {% else %}
            <a href="#" onclick="showLoginModal(); return false;"><i class="fas fa-user"></i> Connexion</a>
            <a href="#" onclick="showRegisterModal(); return false;"><i class="fas fa-user-plus"></i> Inscription</a>
            {% endif %}
        </div>
    </div>
</div>

<!-- Main Header -->
<header class="main-header">
    <div class="container">
        <div class="logo">
            <h1>{{ settings.site_name }}</h1>
            <p>DÉCORATION D'INTÉRIEUR</p>
        </div>
        
        <button class="menu-toggle" onclick="toggleMobileMenu()">
            <i class="fas fa-bars"></i>
        </button>

        <ul class="nav-menu" id="navMenu">
            <li class="nav-item">
                <a href="/">Accueil</a>
            </li>
            {% for cat in categories %}
            <li class="nav-item">
                <a href="/category/{{ cat.slug }}">{{ cat.icon }} {{ cat.name }}</a>
                {% if cat.subcategories and cat.subcategories|length > 0 %}
                <ul class="submenu">
                    {% for sub in cat.subcategories %}
                    <li><a href="/subcategory/{{ sub.slug }}">{{ sub.name }}</a></li>
                    {% endfor %}
                </ul>
                {% endif %}
            </li>
            {% endfor %}
            <li class="nav-item">
                <a href="/promotions"><i class="fas fa-tag"></i> Promos</a>
            </li>
        </ul>

        <div class="header-actions">
            <div class="cart-icon" onclick="window.location.href='/'">
                <i class="fas fa-shopping-bag"></i>
                <span class="cart-count" id="cartCount">0</span>
            </div>
        </div>
    </div>
</header>

<!-- Page Header -->
<section class="page-header">
    <div class="container">
        <h1>Validation de commande</h1>
        <p>Vérifiez vos informations et finalisez votre achat</p>
    </div>
</section>

<!-- Checkout Content -->
<section class="checkout-content">
    <div class="container">
        <div class="checkout-grid">
            <!-- Order Summary -->
            <div class="order-summary">
                <h2>Récapitulatif</h2>
                <div class="summary-items" id="summaryItems">
                    <div style="text-align:center;padding:20px;">Chargement...</div>
                </div>
                <div class="summary-totals">
                    <div class="total-line">
                        <span>Sous-total</span>
                        <span id="subtotal">0 DNT</span>
                    </div>
                    <div class="total-line" id="discountLine" style="display:none;">
                        <span>Réduction</span>
                        <span id="discountAmount" style="color:#e74c3c;">0 DNT</span>
                    </div>
                    <div class="total-line grand-total">
                        <span>Total</span>
                        <span id="grandTotal">0 DNT</span>
                    </div>
                </div>
            </div>

            <!-- Checkout Form -->
            <div class="checkout-form">
                <h2>Informations de livraison</h2>
                <p class="form-subtitle">Veuillez remplir tous les champs obligatoires</p>

                <form id="checkoutForm">
                    <div class="form-group">
                        <label>Nom complet *</label>
                        <input type="text" id="fullname" required                     placeholder="Votre nom et prénom"
                               value="{{ client_info.name if client_info.name else '' }}">
                        {% if client_info.name %}
                        <small style="color: #27ae60; display: block; margin-top: 5px;">
                            <i class="fas fa-check-circle"></i> Récupéré depuis votre compte
                        </small>
                        {% endif %}
                    </div>

                    <div class="form-group">
                        <label>Téléphone *</label>
                        <input type="tel" id="phone" required placeholder="Votre numéro de téléphone"
                               value="{{ client_info.phone if client_info.phone else '' }}"
                               pattern="[0-9]{8,}"
                               title="Le numéro de téléphone doit contenir au moins 8 chiffres"
                               oninput="this.value = this.value.replace(/[^0-9]/g, '')">
                        {% if client_info.phone %}
                        <small style="color: #27ae60; display: block; margin-top: 5px;">
                            <i class="fas fa-check-circle"></i> Récupéré depuis votre compte
                        </small>
                        {% endif %}
                        <small style="color: #666; display: block; margin-top: 5px;">🔒 Uniquement des chiffres (minimum 8)</small>
                    </div>

                    <div class="form-group">
                        <label>Adresse de livraison *</label>
                        <textarea id="address" rows="3" required placeholder="Votre adresse complète"></textarea>
                    </div>

                    <!-- Promo Code -->
                    <div class="promo-section">
                        <div class="promo-input-group">
                            <input type="text" id="promoCode" placeholder="Code promo">
                            <button type="button" class="btn btn-outline btn-sm" onclick="applyPromo()">Appliquer</button>
                        </div>
                        <div id="promoMessage" style="font-size:12px; margin-top:8px;"></div>
                    </div>

                    <!-- Payment Methods -->
                    <div class="payment-methods">
                        <div class="payment-method selected" onclick="selectPayment('cash')">
                            <input type="radio" name="payment" value="cash" checked>                            <label>💰 Paiement à la livraison</label>
                        </div>
                    </div>

                    <button type="submit" class="btn btn-primary" id="submitBtn">
                        <i class="fas fa-check-circle"></i> Confirmer la commande
                    </button>
                </form>
            </div>
        </div>
    </div>
</section>

<!-- Success Modal -->
<div id="successModal" class="success-modal">
    <div class="success-icon">
        <i class="fas fa-check-circle"></i>
    </div>
    <h3>Commande confirmée !</h3>
    <p>Merci pour votre commande. Voici votre numéro de suivi :</p>
    <div class="order-number" id="orderNumber"></div>
    <p>Un email de confirmation vous a été envoyé.</p>
    <button class="btn btn-primary" onclick="continueShopping()">Continuer mes achats</button>
</div>
<div id="modalOverlay" style="display:none; position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.5); z-index:2002;" onclick="closeModal()"></div>

<!-- Footer -->
<footer class="footer">
    <div class="footer-grid">
        <div class="footer-col">
            <h4>{{ settings.site_name }}</h4>
            <p style="color:rgba(255,255,255,0.7);">Décoration d'intérieur haut de gamme</p>
        </div>
        <div class="footer-col">
            <h4>Liens utiles</h4>
            <a href="/">Accueil</a>
            <a href="/promotions">Promotions</a>
            <a href="/about">À propos</a>
            <a href="/contact">Contact</a>
        </div>
        <div class="footer-col">
            <h4>Contact</h4>
            <a href="mailto:{{ settings.contact_email }}">{{ settings.contact_email }}</a>
            <a href="tel:{{ settings.contact_phone }}">{{ settings.contact_phone }}</a>
        </div>
    </div>
    <div class="footer-bottom">
        <p>&copy; 2024 {{ settings.site_name }} - Tous droits réservés</p>
    </div>
</footer>

<script>
    let cart = [];
    let appliedPromo = null;
    let discounts = {};

    // Load cart from localStorage
    function loadCart() {
        const savedCart = localStorage.getItem('newdecors_cart');
        if (savedCart) {
            cart = JSON.parse(savedCart);
        }
        updateCartCount();
        displayOrderSummary();
    }

    // Update cart count in header
    function updateCartCount() {
        const count = cart.reduce((sum, item) => sum + item.quantity, 0);
        document.getElementById('cartCount').textContent = count;
    }

    // Display order summary
    function displayOrderSummary() {
        const container = document.getElementById('summaryItems');
        if (!container) return;

        if (cart.length === 0) {
            container.innerHTML = '<div style="text-align:center;padding:20px;">Votre panier est vide</div>';
            document.getElementById('subtotal').textContent = '0 DNT';
            document.getElementById('grandTotal').textContent = '0 DNT';
            return;
        }

        let html = '';
        let subtotal = 0;

        cart.forEach(item => {
            const itemTotal = item.price * item.quantity;
            subtotal += itemTotal;
            html += `
                <div class="summary-item">
                    <div class="summary-item-image">
                        <i class="fas fa-gift"></i>
                    </div>
                    <div class="summary-item-details">
                        <div class="summary-item-name">${escapeHtml(item.name)}</div>
                        <div class="summary-item-price">${item.price.toFixed(2)} DNT</div>
                        <div class="summary-item-quantity">Quantité: ${item.quantity}</div>
                    </div>
                    <div class="summary-item-total">
                        <strong>${itemTotal.toFixed(2)} DNT</strong>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
        updateTotals(subtotal);
    }

    // Update totals with discount
    function updateTotals(subtotal) {
        let discountAmount = 0;
        let discountLine = document.getElementById('discountLine');
        let discountAmountSpan = document.getElementById('discountAmount');

        if (appliedPromo && discounts[appliedPromo]) {
            const discount = discounts[appliedPromo];
            if (discount.type === 'percentage') {
                discountAmount = subtotal * (discount.value / 100);
            } else if (discount.type === 'fixed') {
                discountAmount = discount.value;
            }
            discountAmount = Math.min(discountAmount, subtotal);
            
            if (discountLine) {
                discountLine.style.display = 'flex';
                discountAmountSpan.textContent = discountAmount.toFixed(2) + ' DNT';
            }
        } else if (discountLine) {
            discountLine.style.display = 'none';
        }

        const total = subtotal - discountAmount;
        document.getElementById('subtotal').textContent = subtotal.toFixed(2) + ' DNT';
        document.getElementById('grandTotal').textContent = total.toFixed(2) + ' DNT';
    }

    // Apply promo code
    async function applyPromo() {
        const promoCode = document.getElementById('promoCode').value.trim();
        const promoMessage = document.getElementById('promoMessage');
        
        if (!promoCode) {
            promoMessage.innerHTML = '<span style="color:#e74c3c;">Veuillez entrer un code promo</span>';
            return;
        }

        try {
            const response = await fetch('/api/validate-promo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code: promoCode })
            });
            const data = await response.json();
            
            if (data.valid) {
                appliedPromo = promoCode;
                discounts[promoCode] = data.discount;
                promoMessage.innerHTML = '<span style="color:#27ae60;">✓ Code promo appliqué !</span>';
                
                // Recalculate totals
                const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
                updateTotals(subtotal);
            } else {
                promoMessage.innerHTML = '<span style="color:#e74c3c;">Code promo invalide</span>';
            }
        } catch (error) {
            promoMessage.innerHTML = '<span style="color:#e74c3c;">Erreur lors de la validation</span>';
        }
    }

    // Select payment method
    function selectPayment(method) {
        const methods = document.querySelectorAll('.payment-method');
        methods.forEach(m => m.classList.remove('selected'));
        event.currentTarget.classList.add('selected');
        const radio = event.currentTarget.querySelector('input[type="radio"]');
        if (radio) radio.checked = true;
    }

// Submit order
document.getElementById('checkoutForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const fullname = document.getElementById('fullname').value.trim();
    const phone = document.getElementById('phone').value.trim();
    const address = document.getElementById('address').value.trim();
    const paymentMethod = 'cash'; // Toujours paiement à la livraison
    
    // Validation du téléphone (uniquement chiffres)
    if (!phone.match(/^[0-9]{8,}$/)) {
        showToast('Le numéro de téléphone doit contenir au moins 8 chiffres', 'error');
        return;
    }
    
    if (!fullname || !phone || !address) {
        showToast('Veuillez remplir tous les champs obligatoires', 'error');
        return;
    }
    
    if (cart.length === 0) {
        showToast('Votre panier est vide', 'error');
        return;
    }
    
    const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    let discountAmount = 0;
    if (appliedPromo && discounts[appliedPromo]) {
        const discount = discounts[appliedPromo];
        if (discount.type === 'percentage') {
            discountAmount = subtotal * (discount.value / 100);
        } else if (discount.type === 'fixed') {
            discountAmount = discount.value;
        }
        discountAmount = Math.min(discountAmount, subtotal);
    }
    const total = subtotal - discountAmount;
    
    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Traitement en cours...';
    
    try {
        const response = await fetch('/api/checkout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                client_name: fullname,
                client_phone: phone,
                client_email: '',  // Plus d'email requis
                client_address: address,
                items: cart,
                total: total,
                payment_method: paymentMethod,
                promo_code: appliedPromo,
                discount_amount: discountAmount
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('orderNumber').textContent = data.order_number;
            document.getElementById('successModal').classList.add('open');
            document.getElementById('modalOverlay').style.display = 'block';
            
            // Vider le panier
            localStorage.removeItem('newdecors_cart');
            cart = [];
            updateCartCount();
            displayOrderSummary();
        } else {
            showToast(data.error || 'Erreur lors de la commande', 'error');
        }
    } catch (error) {
        showToast('Erreur de connexion au serveur', 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-check-circle"></i> Confirmer la commande';
    }
});    
    // Helper functions
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    function showToast(message, type = 'error') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
    
    function continueShopping() {
        closeModal();
        window.location.href = '/';
    }
    
    function closeModal() {
        document.getElementById('successModal').classList.remove('open');
        document.getElementById('modalOverlay').style.display = 'none';
    }
    
    function toggleMobileMenu() {
        const menu = document.getElementById('navMenu');
        menu.classList.toggle('active');
    }
    
    // Login/Register modal functions
    function showLoginModal() {
        // Implement login modal
        window.location.href = '/login';
    }
    
    function showRegisterModal() {
        window.location.href = '/register';
    }
    
    // Initialize page
    loadCart();
</script>
</body>
</html>
'''
HTML_COMPTE = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>Mon compte - {{ settings.site_name }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --primary: #FF69B4;
            --primary-dark: #DB2777;
            --primary-light: #FCE7F3;
            --secondary: #A855F7;
            --secondary-light: #C084FC;
            --dark: #1A1A2E;
            --gray: #6B6B7B;
            --gray-light: #FDF2F8;
            --white: #FFFFFF;
            --white-smoke: #FFF5F7;
            --shadow: 0 10px 30px rgba(0,0,0,0.08);
            --shadow-md: 0 5px 20px rgba(0,0,0,0.1);
            --transition: all 0.3s ease;
        }
        
        body { 
            font-family: 'Inter', sans-serif; 
            color: var(--dark); 
            background: var(--white-smoke);
        }
        
        /* Top Bar */
        .top-bar { 
            background: linear-gradient(135deg, #FF69B4 0%, #DB2777 50%, #A855F7 100%);
            color: white; 
            padding: 10px 0; 
            font-size: 13px;
        }
        .top-bar .container { 
            display: flex; 
            justify-content: space-between; 
            max-width: 1400px; 
            margin: 0 auto; 
            padding: 0 30px;
            flex-wrap: wrap;
            gap: 10px;
        }
        .top-bar a { 
            color: white; 
            text-decoration: none; 
            margin-left: 20px; 
            transition: var(--transition);
        }
        .top-bar a:hover { color: var(--primary-light); }
        
        /* Main Header */
        .main-header { 
            background: var(--white); 
            padding: 15px 0; 
            box-shadow: var(--shadow); 
            position: sticky; 
            top: 0; 
            z-index: 1000;
        }
        .main-header .container { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            max-width: 1400px; 
            margin: 0 auto; 
            padding: 0 30px; 
            flex-wrap: wrap; 
            gap: 15px;
        }
        .logo h1 { 
            font-size: 24px; 
            font-weight: 800;
            background: linear-gradient(135deg, #FF69B4 0%, #DB2777 50%, #A855F7 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .logo p { font-size: 10px; color: var(--gray); letter-spacing: 2px; }
        
        .nav-menu { display: flex; gap: 25px; list-style: none; flex-wrap: wrap; }
        .nav-item { position: relative; }
        .nav-item > a { 
            text-decoration: none; 
            color: var(--dark); 
            font-weight: 500; 
            transition: var(--transition);
        }
        .nav-item > a:hover { color: #DB2777; }
        
        .submenu { 
            position: absolute; 
            top: 100%; 
            left: 0; 
            background: var(--white); 
            min-width: 220px; 
            box-shadow: var(--shadow-md); 
            border-radius: 12px; 
            opacity: 0; 
            visibility: hidden; 
            transform: translateY(-10px); 
            transition: all 0.3s ease; 
            list-style: none; 
            padding: 10px 0; 
            z-index: 100;
        }
        .nav-item:hover .submenu { opacity: 1; visibility: visible; transform: translateY(0); }
        .submenu li a { 
            display: block; 
            padding: 10px 20px; 
            text-decoration: none; 
            color: var(--dark); 
            font-size: 14px; 
            transition: var(--transition);
        }
        .submenu li a:hover { background: var(--gray-light); color: #DB2777; padding-left: 25px; }
        
        .menu-toggle { display: none; background: none; border: none; font-size: 24px; cursor: pointer; color: #DB2777; }
        .header-actions { display: flex; gap: 20px; }
        .cart-icon { position: relative; cursor: pointer; font-size: 24px; color: #DB2777; }
        .cart-count { 
            position: absolute; 
            top: -8px; 
            right: -12px; 
            background: linear-gradient(135deg, #FF69B4, #DB2777);
            color: white; 
            font-size: 11px; 
            width: 18px; 
            height: 18px; 
            border-radius: 50%; 
            display: flex; 
            align-items: center; 
            justify-content: center;
        }
        
        /* Page Header */
        .page-header { 
            background: linear-gradient(135deg, #FF69B4 0%, #DB2777 50%, #A855F7 100%);
            color: white; 
            padding: 60px 0; 
            text-align: center;
        }
        .page-header h1 { font-size: 36px; margin-bottom: 10px; }
        .page-header p { opacity: 0.9; }
        
        /* Account Section */
        .account-section { padding: 60px 0; }
        .container { max-width: 1400px; margin: 0 auto; padding: 0 30px; }
        .account-grid { display: grid; grid-template-columns: 300px 1fr; gap: 40px; }
        
        @media (max-width: 992px) {
            .account-grid { grid-template-columns: 1fr; gap: 30px; }
        }
        
        /* Sidebar */
        .account-sidebar { 
            background: var(--white); 
            border-radius: 20px; 
            padding: 25px; 
            box-shadow: var(--shadow); 
            height: fit-content; 
            position: sticky; 
            top: 100px;
        }
        .user-avatar { text-align: center; margin-bottom: 25px; }
        .user-avatar i { font-size: 70px; color: #FF69B4; }
        .user-avatar h3 { margin-top: 10px; font-size: 18px; color: #DB2777; }
        .user-avatar p { color: var(--gray); font-size: 13px; }
        
        .sidebar-menu { list-style: none; }
        .sidebar-menu li { margin-bottom: 8px; }
        .sidebar-menu a { 
            display: flex; 
            align-items: center; 
            gap: 12px; 
            padding: 12px 18px; 
            text-decoration: none; 
            color: var(--dark); 
            border-radius: 12px; 
            transition: var(--transition);
            font-weight: 500;
        }
        .sidebar-menu a:hover, .sidebar-menu a.active { 
            background: linear-gradient(135deg, #FF69B4, #DB2777);
            color: white; 
        }
        .sidebar-menu a i { width: 22px; }
        
        /* Content Cards */
        .account-card { 
            background: var(--white); 
            border-radius: 20px; 
            padding: 30px; 
            box-shadow: var(--shadow); 
            margin-bottom: 30px;
        }
        .card-title { 
            font-size: 22px; 
            margin-bottom: 25px; 
            padding-bottom: 15px; 
            border-bottom: 2px solid #FF69B4; 
            color: #DB2777; 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        /* Info Grid */
        .info-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
        @media (max-width: 768px) { .info-grid { grid-template-columns: 1fr; } }
        
        .info-item { 
            padding: 12px 0; 
            border-bottom: 1px solid var(--gray-light);
        }
        .info-label { font-weight: 600; color: var(--gray); font-size: 13px; margin-bottom: 5px; }
        .info-value { font-size: 16px; font-weight: 500; color: var(--dark); }
        
        /* Orders Table */
        .orders-table { width: 100%; border-collapse: collapse; }
        .orders-table th, .orders-table td { 
            padding: 14px 12px; 
            text-align: left; 
            border-bottom: 1px solid var(--gray-light);
        }
        .orders-table th { 
            background: linear-gradient(135deg, #FF69B4, #DB2777);
            color: white;
            font-weight: 600;
            border-radius: 12px 12px 0 0;
        }
        .orders-table tr:hover td { background: var(--gray-light); }
        
        .status-badge { 
            padding: 5px 14px; 
            border-radius: 30px; 
            font-size: 12px; 
            font-weight: 600;
            display: inline-block;
        }
        .status-pending { background: #FFF3E0; color: #E65100; }
        .status-confirmed { background: #E3F2FD; color: #1565C0; }
        .status-shipped { background: #E8F5E9; color: #2E7D32; }
        .status-delivered { background: #E8F5E9; color: #2E7D32; }
        .status-cancelled { background: #FFEBEE; color: #C62828; }
        
        .btn-cancel { 
            background: #FFEBEE; 
            color: #C62828; 
            border: none; 
            padding: 6px 14px; 
            border-radius: 30px; 
            cursor: pointer; 
            font-size: 12px;
            font-weight: 600;
            transition: var(--transition);
        }
        .btn-cancel:hover { background: #C62828; color: white; }
        
        /* Products Grid for Reviews */
        .bought-products { 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); 
            gap: 25px; 
            margin-top: 20px;
        }
        .bought-product { 
            background: var(--white-smoke); 
            border-radius: 16px; 
            padding: 20px; 
            text-align: center;
            transition: var(--transition);
            border: 1px solid rgba(255,105,180,0.2);
        }
        .bought-product:hover { transform: translateY(-5px); box-shadow: var(--shadow-md); }
        
        .bought-product-image { 
            width: 120px; 
            height: 120px; 
            background: white; 
            border-radius: 12px; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            margin: 0 auto 15px; 
            overflow: hidden;
        }
        .bought-product-image img { width: 100%; height: 100%; object-fit: cover; }
        .bought-product-name { font-weight: 700; font-size: 15px; margin-bottom: 10px; color: #DB2777; }
        
        .review-stars { margin: 12px 0; }
        .review-stars i { color: #FF69B4; font-size: 18px; cursor: pointer; transition: var(--transition); margin: 0 2px; }
        .review-stars i:hover { transform: scale(1.15); }
        
        .review-textarea { 
            width: 100%; 
            margin-top: 12px; 
            padding: 10px; 
            border: 1px solid var(--gray-light); 
            border-radius: 12px; 
            font-size: 12px; 
            display: none;
            font-family: inherit;
        }
        .review-textarea:focus { outline: none; border-color: #FF69B4; }
        
        .btn-review { 
            background: linear-gradient(135deg, #FF69B4, #DB2777);
            color: white; 
            border: none; 
            padding: 8px 20px; 
            border-radius: 30px; 
            cursor: pointer; 
            font-size: 13px; 
            font-weight: 600;
            margin-top: 12px;
            transition: var(--transition);
        }
        .btn-review:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(255,105,180,0.4); }
        
        /* Buttons */
        .btn { 
            display: inline-flex; 
            align-items: center; 
            gap: 8px; 
            padding: 10px 24px; 
            border-radius: 40px; 
            text-decoration: none; 
            font-weight: 600; 
            transition: var(--transition); 
            border: none; 
            cursor: pointer;
        }
        .btn-primary { background: linear-gradient(135deg, #FF69B4, #DB2777); color: white; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(255,105,180,0.4); }
        .btn-outline { border: 2px solid #FF69B4; color: #DB2777; background: transparent; }
        .btn-outline:hover { background: #FF69B4; color: white; }
        
        /* Footer */
        .footer { 
            background: linear-gradient(135deg, var(--dark) 0%, #1A1A2E 100%);
            color: white; 
            padding: 60px 0 20px; 
            margin-top: 60px;
            position: relative;
        }
        .footer::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #FF69B4, #DB2777, #A855F7);
        }
        .footer-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 40px; 
            max-width: 1400px; 
            margin: 0 auto 40px; 
            padding: 0 30px;
        }
        .footer-col h4 { 
            margin-bottom: 20px; 
            font-size: 18px;
            color: #FF69B4;
        }
        .footer-col a { 
            color: rgba(255,255,255,0.7); 
            text-decoration: none; 
            display: block; 
            margin-bottom: 10px; 
            transition: var(--transition);
        }
        .footer-col a:hover { color: #FF69B4; transform: translateX(5px); }
        .footer-bottom { text-align: center; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.1); font-size: 12px; }
        
        /* Table responsive */
        .table-responsive { overflow-x: auto; -webkit-overflow-scrolling: touch; }
        
        @media (max-width: 768px) {
            .menu-toggle { display: block; }
            .nav-menu { 
                display: none; 
                position: absolute; 
                top: 100%; 
                left: 0; 
                right: 0; 
                background: white; 
                flex-direction: column; 
                padding: 20px; 
                box-shadow: var(--shadow-md);
                z-index: 999;
            }
            .nav-menu.active { display: flex; }
            .submenu { position: static; box-shadow: none; padding-left: 20px; opacity: 1; visibility: visible; transform: none; display: none; }
            .nav-item.active .submenu { display: block; }
            .account-sidebar { position: static; }
            .orders-table th, .orders-table td { padding: 10px 8px; font-size: 12px; }
            .container, .main-header .container, .top-bar .container { padding: 0 20px; }
            .page-header h1 { font-size: 28px; }
            .card-title { font-size: 18px; flex-direction: column; align-items: flex-start; }
        }
        
        @media (max-width: 576px) {
            .bought-products { grid-template-columns: 1fr; }
            .info-grid { grid-template-columns: 1fr; }
            .account-card { padding: 20px; }
        }
        
        .text-center { text-align: center; }
        .text-success { color: #2E7D32; }
        .text-danger { color: #C62828; }
        .mt-3 { margin-top: 15px; }
        .mb-3 { margin-bottom: 15px; }
    </style>
</head>
<body>

<!-- Top Bar -->
<div class="top-bar">
    <div class="container">
        <div>✨ Livraison gratuite dès 200 DNT</div>
        <div>
            <a href="/about">À propos</a>
            <a href="/contact">Contact</a>
            <a href="/compte"><i class="fas fa-user-circle"></i> {{ session.client_name }}</a>
            <a href="/logout/client"><i class="fas fa-sign-out-alt"></i> Déconnexion</a>
        </div>
    </div>
</div>

<!-- Main Header -->
<header class="main-header">
    <div class="container">
        <div class="logo">
            <h1>{{ settings.site_name }}</h1>
            <p>DÉCORATION D'INTÉRIEUR</p>
        </div>
        <button class="menu-toggle" onclick="toggleMobileMenu()"><i class="fas fa-bars"></i></button>
        <ul class="nav-menu" id="navMenu">
            <li class="nav-item"><a href="/">Accueil</a></li>
            {% for cat in categories %}
            <li class="nav-item">
                <a href="/category/{{ cat.slug }}">{{ cat.icon }} {{ cat.name }}</a>
                {% if cat.subcategories %}
                <ul class="submenu">
                    {% for sub in cat.subcategories %}
                    <li><a href="/subcategory/{{ sub.slug }}">{{ sub.name }}</a></li>
                    {% endfor %}
                </ul>
                {% endif %}
            </li>
            {% endfor %}
            <li class="nav-item"><a href="/promotions"><i class="fas fa-tag"></i> Promos</a></li>
        </ul>
        <div class="header-actions">
            <div class="cart-icon" onclick="window.location.href='/'"><i class="fas fa-shopping-bag"></i><span class="cart-count" id="cartCount">0</span></div>
        </div>
    </div>
</header>

<!-- Page Header -->
<section class="page-header">
    <div class="container">
        <h1>Mon compte</h1>
        <p>Gérez vos commandes et donnez votre avis</p>
    </div>
</section>

<!-- Account Section -->
<section class="account-section">
    <div class="container">
        <div class="account-grid">
            <!-- Sidebar -->
            <aside class="account-sidebar">
                <div class="user-avatar">
                    <i class="fas fa-user-circle"></i>
                    <h3>{{ client.fullname }}</h3>
                    <p>{{ client.email }}</p>
                </div>
                <ul class="sidebar-menu">
                    <li><a href="#" onclick="showTab('info')" id="tabInfoBtn" class="active"><i class="fas fa-user"></i> Mes informations</a></li>
                    <li><a href="#" onclick="showTab('orders')" id="tabOrdersBtn"><i class="fas fa-shopping-bag"></i> Mes commandes</a></li>
                    <li><a href="#" onclick="showTab('reviews')" id="tabReviewsBtn"><i class="fas fa-star"></i> Mes avis</a></li>
                </ul>
            </aside>
            
            <!-- Content -->
            <div class="account-content">
                <!-- Tab Informations -->
                <div id="tabInfo" class="account-card">
                    <div class="card-title">
                        <span><i class="fas fa-user"></i> Mes informations personnelles</span>
                        
                    </div>
                    <div class="info-grid">
                        <div class="info-item"><div class="info-label">Nom complet</div><div class="info-value" id="infoName">{{ client.fullname }}</div></div>
                        <div class="info-item"><div class="info-label">Email</div><div class="info-value" id="infoEmail">{{ client.email }}</div></div>
                        <div class="info-item"><div class="info-label">Téléphone</div><div class="info-value" id="infoPhone">{{ client.phone or 'Non renseigné' }}</div></div>
                        <div class="info-item"><div class="info-label">Membre depuis</div><div class="info-value">{{ client.created_at.split()[0] if client.created_at else 'N/A' }}</div></div>
                    </div>
                </div>
                
                <!-- Tab Commandes -->
                <div id="tabOrders" class="account-card" style="display: none;">
                    <div class="card-title"><span><i class="fas fa-shopping-bag"></i> Mes commandes</span></div>
                    {% if orders %}
                    <div class="table-responsive">
                        <table class="orders-table">
                            <thead>
                                <tr>
                                    <th>N° commande</th>
                                    <th>Date</th>
                                    <th>Total</th>
                                    <th>Statut</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for order in orders %}
                                <tr>
                                    <td><strong>{{ order.order_number }}</strong></td>
                                    <td>{{ order.date.split()[0] }}</td>
                                    <td class="text-success">{{ "%.2f"|format(order.total) }} DNT</td>
                                    <td><span class="status-badge status-{{ order.status }}">{{ order.status }}</span></td>
                                    <td>
                                        <button class="btn-cancel" onclick="viewOrderDetails('{{ order.order_number }}')">📋 Détails</button>
                                        {% if order.status == 'pending' %}
                                        <button class="btn-cancel" onclick="cancelOrder('{{ order.order_number }}')" style="background:#C62828; color:white; margin-left:8px;">❌ Annuler</button>
                                        {% endif %}
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                    {% else %}
                    <div class="text-center" style="padding: 40px;">
                        <i class="fas fa-shopping-bag" style="font-size: 48px; color: #FF69B4; opacity: 0.5;"></i>
                        <p style="margin-top: 15px; color: var(--gray);">Vous n'avez pas encore passé de commande</p>
                        <a href="/products" class="btn btn-primary" style="margin-top: 15px;">Découvrir nos produits</a>
                    </div>
                    {% endif %}
                </div>
                
                <!-- Tab Avis -->
                <div id="tabReviews" class="account-card" style="display: none;">
                    <div class="card-title"><span><i class="fas fa-star"></i> Produits à évaluer</span></div>
                    <p style="margin-bottom: 20px; color: var(--gray);">Notez les produits que vous avez achetés pour aider les autres clients</p>
                    
                    {% if products_bought %}
                    <div class="bought-products">
                        {% for product in products_bought %}
                        <div class="bought-product" id="product-{{ product.id }}">
                            <div class="bought-product-image">
                                {% if product.image %}
                                <img src="/uploads/medium/{{ product.image }}" alt="{{ product.name }}">
                                {% else %}
                                <i class="fas fa-image" style="font-size: 40px; color: #ccc;"></i>
                                {% endif %}
                            </div>
                            <div class="bought-product-name">{{ product.name }}</div>
                            <div class="review-stars" data-product-id="{{ product.id }}" data-reviewed="{{ 'true' if product.id in reviewed_products else 'false' }}">
                                {% for i in range(1,6) %}
                                <i class="far fa-star" data-rating="{{ i }}" onclick="setRating(this, {{ product.id }}, {{ i }})"></i>
                                {% endfor %}
                            </div>
                            <textarea class="review-textarea" id="review-{{ product.id }}" placeholder="Votre avis sur ce produit..."></textarea>
                            <button class="btn-review" onclick="submitReview({{ product.id }})">
                                {% if product.id in reviewed_products %}Modifier mon avis{% else %}Donner mon avis{% endif %}
                            </button>
                        </div>
                        {% endfor %}
                    </div>
                    {% else %}
                    <div class="text-center" style="padding: 40px;">
                        <i class="fas fa-shopping-bag" style="font-size: 48px; color: #FF69B4; opacity: 0.5;"></i>
                        <p style="margin-top: 15px; color: var(--gray);">Aucun produit acheté pour le moment</p>
                        <a href="/products" class="btn btn-primary" style="margin-top: 15px;">Découvrir nos produits</a>
                    </div>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>
</section>

<!-- Footer -->
<footer class="footer">
    <div class="footer-grid">
        <div class="footer-col"><h4>{{ settings.site_name }}</h4><p>{{ settings.site_description }}</p></div>
        <div class="footer-col"><h4>Liens rapides</h4><a href="/">Accueil</a><a href="/products">Tous les produits</a><a href="/promotions">Promotions</a></div>
        <div class="footer-col"><h4>Contact</h4><a href="mailto:{{ settings.contact_email }}">{{ settings.contact_email }}</a><a href="tel:{{ settings.contact_phone }}">{{ settings.contact_phone }}</a></div>
    </div>
    <div class="footer-bottom"><p>&copy; 2025 {{ settings.site_name }}. Tous droits réservés.</p></div>
</footer>

<script>
let cart = [];
function loadCart() { 
    let saved = localStorage.getItem('newdecors_cart'); 
    if (saved) cart = JSON.parse(saved); 
    document.getElementById('cartCount').innerText = cart.reduce((s,i)=>s+i.quantity,0);
}
loadCart();

function toggleMobileMenu() { 
    document.getElementById('navMenu').classList.toggle('active'); 
}

let currentTab = 'info';
function showTab(tab) {
    document.getElementById('tabInfo').style.display = tab === 'info' ? 'block' : 'none';
    document.getElementById('tabOrders').style.display = tab === 'orders' ? 'block' : 'none';
    document.getElementById('tabReviews').style.display = tab === 'reviews' ? 'block' : 'none';
    document.querySelectorAll('.sidebar-menu a').forEach(a => a.classList.remove('active'));
    if (tab === 'info') document.getElementById('tabInfoBtn').classList.add('active');
    if (tab === 'orders') document.getElementById('tabOrdersBtn').classList.add('active');
    if (tab === 'reviews') document.getElementById('tabReviewsBtn').classList.add('active');
    currentTab = tab;
}

function setRating(element, productId, rating) {
    const starsContainer = document.querySelector(`.review-stars[data-product-id="${productId}"]`);
    const stars = starsContainer.querySelectorAll('i');
    stars.forEach((star, index) => {
        if (index < rating) {
            star.className = 'fas fa-star';
        } else {
            star.className = 'far fa-star';
        }
    });
    starsContainer.setAttribute('data-rating', rating);
}

function submitReview(productId) {
    const starsContainer = document.querySelector(`.review-stars[data-product-id="${productId}"]`);
    const rating = starsContainer.getAttribute('data-rating');
    const comment = document.getElementById(`review-${productId}`).value;
    
    if (!rating || rating === 'false') {
        alert('Veuillez sélectionner une note');
        return;
    }
    
    fetch('/api/submit-review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId, rating: parseInt(rating), comment: comment })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            alert('Merci pour votre avis !');
            location.reload();
        } else {
            alert('Erreur: ' + (data.error || 'Inconnue'));
        }
    });
}

function viewOrderDetails(orderNumber) {
    window.open(`/order/${orderNumber}`, '_blank');
}

function cancelOrder(orderNumber) {
    if (confirm('Annuler cette commande ?')) {
        fetch(`/api/cancel-order/${orderNumber}`, { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Commande annulée');
                    location.reload();
                } else {
                    alert('Erreur: ' + (data.error || 'Inconnue'));
                }
            });
    }
}

function editInfo() {
    window.location.href = '/compte/edit';
}

// Afficher le premier onglet par défaut
showTab('info');
</script>
</body>
</html>
'''
HTML_CONTACT = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contact - {{ settings.site_name }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary: #2C1810;
            --primary-dark: #1a0f0a;
            --secondary: #C6A43F;
            --secondary-light: #D4B86A;
            --dark: #1a1a2e;
            --gray: #6c757d;
            --light: #f8f9fa;
            --white: #ffffff;
            --shadow: 0 10px 30px rgba(0,0,0,0.08);
            --shadow-hover: 0 15px 40px rgba(0,0,0,0.12);
            --transition: all 0.3s ease;
        }

        body {
            font-family: 'Inter', sans-serif;
            color: var(--dark);
            line-height: 1.6;
            background: var(--white);
        }

        /* Top Bar */
        .top-bar {
            background: var(--primary-dark);
            color: var(--white);
            padding: 10px 0;
            font-size: 13px;
        }

        .top-bar .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            flex-wrap: wrap;
            gap: 10px;
        }

        .top-bar a {
            color: var(--white);
            text-decoration: none;
            margin-left: 20px;
            transition: var(--transition);
        }

        .top-bar a:hover {
            color: var(--secondary);
        }

        /* Main Header */
        .main-header {
            background: var(--white);
            padding: 15px 0;
            box-shadow: var(--shadow);
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .main-header .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            flex-wrap: wrap;
            gap: 15px;
        }

        .logo h1 {
            font-size: 24px;
            font-weight: 700;
            color: var(--primary);
        }

        .logo p {
            font-size: 10px;
            color: var(--gray);
            letter-spacing: 2px;
        }

        /* Navigation */
        .nav-menu {
            display: flex;
            gap: 25px;
            list-style: none;
        }

        .nav-item {
            position: relative;
        }

        .nav-item > a {
            text-decoration: none;
            color: var(--dark);
            font-weight: 500;
            padding: 10px 0;
            display: block;
            transition: var(--transition);
        }

        .nav-item > a:hover {
            color: var(--secondary);
        }

        .submenu {
            position: absolute;
            top: 100%;
            left: 0;
            background: var(--white);
            min-width: 220px;
            box-shadow: var(--shadow);
            border-radius: 12px;
            opacity: 0;
            visibility: hidden;
            transform: translateY(-10px);
            transition: all 0.3s ease;
            z-index: 100;
            list-style: none;
            padding: 10px 0;
        }

        .nav-item:hover .submenu {
            opacity: 1;
            visibility: visible;
            transform: translateY(0);
        }

        .submenu li a {
            display: block;
            padding: 10px 20px;
            text-decoration: none;
            color: var(--dark);
            font-size: 14px;
            transition: var(--transition);
        }

        .submenu li a:hover {
            background: var(--light);
            color: var(--secondary);
            padding-left: 25px;
        }

        .menu-toggle {
            display: none;
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: var(--primary);
        }

        .header-actions {
            display: flex;
            gap: 20px;
            align-items: center;
        }

        .cart-icon {
            position: relative;
            cursor: pointer;
            font-size: 24px;
            color: var(--primary);
        }

        .cart-count {
            position: absolute;
            top: -8px;
            right: -12px;
            background: var(--secondary);
            color: var(--white);
            font-size: 11px;
            font-weight: bold;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* Page Header */
        .page-header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: var(--white);
            padding: 80px 0;
            text-align: center;
            position: relative;
            overflow: hidden;
        }

        .page-header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 320"><path fill="rgba(255,255,255,0.05)" d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,154.7C960,171,1056,181,1152,165.3C1248,149,1344,107,1392,85.3L1440,64L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z"></path></svg>') repeat-x bottom;
            background-size: cover;
            opacity: 0.1;
        }

        .page-header h1 {
            font-size: 48px;
            margin-bottom: 15px;
            position: relative;
        }

        .page-header p {
            font-size: 18px;
            opacity: 0.9;
            position: relative;
        }

        /* Contact Content */
        .contact-content {
            padding: 80px 0;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }

        .contact-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 60px;
        }

        /* Contact Info */
        .contact-info h2 {
            font-size: 32px;
            margin-bottom: 15px;
            color: var(--primary);
            position: relative;
            display: inline-block;
        }

        .contact-info h2::after {
            content: '';
            position: absolute;
            bottom: -10px;
            left: 0;
            width: 60px;
            height: 3px;
            background: var(--secondary);
        }

        .contact-info > p {
            color: var(--gray);
            margin: 25px 0 30px;
        }

        .info-list {
            margin: 30px 0;
        }

        .info-item {
            display: flex;
            align-items: flex-start;
            gap: 20px;
            padding: 20px 0;
            border-bottom: 1px solid #eee;
            transition: var(--transition);
        }

        .info-item:hover {
            transform: translateX(5px);
        }

        .info-icon {
            width: 55px;
            height: 55px;
            background: linear-gradient(135deg, var(--light) 0%, #fff 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            color: var(--secondary);
        }

        .info-details h3 {
            font-size: 18px;
            margin-bottom: 5px;
        }

        .info-details p, .info-details a {
            color: var(--gray);
            text-decoration: none;
            transition: var(--transition);
        }

        .info-details a:hover {
            color: var(--secondary);
        }

        /* Map */
        .map-container {
            margin-top: 30px;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: var(--shadow);
        }

        .map-container iframe {
            width: 100%;
            height: 300px;
            border: none;
        }

        /* Contact Form */
        .contact-form {
            background: var(--white);
            padding: 40px;
            border-radius: 20px;
            box-shadow: var(--shadow);
        }

        .contact-form h2 {
            font-size: 28px;
            margin-bottom: 10px;
            color: var(--primary);
        }

        .contact-form > p {
            color: var(--gray);
            margin-bottom: 30px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
        }

        .form-group input,
        .form-group textarea {
            width: 100%;
            padding: 12px 15px;
            border: 1px solid #ddd;
            border-radius: 10px;
            font-family: inherit;
            transition: var(--transition);
        }

        .form-group input:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: var(--secondary);
            box-shadow: 0 0 0 3px rgba(198, 164, 63, 0.1);
        }

        .btn-submit {
            background: var(--secondary);
            color: var(--white);
            border: none;
            padding: 14px 30px;
            border-radius: 40px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: var(--transition);
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }

        .btn-submit:hover {
            background: var(--secondary-light);
            transform: translateY(-2px);
        }

        /* Success Message */
        .success-message {
            background: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: none;
            align-items: center;
            gap: 10px;
        }

        /* Footer */
        .footer {
            background: var(--primary-dark);
            color: var(--white);
            padding: 60px 0 20px;
        }

        .footer-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 40px;
            max-width: 1200px;
            margin: 0 auto 40px;
            padding: 0 20px;
        }

        .footer-col h4 {
            margin-bottom: 20px;
            font-size: 18px;
        }

        .footer-col a {
            color: rgba(255,255,255,0.7);
            text-decoration: none;
            display: block;
            margin-bottom: 10px;
            transition: var(--transition);
        }

        .footer-col a:hover {
            color: var(--secondary);
            transform: translateX(5px);
        }

        .social-links {
            display: flex;
            gap: 15px;
            margin-top: 15px;
        }

        .social-links a {
            width: 40px;
            height: 40px;
            background: rgba(255,255,255,0.1);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: var(--transition);
        }

        .social-links a:hover {
            background: var(--secondary);
            transform: translateY(-3px);
        }

        .footer-bottom {
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.1);
            font-size: 12px;
        }

        /* Cart Sidebar */
        .cart-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 2000;
            display: none;
        }

        .cart-sidebar {
            position: fixed;
            top: 0;
            right: -400px;
            width: 400px;
            height: 100%;
            background: var(--white);
            z-index: 2001;
            transition: right 0.3s ease;
            display: flex;
            flex-direction: column;
            box-shadow: -5px 0 30px rgba(0,0,0,0.1);
        }

        .cart-sidebar.open {
            right: 0;
        }

        .cart-header {
            padding: 20px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .cart-header button {
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
        }

        .cart-items {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }

        .cart-footer {
            padding: 20px;
            border-top: 1px solid #eee;
        }

        .cart-total {
            display: flex;
            justify-content: space-between;
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 20px;
        }

        /* Toast */
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #27ae60;
            color: white;
            padding: 12px 20px;
            border-radius: 10px;
            z-index: 2004;
            animation: slideIn 0.3s ease;
        }

        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        /* Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 2002;
        }

        .auth-modal {
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: var(--white);
            padding: 30px;
            border-radius: 20px;
            width: 90%;
            max-width: 420px;
            z-index: 2003;
        }

        .auth-modal.open {
            display: block;
        }

        .modal-overlay.open {
            display: block;
        }

        .form-group {
            margin-bottom: 18px;
        }

        .form-group label {
            display: block;
            margin-bottom: 6px;
            font-weight: 500;
            font-size: 13px;
        }

        .form-group input {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .menu-toggle {
                display: block;
            }

            .nav-menu {
                display: none;
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: var(--white);
                flex-direction: column;
                padding: 20px;
                gap: 15px;
                box-shadow: var(--shadow);
            }

            .nav-menu.active {
                display: flex;
            }

            .submenu {
                position: static;
                box-shadow: none;
                padding-left: 20px;
                opacity: 1;
                visibility: visible;
                transform: none;
                display: none;
            }

            .nav-item.active .submenu {
                display: block;
            }

            .contact-grid {
                grid-template-columns: 1fr;
                gap: 40px;
            }

            .page-header h1 {
                font-size: 32px;
            }

            .contact-form {
                padding: 25px;
            }

            .cart-sidebar {
                width: 100%;
                right: -100%;
            }
        }
    </style>
</head>
<body>

<!-- Top Bar -->
<div class="top-bar">
    <div class="container">
        <div>✨ Livraison gratuite dès 200 DNT</div>
        <div>
            <a href="/about">À propos</a>
            <a href="/contact">Contact</a>
            {% if session.client_logged_in %}
            <a href="/compte"><i class="fas fa-user-circle"></i> {{ session.client_name }}</a>
            <a href="/logout/client"><i class="fas fa-sign-out-alt"></i> Déconnexion</a>
            {% else %}
            <a href="#" onclick="showLoginModal(); return false;"><i class="fas fa-user"></i> Connexion</a>
            <a href="#" onclick="showRegisterModal(); return false;"><i class="fas fa-user-plus"></i> Inscription</a>
            {% endif %}
        </div>
    </div>
</div>

<!-- Main Header -->
<header class="main-header">
    <div class="container">
        <div class="logo">
            <h1>{{ settings.site_name }}</h1>
            <p>DÉCORATION D'INTÉRIEUR</p>
        </div>
        
        <button class="menu-toggle" onclick="toggleMobileMenu()">
            <i class="fas fa-bars"></i>
        </button>

        <ul class="nav-menu" id="navMenu">
            <li class="nav-item">
                <a href="/">Accueil</a>
            </li>
            {% for cat in categories %}
            <li class="nav-item">
                <a href="/category/{{ cat.slug }}">{{ cat.icon }} {{ cat.name }}</a>
                {% if cat.subcategories and cat.subcategories|length > 0 %}
                <ul class="submenu">
                    {% for sub in cat.subcategories %}
                    <li><a href="/subcategory/{{ sub.slug }}">{{ sub.name }}</a></li>
                    {% endfor %}
                </ul>
                {% endif %}
            </li>
            {% endfor %}
            <li class="nav-item">
                <a href="/promotions"><i class="fas fa-tag"></i> Promos</a>
            </li>
        </ul>

        <div class="header-actions">
            <div class="cart-icon" onclick="toggleCart()">
                <i class="fas fa-shopping-bag"></i>
                <span class="cart-count" id="cartCount">0</span>
            </div>
        </div>
    </div>
</header>

<!-- Page Header -->
<section class="page-header">
    <div class="container">
        <h1>Contactez-nous</h1>
        <p>Nous sommes à votre écoute</p>
    </div>
</section>

<!-- Contact Content -->
<section class="contact-content">
    <div class="container">
        <div class="contact-grid">
            <!-- Contact Info -->
            <div class="contact-info">
                <h2>Nos coordonnées</h2>
                <p>N'hésitez pas à nous contacter pour toute question ou demande d'information. Notre équipe vous répondra dans les plus brefs délais.</p>
                
                <div class="info-list">
                    <div class="info-item">
                        <div class="info-icon"><i class="fas fa-phone-alt"></i></div>
                        <div class="info-details">
                            <h3>Téléphone</h3>
                            <a href="tel:{{ settings.contact_phone }}">{{ settings.contact_phone }}</a>
                        </div>
                    </div>

                    <div class="info-item">
                        <div class="info-icon"><i class="fas fa-envelope"></i></div>
                        <div class="info-details">
                            <h3>Email</h3>
                            <a href="mailto:{{ settings.contact_email }}">{{ settings.contact_email }}</a>
                        </div>
                    </div>

                    <div class="info-item">
                        <div class="info-icon"><i class="fas fa-map-marker-alt"></i></div>
                        <div class="info-details">
                            <h3>Adresse</h3>
                            <p>{{ settings.contact_address }}</p>
                        </div>
                    </div>
                    
                    <div class="info-item">
                        <div class="info-icon"><i class="fas fa-clock"></i></div>
                        <div class="info-details">
                            <h3>Horaires d'ouverture</h3>
                            <p>Lundi - Vendredi: {{ settings.hours_monday_friday }}</p>
                            <p>Samedi: {{ settings.hours_saturday }}</p>
                            <p>Dimanche: {{ settings.hours_sunday }}</p>
                        </div>
                    </div>
                </div>
                
                <!-- Map -->
                <div class="map-container">
                    <iframe src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3194.5678901234567!2d10.1815316!3d36.8064948!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x12fd337f5e7e2b9f%3A0x4f2c6f5e8b2c4a1d!2sTunis%2C%20Tunisie!5e0!3m2!1sfr!2stn!4v1700000000000!5m2!1sfr!2stn" allowfullscreen="" loading="lazy"></iframe>
                </div>
            </div>
            
            <!-- Contact Form -->
            <div class="contact-form">
                <h2>Envoyez-nous un message</h2>
                <p>Nous vous répondrons dans les plus brefs délais.</p>
                
                <div id="successMessage" class="success-message">
                    <i class="fas fa-check-circle"></i> Votre message a été envoyé avec succès !
                </div>
                
                <form id="contactForm">
                    <div class="form-group">
                        <label>Nom complet</label>
                        <input type="text" id="contact_name" required placeholder="Votre nom">
                    </div>
                    
                    <div class="form-group">
                        <label>Email</label>
                        <input type="email" id="contact_email" required placeholder="votre@email.com">
                    </div>
                    
                    <div class="form-group">
                        <label>Téléphone</label>
                        <input type="tel" id="contact_phone" placeholder="Votre téléphone">
                    </div>
                    
                    <div class="form-group">
                        <label>Message</label>
                        <textarea id="contact_message" rows="5" required placeholder="Votre message..."></textarea>
                    </div>
                    
                    <button type="submit" class="btn-submit">
                        <i class="fas fa-paper-plane"></i> Envoyer le message
                    </button>
                </form>
            </div>
        </div>
    </div>
</section>

<!-- Footer -->
<footer class="footer">
    <div class="footer-grid">
        <div class="footer-col">
            <h4>{{ settings.site_name }}</h4>
            <p>{{ settings.site_description }}</p>
            <div class="social-links">
                <a href="#"><i class="fab fa-facebook-f"></i></a>
                <a href="#"><i class="fab fa-instagram"></i></a>
                <a href="#"><i class="fab fa-pinterest"></i></a>
            </div>
        </div>
        <div class="footer-col">
            <h4>Liens rapides</h4>
            <a href="/">Accueil</a>
            <a href="/products">Tous les produits</a>
            <a href="/promotions">Promotions</a>
            <a href="/about">À propos</a>
            <a href="/contact">Contact</a>
        </div>
        <div class="footer-col">
            <h4>Contact</h4>
            <a href="tel:{{ settings.contact_phone }}"><i class="fas fa-phone"></i> {{ settings.contact_phone }}</a>
            <a href="mailto:{{ settings.contact_email }}"><i class="fas fa-envelope"></i> {{ settings.contact_email }}</a>
            <p><i class="fas fa-map-marker-alt"></i> {{ settings.contact_address }}</p>
        </div>
    </div>
    <div class="footer-bottom">
        <p>&copy; 2025 {{ settings.site_name }}. Tous droits réservés.</p>
    </div>
</footer>

<!-- Cart Sidebar -->
<div class="cart-overlay" id="cartOverlay" onclick="toggleCart()"></div>
<div class="cart-sidebar" id="cartSidebar">
    <div class="cart-header">
        <h3>Mon panier</h3>
        <button onclick="toggleCart()">&times;</button>
    </div>
    <div class="cart-items" id="cartItems">
        <div style="text-align:center;padding:40px">Panier vide</div>
    </div>
    <div class="cart-footer">
        <div class="cart-total">
            <span>Total</span>
            <span id="cartTotal">0 DNT</span>
        </div>
        <button class="btn btn-primary" onclick="showCheckout()" style="width:100%">Commander</button>
    </div>
</div>

<!-- Login Modal -->
<div class="modal-overlay" id="loginOverlay" onclick="closeLoginModal()"></div>
<div class="auth-modal" id="loginModal">
    <h2 style="text-align:center;margin-bottom:20px">Connexion</h2>
    <div class="form-group">
        <label>Nom d'utilisateur</label>
        <input type="text" id="login_username">
    </div>
    <div class="form-group">
        <label>Mot de passe</label>
        <input type="password" id="login_password">
    </div>
    <button class="btn btn-primary" onclick="handleLogin()" style="width:100%">Se connecter</button>
    <p style="text-align:center;margin-top:15px">Pas de compte ? <a href="#" onclick="showRegisterModal();return false">S'inscrire</a></p>
</div>

<!-- Register Modal -->
<div class="modal-overlay" id="registerOverlay" onclick="closeRegisterModal()"></div>
<div class="auth-modal" id="registerModal">
    <h2 style="text-align:center;margin-bottom:20px">Inscription</h2>
    <div class="form-group">
        <label>Nom d'utilisateur</label>
        <input type="text" id="reg_username">
    </div>
    <div class="form-group">
        <label>Nom complet</label>
        <input type="text" id="reg_fullname">
    </div>
    <div class="form-group">
        <label>Email</label>
        <input type="email" id="reg_email">
    </div>
    <div class="form-group">
        <label>Téléphone</label>
        <input type="tel" id="reg_phone">
    </div>
    <div class="form-group">
        <label>Mot de passe</label>
        <input type="password" id="reg_password">
    </div>
    <div class="form-group">
        <label>Confirmer</label>
        <input type="password" id="reg_password2">
    </div>
    <button class="btn btn-primary" onclick="handleRegister()" style="width:100%">S'inscrire</button>
    <p style="text-align:center;margin-top:15px">Déjà un compte ? <a href="#" onclick="showLoginModal();return false">Se connecter</a></p>
</div>

<script>
let cart = [];

function loadCart() {
    let saved = localStorage.getItem('newdecors_cart');
    if (saved) cart = JSON.parse(saved);
    updateCartUI();
}

function saveCart() {
    localStorage.setItem('newdecors_cart', JSON.stringify(cart));
    updateCartUI();
}

function addToCart(id, name, price) {
    let existing = cart.find(item => item.id === id);
    if (existing) existing.quantity++;
    else cart.push({id: id, name: name, price: price, quantity: 1});
    saveCart();
    showToast(name + ' ajouté au panier');
}

function updateCartUI() {
    let count = cart.reduce((s,i) => s + i.quantity, 0);
    let cartCountElem = document.getElementById('cartCount');
    if (cartCountElem) cartCountElem.innerText = count;
    
    if (cart.length === 0) {
        document.getElementById('cartItems').innerHTML = '<div style="text-align:center;padding:40px">Panier vide</div>';
        document.getElementById('cartTotal').innerHTML = '0 DNT';
        return;
    }
    
    let total = 0;
    let html = '';
    for (let item of cart) {
        total += item.price * item.quantity;
        html += '<div class="cart-item">' +
            '<div class="cart-item-details">' +
            '<div class="cart-item-title">' + item.name + '</div>' +
            '<div class="cart-item-price">' + item.price.toFixed(2) + ' DNT</div>' +
            '<div class="cart-item-quantity">' +
            '<button class="quantity-btn" onclick="updateQuantity(' + item.id + ', -1)">-</button>' +
            '<span>' + item.quantity + '</span>' +
            '<button class="quantity-btn" onclick="updateQuantity(' + item.id + ', 1)">+</button>' +
            '<button onclick="removeItem(' + item.id + ')" style="margin-left:auto; background:none; border:none; color:#e74c3c"><i class="fas fa-trash"></i></button>' +
            '</div></div></div>';
    }
    document.getElementById('cartItems').innerHTML = html;
    document.getElementById('cartTotal').innerHTML = total.toFixed(2) + ' DNT';
}

function updateQuantity(id, delta) {
    let item = cart.find(i => i.id === id);
    if (item) {
        item.quantity += delta;
        if (item.quantity <= 0) cart = cart.filter(i => i.id !== id);
        saveCart();
    }
}

function removeItem(id) {
    cart = cart.filter(i => i.id !== id);
    saveCart();
}

function toggleCart() {
    document.getElementById('cartSidebar').classList.toggle('open');
    document.getElementById('cartOverlay').classList.toggle('open');
}

function showCheckout() {
    if (cart.length === 0) { showToast('Panier vide'); return; }
    window.location.href = '/products';
}

function showToast(msg) {
    let toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = '<i class="fas fa-check-circle"></i> ' + msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function toggleMobileMenu() {
    document.getElementById('navMenu').classList.toggle('active');
}

// Modal functions
function showLoginModal() {
    document.getElementById('loginModal').classList.add('open');
    document.getElementById('loginOverlay').classList.add('open');
}
function closeLoginModal() {
    document.getElementById('loginModal').classList.remove('open');
    document.getElementById('loginOverlay').classList.remove('open');
}
function showRegisterModal() {
    document.getElementById('registerModal').classList.add('open');
    document.getElementById('registerOverlay').classList.add('open');
}
function closeRegisterModal() {
    document.getElementById('registerModal').classList.remove('open');
    document.getElementById('registerOverlay').classList.remove('open');
}

// Auth handlers
async function handleLogin() {
    let username = document.getElementById('login_username').value;
    let password = document.getElementById('login_password').value;
    if (!username || !password) { alert('Veuillez remplir tous les champs'); return; }
    let res = await fetch('/api/client/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: username, password: password})
    });
    let data = await res.json();
    if (data.success) { location.reload(); }
    else { alert(data.error || 'Erreur de connexion'); }
}

async function handleRegister() {
    let username = document.getElementById('reg_username').value;
    let fullname = document.getElementById('reg_fullname').value;
    let email = document.getElementById('reg_email').value;
    let phone = document.getElementById('reg_phone').value;
    let password = document.getElementById('reg_password').value;
    let password2 = document.getElementById('reg_password2').value;
    
    // Validation du nom
    if (!username || !fullname || !email || !password) { 
        alert('Veuillez remplir tous les champs'); 
        return; 
    }
    
    // Validation du mot de passe (8 caractères minimum + au moins 1 chiffre)
    if (password.length < 8) {
        alert('Le mot de passe doit contenir au moins 8 caractères');
        return;
    }
    
    // Vérifier si le mot de passe contient au moins un chiffre
    if (!/\d/.test(password)) {
        alert('Le mot de passe doit contenir au moins un chiffre');
        return;
    }
    
    // Validation du téléphone (minimum 8 chiffres)
    let phoneDigits = phone.replace(/\D/g, ''); // Enlever tous les caractères non numériques
    if (phoneDigits.length < 8) {
        alert('Le numéro de téléphone doit contenir au moins 8 chiffres');
        return;
    }
    
    // Vérifier que les mots de passe correspondent
    if (password !== password2) { 
        alert('Les mots de passe ne correspondent pas'); 
        return; 
    }
    
    let res = await fetch('/api/client/register', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            username: username, 
            fullname: fullname, 
            email: email, 
            phone: phoneDigits, // Envoyer uniquement les chiffres
            password: password
        })
    });
    let data = await res.json();
    if (data.success) {
        alert('Inscription réussie ! Connectez-vous');
        closeRegisterModal();
        showLoginModal();
    } else {
        alert(data.error || 'Erreur');
    }
}
// Contact form
document.getElementById('contactForm').addEventListener('submit', function(e) {
    e.preventDefault();
    let name = document.getElementById('contact_name').value;
    let successMsg = document.getElementById('successMessage');
    successMsg.style.display = 'flex';
    this.reset();
    setTimeout(() => {
        successMsg.style.display = 'none';
    }, 5000);
});

loadCart();
</script>

<style>
.cart-item {
    display: flex;
    gap: 12px;
    padding: 12px 0;
    border-bottom: 1px solid #eee;
}
.cart-item-details {
    flex: 1;
}
.cart-item-title {
    font-weight: 600;
    font-size: 14px;
    margin-bottom: 4px;
}
.cart-item-price {
    color: var(--secondary);
    font-size: 14px;
    font-weight: 600;
}
.cart-item-quantity {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
}
.quantity-btn {
    width: 26px;
    height: 26px;
    border: 1px solid #ddd;
    background: white;
    border-radius: 5px;
    cursor: pointer;
}
.btn-primary {
    background: var(--secondary);
    color: var(--white);
    border: none;
    padding: 12px;
    border-radius: 40px;
    font-weight: 600;
    cursor: pointer;
    transition: var(--transition);
}
.btn-primary:hover {
    background: var(--secondary-light);
    transform: translateY(-2px);
}
</style>
</body>
</html>
'''

HTML_PRINT_STOCK = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Rapport des ventes - NEW DECORS</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Courier New', monospace; padding: 20px; background: white; }
        .header { text-align: center; margin-bottom: 30px; border-bottom: 2px solid #333; padding-bottom: 15px; }
        .header h1 { font-size: 24px; margin-bottom: 5px; }
        .header p { font-size: 12px; color: #666; margin: 3px 0; }
        .filters-info { background: #f5f5f5; padding: 10px; margin-bottom: 20px; font-size: 12px; border: 1px solid #ddd; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 11px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f2f2f2; font-weight: bold; }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
        .totals { background: #f5f5f5; padding: 15px; margin-top: 20px; border: 1px solid #ddd; }
        .footer { text-align: center; margin-top: 30px; padding-top: 10px; border-top: 1px solid #ddd; font-size: 10px; color: #999; }
        .signature { margin-top: 40px; display: flex; justify-content: space-between; }
        .signature div { width: 200px; text-align: center; border-top: 1px solid #333; padding-top: 5px; font-size: 11px; }
        @media print { body { padding: 10px; } .no-print { display: none; } }
        .btn-print-page, .btn-close { padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin: 10px; }
        .btn-print-page { background: #3498db; color: white; }
        .btn-close { background: #e74c3c; color: white; }
    </style>
</head>
<body>
    <div class="header">
        <h1>NEW DECORS</h1>
        <p>Rapport des ventes</p>
        <p>{{ now.strftime('%d/%m/%Y à %H:%M') }}</p>
    </div>
    
    <div class="filters-info">
        <strong>Période:</strong> Du {{ start_date or 'Début' }} au {{ end_date or "Aujourd'hui" }}<br>
        <strong>Type:</strong> {{ sale_type }}<br>
        <strong>Nombre de ventes:</strong> {{ sales|length }}
    </div>
    
    <table>
        <thead>
            <tr>
                <th>Date</th>
                <th>Type</th>
                <th>Produit</th>
                <th>Client</th>
                <th>Tél</th>
                <th class="text-center">Qté</th>
                <th class="text-right">Total</th>
                <th class="text-right">Bénéfice</th>
                <th>Vendeur</th>
            </tr>
        </thead>
        <tbody>
            {% for sale in sales %}
            <tr>
                <td>{% if sale.date %}{{ sale.date.strftime('%Y-%m-%d') if sale.date is not string else sale.date.split()[0] }}{% else %}-{% endif %}</td>
                <td>{{ '📦 En ligne' if sale.sale_type == 'order' else '🛒 Caisse' }}</td>
                <td>{{ sale.product_name or '-' }}</td>
                <td>{{ sale.client_name or '-' }}</td>
                <td>{{ sale.client_phone or '-' }}</td>
                <td class="text-center">{{ sale.quantity }}</td>
                <td class="text-right">{{ "%.2f"|format(sale.total) }} DNT</td>
                <td class="text-right">{{ "%.2f"|format(sale.profit) }} DNT</td>
                <td>{{ sale.seller_name or '-' }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    
    <div class="totals">
        <strong>📊 RÉCAPITULATIF</strong><br>
        • Total articles vendus: {{ total_quantity }}<br>
        • Chiffre d'affaires total: {{ "%.2f"|format(total_revenue) }} DNT<br>
        • Bénéfice total: {{ "%.2f"|format(total_profit) }} DNT<br>
        • Marge moyenne: {{ "%.1f"|format((total_profit / total_revenue * 100) if total_revenue > 0 else 0) }}%
    </div>
    
    <div class="signature">
        <div>Signature du client</div>
        <div>Cachet et signature</div>
    </div>
    
    <div class="footer">
        Document généré par NEW DECORS - Système de gestion
    </div>
    
    <div class="no-print" style="text-align: center; margin-top: 20px;">
        <button class="btn-print-page" onclick="window.print()">🖨️ Imprimer</button>
        <button class="btn-close" onclick="window.close()">❌ Fermer</button>
    </div>
</body>
</html>
'''
# ======= ROUTES FLASK ====================

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()
    
    execute_query(cursor,"SELECT * FROM categories WHERE active=1 ORDER BY order_position")
    categories = cursor.fetchall()
    
    # Récupérer les sous-catégories pour chaque catégorie
    for cat in categories:
        execute_query(cursor,"SELECT * FROM subcategories WHERE category_id=? ORDER BY name", (cat['id'],))
        cat['subcategories'] = cursor.fetchall()
    
    execute_query(cursor,"SELECT * FROM sliders WHERE active=1 ORDER BY order_position")
    sliders = cursor.fetchall()
    
    execute_query(cursor,"SELECT * FROM products WHERE active=1 AND prix_promo IS NOT NULL AND prix_promo > 0 ORDER BY created_at DESC LIMIT 6")
    promo_products = cursor.fetchall()
    
    execute_query(cursor,"SELECT * FROM products WHERE active=1 ORDER BY created_at DESC LIMIT 8")
    new_products = cursor.fetchall()
    
    execute_query(cursor,"SELECT key, value FROM settings")
    settings_rows = cursor.fetchall()
    settings = {row['key']: row['value'] for row in settings_rows}
    
    conn.close()
    
    return render_template('index.html',
                                  categories=categories,
                                  sliders=sliders,
                                  products=new_products,
                                  promo_products=promo_products, 
                                  new_products=new_products,
                                  settings=settings)

@app.route('/admin')
@login_required
def admin():
    if session.get('role') == 'client':
        return redirect(url_for('index'))
    
    # Récupérer le nom complet ou le nom d'utilisateur
    username = session.get('fullname') or session.get('username', 'Administrateur')
    
    return render_template('admin.html', username=username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            return render_template_string(HTML_LOGIN, error="Veuillez remplir tous les champs")
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # === LOGS DE DEBUG ===
        import sys
        print(f"=== DEBUG LOGIN ===", file=sys.stderr)
        print(f"Username: {username}", file=sys.stderr)
        print(f"Password hash: {hashed_password}", file=sys.stderr)
        
        conn = get_db()
        cursor = conn.cursor()
        
        DATABASE_URL = os.environ.get('DATABASE_URL')
        print(f"DATABASE_URL existe: {DATABASE_URL is not None}", file=sys.stderr)
        
        if DATABASE_URL:
            cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s AND active=1", (username, hashed_password))
        else:
            cursor.execute("SELECT * FROM users WHERE username=? AND password=? AND active=1", (username, hashed_password))
        
        user = cursor.fetchone()
        print(f"User trouvé: {user is not None}", file=sys.stderr)
        
        if user:
            print(f"User ID: {user.get('id')}, Role: {user.get('role')}", file=sys.stderr)
        else:
            # Vérifions si l'utilisateur existe au moins
            if DATABASE_URL:
                cursor.execute("SELECT username, active FROM users WHERE username=%s", (username,))
            else:
                cursor.execute("SELECT username, active FROM users WHERE username=?", (username,))
            user_check = cursor.fetchone()
            if user_check:
                print(f"L'utilisateur {username} existe (active={user_check.get('active')}) mais mot de passe incorrect", file=sys.stderr)
            else:
                print(f"L'utilisateur {username} n'existe pas dans la base", file=sys.stderr)
        
        conn.close()
        
        if user:
            # Enregistrer la connexion dans les logs
            conn = get_db()
            cursor = conn.cursor()
            execute_query(cursor, """
                INSERT INTO user_logs (user_id, action, ip_address)
                VALUES (%s, %s, %s)
            """, (user['id'], 'login', request.remote_addr))
            conn.commit()
            conn.close()
            
            # Mettre à jour last_login
            conn = get_db()
            cursor = conn.cursor()
            execute_query(cursor, "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user['id'],))
            conn.commit()
            conn.close()
            
            session['logged_in'] = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            # Rediriger selon le rôle
            if user['role'] == 'admin':
                return redirect(url_for('admin') + '?tab=dashboard')
            elif user['role'] == 'vendeur':
                return redirect(url_for('admin') + '?tab=dashboard')
            else:
                return redirect(url_for('index'))
        else:
            return render_template_string(HTML_LOGIN, error="Identifiants invalides ou compte désactivé")
    
    return render_template_string(HTML_LOGIN)
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory('static/uploads', filename)

@app.route('/uploads/medium/<filename>')
def uploaded_medium(filename):
    return send_from_directory('static/uploads/medium', filename)

@app.route('/admin/stats/filtered', methods=['POST'])
@login_required
def admin_stats_filtered():
    from datetime import datetime
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = get_db()
    cursor = conn.cursor()
    
    user_role = session.get('role')
    is_admin = (user_role == 'admin')
    
    # Produits (pas de filtre)
    execute_query(cursor,"SELECT COUNT(*) as count FROM products WHERE active=1")
    products = cursor.fetchone()['count']
    
    execute_query(cursor,"SELECT SUM(stock) as total FROM products WHERE active=1")
    row = cursor.fetchone()
    stock_total = row['total'] or 0 if row else 0
    
    execute_query(cursor,"SELECT COUNT(*) as count FROM products WHERE stock <= stock_min AND active=1")
    alert_products = cursor.fetchone()['count']
    
    # Commandes sur la période
    if DATABASE_URL:
        execute_query(cursor,"""
            SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total 
            FROM orders 
            WHERE DATE(date) BETWEEN %s AND %s AND status NOT IN ('cancelled', 'pending')
        """, (start_date, end_date))
    else:
        execute_query(cursor,"""
            SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total 
            FROM orders 
            WHERE date BETWEEN ? AND ? AND status NOT IN ('cancelled', 'pending')
        """, (start_date + ' 00:00:00', end_date + ' 23:59:59'))
    period_data = cursor.fetchone()
    orders_count = period_data['count'] or 0
    ca_period = period_data['total'] or 0
    
    # CA total
    execute_query(cursor,"SELECT COALESCE(SUM(total), 0) as total FROM orders WHERE status NOT IN ('cancelled', 'pending')")
    orders_total_ca = cursor.fetchone()['total'] or 0
    
    execute_query(cursor,"SELECT COALESCE(SUM(total), 0) as total FROM stock_out WHERE sale_type = 'direct'")
    direct_total_ca = cursor.fetchone()['total'] or 0
    
    ca_total = orders_total_ca + direct_total_ca
    
    # Bénéfice sur la période
    profit_period = 0
    if is_admin:
        if DATABASE_URL:
            execute_query(cursor,"""
                SELECT COALESCE(SUM(profit), 0) as total 
                FROM stock_out 
                WHERE DATE(date) BETWEEN %s AND %s
            """, (start_date, end_date))
        else:
            execute_query(cursor,"""
                SELECT COALESCE(SUM(profit), 0) as total 
                FROM stock_out 
                WHERE date BETWEEN ? AND ?
            """, (start_date + ' 00:00:00', end_date + ' 23:59:59'))
        profit_period = cursor.fetchone()['total'] or 0
    
    conn.close()
    
    return jsonify({
        'products': products,
        'stock_total': stock_total,
        'alert_products': alert_products,
        'orders_count': orders_count,
        'ca_period': ca_period,
        'ca_total': ca_total,
        'profit_period': profit_period,
        'is_admin': is_admin
    })

# ==================== API PRODUITS ====================

@app.route('/admin/products')
@login_required
def admin_products():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM products ORDER BY id DESC")
    products = cursor.fetchall()
    conn.close()
    return jsonify({'products': products})

@app.route('/admin/products/enhanced')
@login_required
def admin_products_enhanced():
    conn = get_db()
    cursor = conn.cursor()
    
    execute_query(cursor,"""
        SELECT 
            p.*,
            sc.name as subcategory_name,
            (SELECT s.name FROM stock_in si 
             LEFT JOIN suppliers s ON si.supplier_id = s.id 
             WHERE si.product_id = p.id 
             ORDER BY si.date DESC LIMIT 1) as supplier_name,
            (SELECT date FROM stock_in 
             WHERE product_id = p.id 
             ORDER BY date DESC LIMIT 1) as last_purchase_date
        FROM products p
        LEFT JOIN subcategories sc ON p.subcategory_id = sc.id
        ORDER BY p.id DESC
    """)
    products = cursor.fetchall()
    
    # S'assurer que prix_promo est bien un float ou None
    products_list = []
    for p in products:
        product_dict = dict(p)
        if product_dict.get('prix_promo') == '' or product_dict.get('prix_promo') == 0:
            product_dict['prix_promo'] = None
        products_list.append(product_dict)
    
    execute_query(cursor,"SELECT id, name FROM suppliers WHERE active=1 ORDER BY name")
    suppliers = cursor.fetchall()
    
    execute_query(cursor,"SELECT id, name FROM subcategories ORDER BY name")
    subcategories = cursor.fetchall()
    
    conn.close()
    
    return jsonify({
        'products': products_list,
        'suppliers': suppliers,
        'subcategories': subcategories
    })
@app.route('/admin/product/stock', methods=['POST'])
@login_required
def admin_product_stock():
    product_id = request.form.get('id')
    new_stock = int(request.form.get('stock', 0))
    
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})
@app.route('/admin/product/purchase-history/<int:product_id>')
@login_required
def admin_product_purchase_history(product_id):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"""
        SELECT si.*, s.name as supplier_name 
        FROM stock_in si
        LEFT JOIN suppliers s ON si.supplier_id = s.id
        WHERE si.product_id = ?
        ORDER BY si.date DESC
        LIMIT 20
    """, (product_id,))
    history = cursor.fetchall()
    conn.close()
    return jsonify(history)


@app.route('/admin/product', methods=['POST'])
@login_required
def admin_product_save():
    product_id = request.form.get('id')
    reference = request.form.get('reference')
    name = request.form.get('name')
    slug = request.form.get('slug') or name.lower().replace(' ', '-')
    description = request.form.get('description', '')
    short_description = request.form.get('short_description', '')
    subcategory_id = request.form.get('subcategory_id') or None
    stock_min = int(request.form.get('stock_min', 5))
    featured = 1 if request.form.get('featured') else 0
    
    # Pour la modification, récupérer les valeurs existantes
    if product_id:
        conn = get_db()
        cursor = conn.cursor()
        execute_query(cursor,"SELECT stock, prix_achat, prix_vente, prix_promo FROM products WHERE id=?", (product_id,))
        existing = cursor.fetchone()
        conn.close()
        
        # Utiliser les valeurs existantes si les champs ne sont pas dans le formulaire
        # ou si le formulaire les envoie vides
        stock = request.form.get('stock')
        if stock is None or stock == '':
            stock = existing['stock'] if existing else 0
        else:
            stock = int(stock)
        
        prix_achat = request.form.get('prix_achat')
        if prix_achat is None or prix_achat == '':
            prix_achat = existing['prix_achat'] if existing else 0
        else:
            prix_achat = float(prix_achat)
        
        prix_vente = request.form.get('prix_vente')
        if prix_vente is None or prix_vente == '':
            prix_vente = existing['prix_vente'] if existing else 0
        else:
            prix_vente = float(prix_vente)
        
        prix_promo = request.form.get('prix_promo')
        if prix_promo is None or prix_promo == '':
            prix_promo = existing['prix_promo'] if existing else None
        else:
            prix_promo = float(prix_promo) if prix_promo.strip() else None
    else:
        # Nouveau produit : les valeurs doivent être fournies
        stock = int(request.form.get('stock', 0))
        prix_achat = float(request.form.get('prix_achat', 0))
        prix_vente = float(request.form.get('prix_vente', 0))
        prix_promo = request.form.get('prix_promo')
        prix_promo = float(prix_promo) if prix_promo and prix_promo.strip() else None
    
    image_file = request.files.get('image')
    image_name = None
    if image_file and image_file.filename:
        image_name = save_image(image_file, 'medium')
    
    conn = get_db()
    cursor = conn.cursor()
    
    if product_id:
        if image_name:
            execute_query(cursor,"""
                UPDATE products 
                SET reference=?, name=?, slug=?, description=?, short_description=?, 
                    subcategory_id=?, prix_achat=?, prix_vente=?, prix_promo=?, 
                    stock=?, stock_min=?, image=?, featured=? 
                WHERE id=?
            """, (reference, name, slug, description, short_description, subcategory_id, 
                  prix_achat, prix_vente, prix_promo, stock, stock_min, image_name, featured, product_id))
        else:
            execute_query(cursor,"""
                UPDATE products 
                SET reference=?, name=?, slug=?, description=?, short_description=?, 
                    subcategory_id=?, prix_achat=?, prix_vente=?, prix_promo=?, 
                    stock=?, stock_min=?, featured=? 
                WHERE id=?
            """, (reference, name, slug, description, short_description, subcategory_id, 
                  prix_achat, prix_vente, prix_promo, stock, stock_min, featured, product_id))
    else:
        execute_query(cursor,"""
            INSERT INTO products (reference, name, slug, description, short_description, 
                                  subcategory_id, prix_achat, prix_vente, prix_promo, 
                                  stock, stock_min, image, featured) 
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (reference, name, slug, description, short_description, subcategory_id, 
              prix_achat, prix_vente, prix_promo, stock, stock_min, image_name, featured))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})
@app.route('/admin/product/<int:product_id>', methods=['DELETE'])
@login_required
def admin_product_delete(product_id):
    # Vérifier que l'utilisateur est admin
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Action réservée à l\'administrateur'}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor, "DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})
@app.route('/admin/product/active', methods=['POST'])
@login_required
def admin_product_active():
    product_id = request.form.get('id')
    active = int(request.form.get('active', 1))
    
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"UPDATE products SET active = ? WHERE id = ?", (active, product_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# ============== API IMAGES PRODUITS ====================

@app.route('/admin/product/images/<int:product_id>', methods=['GET'])
@login_required
def get_product_images(product_id):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM product_images WHERE product_id=? ORDER BY order_position", (product_id,))
    images = cursor.fetchall()
    conn.close()
    return jsonify(images)

@app.route('/admin/product/image', methods=['POST'])
@login_required
def add_product_image():
    print("=== DEBUG: add_product_image appelée ===")
    print("Files:", request.files)
    print("Form:", request.form)
    
    product_id = request.form.get('product_id')
    image_file = request.files.get('image')
    
    if not product_id:
        print("ERREUR: Pas de product_id")
        return jsonify({'success': False, 'error': 'Product ID manquant'})
    
    if not image_file or not image_file.filename:
        print("ERREUR: Pas d'image")
        return jsonify({'success': False, 'error': 'Aucune image'})
    
    print(f"Traitement de l'image pour le produit {product_id}")
    image_name = save_image(image_file, 'medium')
    print(f"Image sauvegardée: {image_name}")
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        execute_query(cursor,"""
            INSERT INTO product_images (product_id, image, order_position)
            VALUES (?, ?, ?)
        """, (product_id, image_name, 0))
        conn.commit()
        print("✅ Image ajoutée en BDD")
    except Exception as e:
        print(f"ERREUR SQL: {e}")
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})
    
    conn.close()
    return jsonify({'success': True, 'image': image_name})

@app.route('/admin/product/image/<int:image_id>', methods=['DELETE'])
@login_required
def delete_product_image(image_id):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT image FROM product_images WHERE id=?", (image_id,))
    image = cursor.fetchone()
    if image:
        # Supprimer le fichier
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], 'medium', image['image']))
        except:
            pass
    execute_query(cursor,"DELETE FROM product_images WHERE id=?", (image_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ============== API PROMO PRODUITS ====================

@app.route('/admin/product/promo', methods=['POST'])
@login_required
def admin_product_promo():
    product_id = request.form.get('id')
    prix_promo = request.form.get('prix_promo')
    
    print(f"=== DEBUG PROMO ===")
    print(f"Product ID: {product_id}")
    print(f"Prix promo reçu: {prix_promo}")
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Vérifier si le produit existe
    execute_query(cursor,"SELECT id, name, prix_vente FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    
    if not product:
        conn.close()
        return jsonify({'success': False, 'error': 'Produit non trouvé'})
    
    # Si prix_promo est vide ou null, on met None (pas de promo)
    if prix_promo and prix_promo.strip():
        prix_promo = float(prix_promo)
        print(f"Nouveau prix promo: {prix_promo}")
        print(f"Prix vente original: {product['prix_vente']}")
        action_msg = f"promo: {product['name']} - {product['prix_vente']} DNT → {prix_promo} DNT"
    else:
        prix_promo = None
        print("Suppression de la promotion")
        action_msg = f"promo_supprimée: {product['name']} - retour à {product['prix_vente']} DNT"
    
    # Mettre à jour
    execute_query(cursor,"UPDATE products SET prix_promo = ? WHERE id = ?", (prix_promo, product_id))
    
    # ========== CORRECTION : Utiliser user_logs ==========
    execute_query(cursor,"""
        INSERT INTO user_logs (user_id, action, ip_address)
        VALUES (?, ?, ?)
    """, (session.get('user_id'), action_msg, request.remote_addr))
    # ==================================
    
    conn.commit()
    
    # Vérifier la mise à jour
    execute_query(cursor,"SELECT prix_promo FROM products WHERE id = ?", (product_id,))
    updated = cursor.fetchone()
    print(f"Valeur en BDD après update: {updated['prix_promo']}")
    
    conn.close()
    
    return jsonify({'success': True, 'product_id': product_id, 'prix_promo': prix_promo})

@app.route('/api/validate-promo', methods=['POST'])
def validate_promo():
    data = request.json
    code = data.get('code', '').upper()
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupérer le code promo
    execute_query(cursor,"SELECT * FROM promotions WHERE code = ? AND active = 1", (code,))
    promo = cursor.fetchone()
    
    if not promo:
        conn.close()
        return jsonify({'valid': False, 'error': 'Code promo invalide'})
    
    # Vérifier les dates
    today = datetime.now().date()
    if promo['start_date']:
        start_date = datetime.strptime(promo['start_date'], '%Y-%m-%d').date()
        if today < start_date:
            conn.close()
            return jsonify({'valid': False, 'error': 'Code promo pas encore actif'})
    
    if promo['end_date']:
        end_date = datetime.strptime(promo['end_date'], '%Y-%m-%d').date()
        if today > end_date:
            conn.close()
            return jsonify({'valid': False, 'error': 'Code promo expiré'})
    
    # Vérifier la limite d'utilisation
    if promo['usage_limit'] and promo['used_count'] >= promo['usage_limit']:
        conn.close()
        return jsonify({'valid': False, 'error': 'Code promo déjà utilisé trop de fois'})
    
    conn.close()
    
    return jsonify({
        'valid': True,
        'discount': {
            'type': promo['discount_type'],
            'value': promo['discount_value'],
            'min_purchase': promo['min_purchase']
        }
    })

# ==================== API CATÉGORIES ====================

@app.route('/admin/categories')
@login_required
def admin_categories():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM categories ORDER BY order_position")
    categories = cursor.fetchall()
    execute_query(cursor,"""
        SELECT s.*, c.name as category_name FROM subcategories s
        LEFT JOIN categories c ON s.category_id = c.id
        ORDER BY c.order_position, s.name
    """)
    subcategories = cursor.fetchall()
    conn.close()
    return jsonify({'categories': categories, 'subcategories': subcategories})

@app.route('/admin/category', methods=['POST'])
@login_required
def admin_category_save():
    cat_id = request.form.get('id')
    name = request.form.get('name')
    slug = request.form.get('slug') or name.lower().replace(' ', '-')
    icon = request.form.get('icon', '📦')
    order_position = int(request.form.get('order_position', 0))
    
    conn = get_db()
    cursor = conn.cursor()
    if cat_id:
        execute_query(cursor,"UPDATE categories SET name=?, slug=?, icon=?, order_position=? WHERE id=?", (name, slug, icon, order_position, cat_id))
    else:
        execute_query(cursor,"INSERT INTO categories (name, slug, icon, order_position) VALUES (?,?,?,?)", (name, slug, icon, order_position))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/category/<int:cat_id>', methods=['DELETE'])
@login_required
def admin_category_delete(cat_id):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/subcategory', methods=['POST'])
@login_required
def admin_subcategory_save():
    sub_id = request.form.get('id')
    category_id = request.form.get('category_id')
    name = request.form.get('name')
    slug = request.form.get('slug') or name.lower().replace(' ', '-')
    
    conn = get_db()
    cursor = conn.cursor()
    if sub_id:
        execute_query(cursor,"UPDATE subcategories SET category_id=?, name=?, slug=? WHERE id=?", (category_id, name, slug, sub_id))
    else:
        execute_query(cursor,"INSERT INTO subcategories (category_id, name, slug) VALUES (?,?,?)", (category_id, name, slug))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/subcategory/<int:sub_id>', methods=['DELETE'])
@login_required
def admin_subcategory_delete(sub_id):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"DELETE FROM subcategories WHERE id=?", (sub_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/subcategory/<slug>')
def subcategory_page(slug):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT id, name, description FROM subcategories WHERE slug=?", (slug,))
    sub = cursor.fetchone()
    if not sub:
        return "Sous-catégorie non trouvée", 404
    
    execute_query(cursor,"SELECT * FROM products WHERE subcategory_id=? AND active=1 ORDER BY created_at DESC", (sub['id'],))
    products = cursor.fetchall()
    
    execute_query(cursor,"SELECT * FROM categories WHERE active=1 ORDER BY order_position")
    categories = cursor.fetchall()
    
    for cat in categories:
        execute_query(cursor,"SELECT * FROM subcategories WHERE category_id=? ORDER BY name", (cat['id'],))
        cat['subcategories'] = cursor.fetchall()
    
    execute_query(cursor,"SELECT key, value FROM settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    
    conn.close()
    
    return render_template('index.html', 
                                  products=products, 
                                  categories=categories,
                                  settings=settings, 
                                  category_name=cat['name'],
                                  category_description=cat['description'] or '')
    
# ==================== API COMMANDES ====================

@app.route('/admin/orders')
@login_required
def admin_orders():
    limit = request.args.get('limit')
    conn = get_db()
    cursor = conn.cursor()
    if limit:
        execute_query(cursor,"SELECT * FROM orders ORDER BY date DESC LIMIT ?", (limit,))
    else:
        execute_query(cursor,"SELECT * FROM orders ORDER BY date DESC")
    orders = cursor.fetchall()
    conn.close()
    return jsonify(orders)

@app.route('/admin/order/<int:order_id>')
@login_required
def admin_order(order_id):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM orders WHERE id=?", (order_id,))
    order = cursor.fetchone()
    conn.close()
    return jsonify(order)

@app.route('/admin/order/status', methods=['POST'])
@login_required
def admin_order_status():
    data = request.json
    order_id = data.get('id')
    new_status = data.get('status')
    user_role = session.get('role')
    user_id = session.get('user_id')
    username = session.get('username')
    
    conn = get_db()
    cursor = conn.cursor()
    
    execute_query(cursor,"SELECT * FROM orders WHERE id=?", (order_id,))
    order = cursor.fetchone()
    
    if not order:
        conn.close()
        return jsonify({'success': False, 'error': 'Commande non trouvée'})
    
    old_status = order['status']
    stock_deducted = order['stock_deducted']
    
    # ========== RESTRICTIONS SELON LE RÔLE ==========
    if user_role != 'admin':
        # Vendeur : ne peut modifier que si la commande est en 'pending'
        if old_status != 'pending':
            conn.close()
            return jsonify({'success': False, 'error': 'Action non autorisée. Seul l\'administrateur peut modifier les commandes déjà traitées.'})
        
        # Vendeur : ne peut PAS confirmer une commande
        if new_status == 'confirmed':
            conn.close()
            return jsonify({'success': False, 'error': 'Seul l\'administrateur peut confirmer une commande.'})
        
        # Vendeur : ne peut PAS marquer comme livrée
        if new_status == 'delivered':
            conn.close()
            return jsonify({'success': False, 'error': 'Seul l\'administrateur peut marquer une commande comme livrée.'})
        
        # Vendeur : ne peut PAS modifier une commande déjà expédiée
        if old_status == 'shipped':
            conn.close()
            return jsonify({'success': False, 'error': 'Action non autorisée. Cette commande est déjà expédiée.'})
    
    # Si l'utilisateur est admin, toutes les modifications sont autorisées
    # ================================================================
    
    # ========== AJOUTER LE LOG DANS user_logs ==========
    execute_query(cursor,"""
        INSERT INTO user_logs (user_id, action, ip_address)
        VALUES (?, ?, ?)
    """, (user_id, f"commande_status: {order['order_number']} - {old_status} → {new_status} par {username}", request.remote_addr))
    # ===================================================
    
    # Enregistrer dans les logs dédiés (order_logs)
    execute_query(cursor,"""
        INSERT INTO order_logs (order_id, user_id, old_status, new_status, action_date, ip_address)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
    """, (order_id, user_id, old_status, new_status, request.remote_addr))
    
    # ====== GESTION DU STOCK ET DES VENTES ======
    
    # Cas 1: Commande confirmée, expédiée ou livrée -> Déduire le stock et enregistrer dans stock_out
    if new_status in ['confirmed', 'shipped', 'delivered'] and not stock_deducted:
        items = json.loads(order['items'])
        
        # Calculer le sous-total et la réduction
        subtotal = sum(item['price'] * item['quantity'] for item in items)
        discount = subtotal - order['total']
        discount_factor = 1 - (discount / subtotal) if subtotal > 0 else 1
        
        for item in items:
            execute_query(cursor,"SELECT prix_achat FROM products WHERE id=?", (item['id'],))
            product = cursor.fetchone()
            purchase_price = product['prix_achat'] if product else 0
            
            # Prix unitaire après réduction
            discounted_price = item['price'] * discount_factor
            
            profit = (discounted_price - purchase_price) * item['quantity']
            
            # Enregistrer dans stock_out avec le prix réduit
            execute_query(cursor,"""
                INSERT INTO stock_out (product_id, client_name, client_phone, client_email, client_address, 
                                       quantity, sale_price, total, profit, notes, sale_type, order_number, seller_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'order', ?, ?)
            """, (item['id'], order['client_name'], order['client_phone'], order['client_email'], order['client_address'],
                  item['quantity'], discounted_price, discounted_price * item['quantity'], profit, 
                  f"Commande en ligne #{order['order_number']} (statut: {new_status})", 
                  order['order_number'], 'Client en ligne'))
            
            # Déduire le stock
            execute_query(cursor,"UPDATE products SET stock = stock - ? WHERE id=?", (item['quantity'], item['id']))
        
        execute_query(cursor,"UPDATE orders SET stock_deducted = 1 WHERE id=?", (order_id,))
    
    # Cas 2: Commande annulée -> Supprimer de stock_out et remettre le stock
    elif new_status == 'cancelled' and stock_deducted:
        items = json.loads(order['items'])
        
        for item in items:
            # Supprimer l'entrée de stock_out
            execute_query(cursor,"""
                DELETE FROM stock_out 
                WHERE notes LIKE ? AND product_id = ?
            """, (f"%{order['order_number']}%", item['id']))
            
            # Remettre le stock
            execute_query(cursor,"UPDATE products SET stock = stock + ? WHERE id=?", (item['quantity'], item['id']))
        
        execute_query(cursor,"UPDATE orders SET stock_deducted = 0 WHERE id=?", (order_id,))
    
    # Mettre à jour le statut
    execute_query(cursor,"UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': f'Statut modifié de {old_status} à {new_status}'})

# ==================== API FOURNISSEURS ====================

@app.route('/admin/suppliers')
@login_required
def admin_suppliers():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM suppliers WHERE active=1 ORDER BY name")
    suppliers = cursor.fetchall()
    conn.close()
    return jsonify(suppliers)

@app.route('/admin/supplier', methods=['POST'])
@login_required
def admin_supplier_save():
    sup_id = request.form.get('id')
    name = request.form.get('name')
    company = request.form.get('company')
    phone = request.form.get('phone')
    email = request.form.get('email')
    address = request.form.get('address')
    contact_person = request.form.get('contact_person')
    
    conn = get_db()
    cursor = conn.cursor()
    if sup_id:
        execute_query(cursor,"UPDATE suppliers SET name=?, company=?, phone=?, email=?, address=?, contact_person=? WHERE id=?", 
                      (name, company, phone, email, address, contact_person, sup_id))
    else:
        execute_query(cursor,"INSERT INTO suppliers (name, company, phone, email, address, contact_person) VALUES (?,?,?,?,?,?)",
                      (name, company, phone, email, address, contact_person))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/supplier/<int:sup_id>', methods=['DELETE'])
@login_required
def admin_supplier_delete(sup_id):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"UPDATE suppliers SET active=0 WHERE id=?", (sup_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ==================== API STOCK ====================

@app.route('/admin/stock-in')
@login_required
def admin_stock_in():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"""
        SELECT si.*, p.name as product_name, s.name as supplier_name 
        FROM stock_in si
        LEFT JOIN products p ON si.product_id = p.id
        LEFT JOIN suppliers s ON si.supplier_id = s.id
        ORDER BY si.date DESC
    """)
    stock = cursor.fetchall()
    conn.close()
    return jsonify(stock)

@app.route('/admin/stock-in', methods=['POST'])
@login_required
def admin_stock_in_save():
    product_id = request.form.get('product_id')
    supplier_id = request.form.get('supplier_id') or None
    quantity = int(request.form.get('quantity'))
    purchase_price = float(request.form.get('purchase_price'))
    prix_vente = float(request.form.get('prix_vente'))
    total = quantity * purchase_price
    notes = request.form.get('notes', '')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupérer le nom du produit et du fournisseur pour le log
    execute_query(cursor,"SELECT name FROM products WHERE id=?", (product_id,))
    product = cursor.fetchone()
    product_name = product['name'] if product else 'Produit'
    
    supplier_name = ''
    if supplier_id:
        execute_query(cursor,"SELECT name FROM suppliers WHERE id=?", (supplier_id,))
        supplier = cursor.fetchone()
        supplier_name = supplier['name'] if supplier else ''
    
    # 1. Insérer l'entrée stock
    execute_query(cursor,"""
        INSERT INTO stock_in (product_id, supplier_id, quantity, purchase_price, total, notes) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (product_id, supplier_id, quantity, purchase_price, total, notes))
    
    # 2. Mettre à jour le produit
    execute_query(cursor,"""
        UPDATE products 
        SET stock = stock + ?, 
            prix_achat = ?,
            prix_vente = ?
        WHERE id = ?
    """, (quantity, purchase_price, prix_vente, product_id))
    
    # ========== CORRECTION : Utiliser user_logs ==========
    execute_query(cursor,"""
        INSERT INTO user_logs (user_id, action, ip_address)
        VALUES (?, ?, ?)
    """, (session.get('user_id'), f"achat: {product_name} x{quantity} - {supplier_name} - {total:.2f} DNT", request.remote_addr))
    # ====================
    
    conn.commit()
    
    # 3. Récupérer les données mises à jour
    execute_query(cursor,"SELECT * FROM products WHERE id = ?", (product_id,))
    updated_product = cursor.fetchone()
    
    conn.close()
    
    return jsonify({
        'success': True, 
        'product': updated_product
    })
@app.route('/admin/stock-out')
@login_required
def admin_stock_out():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"""
        SELECT 
            so.*, 
            p.name as product_name,
            p.reference as product_reference,
            COALESCE(so.sale_type, 'direct') as sale_type
        FROM stock_out so
        LEFT JOIN products p ON so.product_id = p.id
        ORDER BY so.date DESC
    """)
    stock = cursor.fetchall()
    conn.close()
    return jsonify(stock)

@app.route('/admin/stock-out/deleted')
@login_required
def admin_stock_out_deleted():
    """Récupère les ventes qui ont été annulées (pour audit)"""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Non autorisé'}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"""
        SELECT so.*, p.name as product_name, o.status as order_status, o.order_number
        FROM stock_out so
        LEFT JOIN products p ON so.product_id = p.id
        LEFT JOIN orders o ON so.notes LIKE ('%' || o.order_number || '%')
        WHERE o.status = 'cancelled' OR so.notes LIKE '%ANNULÉ%'
        ORDER BY so.date DESC
    """)
    stock = cursor.fetchall()
    conn.close()
    return jsonify(stock)

# ==================== API STOCK OUT ====================

@app.route('/admin/stock-out', methods=['POST'])
@login_required
def admin_stock_out_save():
    product_id = request.form.get('product_id')
    client_name = request.form.get('client_name')
    client_phone = request.form.get('client_phone')
    client_email = request.form.get('client_email', '')
    client_address = request.form.get('client_address', '')
    quantity = int(request.form.get('quantity'))
    sale_price = float(request.form.get('sale_price'))
    total = quantity * sale_price
    notes = request.form.get('notes', '')
    
    # Récupérer le vendeur connecté
    seller_id = session.get('user_id')
    seller_name = session.get('username')
    
    conn = get_db()
    cursor = conn.cursor()
    
    execute_query(cursor, "SELECT name, prix_achat FROM products WHERE id=%s", (product_id,))
    product = cursor.fetchone()
    product_name = product['name'] if product else 'Produit'
    purchase_price = product['prix_achat'] if product else 0
    profit = total - (quantity * purchase_price)
    
    # Générer numéro de ticket
    execute_query(cursor, "SELECT numero FROM tickets ORDER BY id DESC LIMIT 1")
    last = cursor.fetchone()
    if last:
        num = int(last['numero'].split('-')[1]) + 1
        ticket_num = f"TICKET-{num:03d}"
    else:
        ticket_num = "TICKET-001"
    
    # Enregistrer le ticket
    execute_query(cursor, """
        INSERT INTO tickets (numero, client_name, client_phone, client_email, product_name, quantity, price, total)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (ticket_num, client_name, client_phone, client_email, product_name, quantity, sale_price, total))
    
    # Enregistrer la sortie stock avec le vendeur
    execute_query(cursor, """
        INSERT INTO stock_out (product_id, client_name, client_phone, client_email, client_address, quantity, sale_price, total, profit, notes, seller_id, seller_name, sale_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'direct')
    """, (product_id, client_name, client_phone, client_email, client_address, quantity, sale_price, total, profit, notes, seller_id, seller_name))
    
    execute_query(cursor, "UPDATE products SET stock = stock - %s WHERE id=%s", (quantity, product_id))
    
    # Enregistrer dans les logs
    execute_query(cursor, """
        INSERT INTO user_logs (user_id, action, ip_address)
        VALUES (%s, %s, %s)
    """, (seller_id, f"vente: {product_name} x{quantity} - {client_name} - {total:.2f} DNT", request.remote_addr))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'ticket_number': ticket_num})
    
    # ==================== API TICKET ====================

@app.route('/admin/stock-out/last-ticket')
@login_required
def admin_stock_out_last_ticket():
    # Générer un numéro basé sur la date
    from datetime import datetime
    ticket_num = f"TKT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return jsonify({'numero': ticket_num})

@app.route('/admin/tickets')
@login_required
def admin_tickets():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM tickets ORDER BY date DESC LIMIT 100")
    tickets = cursor.fetchall()
    conn.close()
    return jsonify(tickets)

@app.route('/admin/ticket/<ticket_number>')
@login_required
def admin_ticket(ticket_number):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM tickets WHERE numero=?", (ticket_number,))
    ticket = cursor.fetchone()
    conn.close()
    return jsonify(ticket)

# ==================== API CLIENTS ====================

@app.route('/admin/clients')
@login_required
def admin_clients():
    conn = get_db()
    cursor = conn.cursor()
    # Récupérer TOUS les utilisateurs avec rôle 'client' depuis la table users
    execute_query(cursor,"""
        SELECT id, username, fullname as name, email, phone, 
               created_at, last_login, active 
        FROM users 
        WHERE role = 'client' 
        ORDER BY created_at DESC
    """)
    clients = cursor.fetchall()
    
    # Pour chaque client, calculer le total des achats depuis les commandes
    for client in clients:
        # Chercher les commandes par email ou téléphone
        execute_query(cursor,"""
            SELECT COUNT(*) as total_orders, SUM(total) as total_achats 
            FROM orders 
            WHERE client_email = ? OR client_phone = ?
        """, (client['email'], client['phone']))
        stats = cursor.fetchone()
        client['total_orders'] = stats['total_orders'] or 0
        client['total_achats'] = stats['total_achats'] or 0
        
        # Dernière commande
        execute_query(cursor,"""
            SELECT date FROM orders 
            WHERE client_email = ? OR client_phone = ?
            ORDER BY date DESC LIMIT 1
        """, (client['email'], client['phone']))
        last = cursor.fetchone()
        client['last_order'] = last['date'] if last else None
    
    conn.close()
    return jsonify(clients)

# ==================== API STATISTIQUES ====================

# ==================== API STATISTIQUES (CORRIGÉE) ====================

@app.route('/admin/stats')
@login_required
def admin_stats():
    from datetime import datetime
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupérer le rôle de l'utilisateur
    user_role = session.get('role')
    is_admin = (user_role == 'admin')
    
    execute_query(cursor,"SELECT COUNT(*) as count FROM products WHERE active=1")
    products = cursor.fetchone()['count']
    
    execute_query(cursor,"SELECT SUM(stock) as total FROM products WHERE active=1")
    row = cursor.fetchone()
    stock_total = row['total'] or 0 if row else 0
    
    execute_query(cursor,"SELECT COUNT(*) as count FROM products WHERE stock <= stock_min AND active=1")
    alert_products = cursor.fetchone()['count']
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Commandes en ligne du jour (PostgreSQL compatible)
    if DATABASE_URL:
        execute_query(cursor,"""
            SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total 
            FROM orders 
            WHERE DATE(date) = %s AND status NOT IN ('cancelled', 'pending')
        """, (today,))
    else:
        execute_query(cursor,"""
            SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total 
            FROM orders 
            WHERE date LIKE ? AND status NOT IN ('cancelled', 'pending')
        """, (today + '%',))
    orders_today_data = cursor.fetchone()
    orders_today_count = orders_today_data['count'] or 0
    orders_today_ca = orders_today_data['total'] or 0
    
    # Ventes directes (caisse) du jour
    if DATABASE_URL:
        execute_query(cursor,"""
            SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total 
            FROM stock_out 
            WHERE sale_type = 'direct' AND DATE(date) = %s
        """, (today,))
    else:
        execute_query(cursor,"""
            SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total 
            FROM stock_out 
            WHERE sale_type = 'direct' AND date LIKE ?
        """, (today + '%',))
    direct_today_data = cursor.fetchone()
    direct_today_count = direct_today_data['count'] or 0
    direct_today_ca = direct_today_data['total'] or 0
    
    # Total du jour
    orders_today = orders_today_count + direct_today_count
    ca_jour = orders_today_ca + direct_today_ca
    
    # CA du mois
    month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    
    if DATABASE_URL:
        execute_query(cursor,"""
            SELECT COALESCE(SUM(total), 0) as total 
            FROM orders 
            WHERE DATE(date) >= %s AND status NOT IN ('cancelled', 'pending')
        """, (month_start,))
    else:
        execute_query(cursor,"""
            SELECT COALESCE(SUM(total), 0) as total 
            FROM orders 
            WHERE date >= ? AND status NOT IN ('cancelled', 'pending')
        """, (month_start,))
    orders_month_ca = cursor.fetchone()['total'] or 0
    
    if DATABASE_URL:
        execute_query(cursor,"""
            SELECT COALESCE(SUM(total), 0) as total 
            FROM stock_out 
            WHERE sale_type = 'direct' AND DATE(date) >= %s
        """, (month_start,))
    else:
        execute_query(cursor,"""
            SELECT COALESCE(SUM(total), 0) as total 
            FROM stock_out 
            WHERE sale_type = 'direct' AND date >= ?
        """, (month_start,))
    direct_month_ca = cursor.fetchone()['total'] or 0
    
    ca_mois = orders_month_ca + direct_month_ca
    
    # CA total
    execute_query(cursor,"SELECT COALESCE(SUM(total), 0) as total FROM orders WHERE status NOT IN ('cancelled', 'pending')")
    orders_total_ca = cursor.fetchone()['total'] or 0
    
    execute_query(cursor,"SELECT COALESCE(SUM(total), 0) as total FROM stock_out WHERE sale_type = 'direct'")
    direct_total_ca = cursor.fetchone()['total'] or 0
    
    ca_total = orders_total_ca + direct_total_ca
    
    # Bénéfice total (seulement pour l'admin)
    profit_total = 0
    if is_admin:
        execute_query(cursor,"SELECT COALESCE(SUM(profit), 0) as total FROM stock_out")
        profit_total = cursor.fetchone()['total'] or 0
    
    conn.close()
    
    return jsonify({
        'products': products,
        'stock_total': stock_total,
        'alert_products': alert_products,
        'orders_today': orders_today,
        'ca_jour': ca_jour,
        'ca_mois': ca_mois,
        'ca_total': ca_total,
        'profit_total': profit_total,
        'is_admin': is_admin
    })
# ==================== API PROMOTIONS ====================

@app.route('/admin/promotions')
@login_required
def admin_promotions():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM promotions ORDER BY id DESC")
    promotions = cursor.fetchall()
    conn.close()
    return jsonify(promotions)

@app.route('/admin/promotion', methods=['POST'])
@login_required
def admin_promotion_save():
    promo_id = request.form.get('id')
    code = request.form.get('code').upper()
    description = request.form.get('description', '')
    discount_type = request.form.get('discount_type')
    discount_value = float(request.form.get('discount_value'))
    min_purchase = float(request.form.get('min_purchase', 0))
    start_date = request.form.get('start_date') or None
    end_date = request.form.get('end_date') or None
    usage_limit = request.form.get('usage_limit')
    usage_limit = int(usage_limit) if usage_limit and usage_limit.strip() else None
    active = 1 if request.form.get('active') else 0
    
    conn = get_db()
    cursor = conn.cursor()
    if promo_id:
        execute_query(cursor,"UPDATE promotions SET code=?, description=?, discount_type=?, discount_value=?, min_purchase=?, start_date=?, end_date=?, usage_limit=?, active=? WHERE id=?",
                      (code, description, discount_type, discount_value, min_purchase, start_date, end_date, usage_limit, active, promo_id))
    else:
        execute_query(cursor,"INSERT INTO promotions (code, description, discount_type, discount_value, min_purchase, start_date, end_date, usage_limit, active) VALUES (?,?,?,?,?,?,?,?,?)",
                      (code, description, discount_type, discount_value, min_purchase, start_date, end_date, usage_limit, active))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/promotion/<int:promo_id>', methods=['DELETE'])
@login_required
def admin_promotion_delete(promo_id):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"DELETE FROM promotions WHERE id=?", (promo_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/apply-promo', methods=['POST'])
def apply_promo():
    data = request.json
    code = data.get('code', '').upper()
    total = data.get('total', 0)
    
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM promotions WHERE code=? AND active=1", (code,))
    promo = cursor.fetchone()
    
    if not promo:
        return jsonify({'success': False, 'error': 'Code promo invalide'})
    
    # Vérifier date
    today = datetime.now().date()
    if promo['start_date']:
        start = datetime.strptime(promo['start_date'], '%Y-%m-%d').date()
        if today < start:
            return jsonify({'success': False, 'error': 'Code promo pas encore actif'})
    if promo['end_date']:
        end = datetime.strptime(promo['end_date'], '%Y-%m-%d').date()
        if today > end:
            return jsonify({'success': False, 'error': 'Code promo expiré'})
    
    # Vérifier limite
    if promo['usage_limit'] and promo['used_count'] >= promo['usage_limit']:
        return jsonify({'success': False, 'error': 'Code promo épuisé'})
    
    # Vérifier montant minimum
    if total < promo['min_purchase']:
        return jsonify({'success': False, 'error': f'Minimum d\'achat: {promo["min_purchase"]} DNT'})
    
    # Calculer réduction
    if promo['discount_type'] == 'percentage':
        discount = total * promo['discount_value'] / 100
    else:
        discount = min(promo['discount_value'], total)
    
    conn.close()
    return jsonify({'success': True, 'discount': discount})

# ==================== API AVIS ====================

@app.route('/api/review', methods=['POST'])
def add_review():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"""
        INSERT INTO reviews (product_id, client_name, client_email, rating, comment, approved)
        VALUES (?, ?, ?, ?, ?, 1)
    """, (data['product_id'], data['client_name'], data['client_email'], data['rating'], data['comment']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/order', methods=['POST'])
def api_order():
    data = request.json
    order_number = str(uuid.uuid4())[:8].upper()
    items_json = json.dumps(data['items'])
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Insérer la commande
    execute_query(cursor,"""
        INSERT INTO orders (order_number, client_name, client_phone, client_email, client_address, items, total)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (order_number, data['client_name'], data['client_phone'], data['client_email'], 
          data['client_address'], items_json, data['total']))
    
    # Enregistrer dans stock_out avec sale_type = 'order'
    for item in data['items']:
        execute_query(cursor,"SELECT prix_achat FROM products WHERE id=?", (item['id'],))
        product = cursor.fetchone()
        purchase_price = product['prix_achat'] if product else 0
        profit = (item['price'] - purchase_price) * item['quantity']
        
        execute_query(cursor,"""
            INSERT INTO stock_out (product_id, client_name, client_phone, client_email, client_address, quantity, sale_price, total, profit, notes, sale_type, order_number, seller_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'order', ?, ?)
        """, (item['id'], data['client_name'], data['client_phone'], data['client_email'], data['client_address'],
              item['quantity'], item['price'], item['price'] * item['quantity'], profit, 
              f"Commande en ligne #{order_number}", order_number, 'Client en ligne'))
        
        execute_query(cursor,"UPDATE products SET stock = stock - ? WHERE id=?", (item['quantity'], item['id']))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'order_number': order_number})

# ==================== API SLIDER ====================

@app.route('/admin/sliders')
@login_required
def admin_sliders():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM sliders ORDER BY order_position")
    sliders = cursor.fetchall()
    conn.close()
    return jsonify(sliders)

@app.route('/admin/slider', methods=['POST'])
@login_required
def admin_slider_save():
    slider_id = request.form.get('id')
    title = request.form.get('title', '')
    subtitle = request.form.get('subtitle', '')
    button_text = request.form.get('button_text', '')
    button_link = request.form.get('button_link', '')
    order_position = int(request.form.get('order_position', 0))
    active = 1 if request.form.get('active') else 0
    
    image_file = request.files.get('image')
    image_name = None
    if image_file and image_file.filename:
        ext = image_file.filename.rsplit('.', 1)[1].lower() if '.' in image_file.filename else 'jpg'
        image_name = str(uuid.uuid4()) + '.' + ext
        img = Image.open(image_file)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        img.thumbnail((1920, 600), Image.Resampling.LANCZOS)
        img.save(os.path.join(app.config['UPLOAD_FOLDER'], 'slider', image_name), 'JPEG', quality=85)
    
    conn = get_db()
    cursor = conn.cursor()
    if slider_id:
        if image_name:
            execute_query(cursor,"UPDATE sliders SET title=?, subtitle=?, button_text=?, button_link=?, image=?, order_position=?, active=? WHERE id=?",
                          (title, subtitle, button_text, button_link, image_name, order_position, active, slider_id))
        else:
            execute_query(cursor,"UPDATE sliders SET title=?, subtitle=?, button_text=?, button_link=?, order_position=?, active=? WHERE id=?",
                          (title, subtitle, button_text, button_link, order_position, active, slider_id))
    else:
        execute_query(cursor,"INSERT INTO sliders (title, subtitle, button_text, button_link, image, order_position, active) VALUES (?,?,?,?,?,?,?)",
                      (title, subtitle, button_text, button_link, image_name, order_position, active))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/slider/<int:slider_id>', methods=['DELETE'])
@login_required
def admin_slider_delete(slider_id):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"DELETE FROM sliders WHERE id=?", (slider_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ======= API UTILISATEURS ====================

@app.route('/admin/users', methods=['GET'])
@login_required
def admin_users():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Non autorisé'}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT id, username, fullname, email, phone, role, active, last_login, created_at FROM users ORDER BY id")
    users = cursor.fetchall()
    conn.close()
    return jsonify(users)

@app.route('/admin/user', methods=['POST'])
@login_required
def admin_user_save():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Non autorisé'}), 403
    
    user_id = request.form.get('id')
    username = request.form.get('username')
    fullname = request.form.get('fullname')
    email = request.form.get('email')
    phone = request.form.get('phone')
    role = request.form.get('role')
    active = 1 if request.form.get('active') else 0
    password = request.form.get('password')
    
    conn = get_db()
    cursor = conn.cursor()
    
    if user_id:
        if password:
            hashed = hashlib.sha256(password.encode()).hexdigest()
            execute_query(cursor,"""
                UPDATE users SET username=?, fullname=?, email=?, phone=?, role=?, active=?, password=?
                WHERE id=?
            """, (username, fullname, email, phone, role, active, hashed, user_id))
        else:
            execute_query(cursor,"""
                UPDATE users SET username=?, fullname=?, email=?, phone=?, role=?, active=?
                WHERE id=?
            """, (username, fullname, email, phone, role, active, user_id))
    else:
        hashed = hashlib.sha256(password.encode()).hexdigest()
        execute_query(cursor,"""
            INSERT INTO users (username, password, fullname, email, phone, role, active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (username, hashed, fullname, email, phone, role, active))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/user/<int:user_id>', methods=['DELETE'])
@login_required
def admin_user_delete(user_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Non autorisé'}), 403
    
    if user_id == 1:
        return jsonify({'error': 'Impossible de supprimer l\'admin principal'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/user/logs/<int:user_id>', methods=['GET'])
@login_required
def admin_user_logs(user_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Non autorisé'}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM user_logs WHERE user_id=? ORDER BY date DESC LIMIT 50", (user_id,))
    logs = cursor.fetchall()
    conn.close()
    return jsonify(logs)

# ==================== API CLIENT ====================

@app.route('/api/client/login', methods=['POST'])
def api_client_login():
    data = request.json
    username = data.get('username')
    password = hashlib.sha256(data.get('password', '').encode()).hexdigest()
    
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM users WHERE username=? AND password=? AND active=1 AND role='client'", (username, password))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        session['client_logged_in'] = True
        session['client_id'] = user['id']
        session['client_name'] = user['fullname']
        session['client_email'] = user['email']  
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Identifiants invalides'})

@app.route('/api/client/register', methods=['POST'])
def api_client_register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    fullname = data.get('fullname')
    email = data.get('email')
    phone = data.get('phone', '')
    
    # Validation serveur du mot de passe
    if len(password) < 8:
        return jsonify({'success': False, 'error': 'Le mot de passe doit contenir au moins 8 caractères'})
    
    if not any(c.isdigit() for c in password):
        return jsonify({'success': False, 'error': 'Le mot de passe doit contenir au moins un chiffre'})
    
    # Validation du téléphone
    phone_digits = ''.join(filter(str.isdigit, phone))
    if len(phone_digits) < 8:
        return jsonify({'success': False, 'error': 'Le numéro de téléphone doit contenir au moins 8 chiffres'})
    
    # Hachage du mot de passe
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Vérifier si l'utilisateur existe déjà
    execute_query(cursor,"SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
    if cursor.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Nom d\'utilisateur ou email déjà utilisé'})
    
    # Insérer le nouvel utilisateur
    execute_query(cursor,"""
        INSERT INTO users (username, password, fullname, email, phone, role, active)
        VALUES (?, ?, ?, ?, ?, 'client', 1)
    """, (username, hashed_password, fullname, email, phone_digits))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/logout/client')
def logout_client():
    session.pop('client_logged_in', None)
    session.pop('client_id', None)
    session.pop('client_name', None)
    return redirect(url_for('index'))

# ==================== ESPACE CLIENT ====================

@app.route('/compte')
def compte_client():
    if not session.get('client_logged_in'):
        return redirect(url_for('index'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupérer les infos du client
    execute_query(cursor,"SELECT * FROM users WHERE id=?", (session.get('client_id'),))
    client = cursor.fetchone()
    
    # Récupérer les commandes du client
    execute_query(cursor,"""
        SELECT * FROM orders 
        WHERE client_email = ? OR client_phone = ?
        ORDER BY date DESC
    """, (client['email'], client['phone']))
    orders = cursor.fetchall()
    
    # Récupérer les produits déjà achetés par le client (pour permettre les avis)
    product_ids = set()
    products_bought = []
    
    for order in orders:
        items = json.loads(order['items'])
        for item in items:
            product_ids.add(item['id'])
    
    if product_ids:
        placeholders = ','.join('?' * len(product_ids))
        execute_query(cursor,f"SELECT * FROM products WHERE id IN ({placeholders})", tuple(product_ids))
        products_bought = cursor.fetchall()
    
    # Récupérer les avis déjà laissés par le client
    execute_query(cursor,"SELECT product_id FROM reviews WHERE client_email=?", (client['email'],))
    reviewed_products = [r['product_id'] for r in cursor.fetchall()]
    
    execute_query(cursor,"SELECT key, value FROM settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    
    execute_query(cursor,"SELECT * FROM categories WHERE active=1 ORDER BY order_position")
    categories = cursor.fetchall()
    
    for cat in categories:
        execute_query(cursor,"SELECT * FROM subcategories WHERE category_id=? ORDER BY name", (cat['id'],))
        cat['subcategories'] = cursor.fetchall()
    
    conn.close()
    
    return render_template_string(HTML_COMPTE, 
                                  client=client,
                                  orders=orders,
                                  products_bought=products_bought,
                                  reviewed_products=reviewed_products,
                                  settings=settings,
                                  categories=categories)

@app.route('/api/submit-review', methods=['POST'])
def submit_review():
    if not session.get('client_logged_in'):
        return jsonify({'success': False, 'error': 'Connectez-vous pour laisser un avis'})
    
    data = request.json
    product_id = data.get('product_id')
    rating = data.get('rating')
    comment = data.get('comment', '')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Vérifier si le client a déjà laissé un avis
    execute_query(cursor,"SELECT id FROM reviews WHERE product_id=? AND client_email=?", 
                   (product_id, session.get('client_email')))
    existing = cursor.fetchone()
    
    if existing:
        execute_query(cursor,"""
            UPDATE reviews SET rating=?, comment=?, date=CURRENT_TIMESTAMP
            WHERE product_id=? AND client_email=?
        """, (rating, comment, product_id, session.get('client_email')))
    else:
        execute_query(cursor,"""
            INSERT INTO reviews (product_id, client_name, client_email, rating, comment, approved)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (product_id, session.get('client_name'), session.get('client_email'), rating, comment))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/cancel-order/<order_number>', methods=['POST'])
def cancel_order(order_number):
    if not session.get('client_logged_in'):
        return jsonify({'success': False, 'error': 'Non autorisé'})
    
    conn = get_db()
    cursor = conn.cursor()
    
    execute_query(cursor,"SELECT * FROM orders WHERE order_number=? AND client_email=?", 
                   (order_number, session.get('client_email')))
    order = cursor.fetchone()
    
    if not order:
        conn.close()
        return jsonify({'success': False, 'error': 'Commande non trouvée'})
    
    # On ne peut annuler que si le statut est 'pending'
    if order['status'] != 'pending':
        conn.close()
        return jsonify({'success': False, 'error': 'Cette commande ne peut plus être annulée'})
    
    # Annuler la commande (stock non déduit car toujours en pending)
    execute_query(cursor,"UPDATE orders SET status='cancelled' WHERE order_number=?", (order_number,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# ==================== API CAISSE ====================

@app.route('/caisse')
@login_required
def caisse():
    """Interface de caisse pour les ventes directes"""
    if session.get('role') not in ['admin', 'vendeur']:
        return "Accès non autorisé", 403
    
    conn = get_db()
    cursor = conn.cursor()
    
    execute_query(cursor,"SELECT key, value FROM settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    
    execute_query(cursor,"SELECT * FROM categories WHERE active=1 ORDER BY order_position")
    categories = cursor.fetchall()
    
    # MODIFICATION ICI : Récupérer TOUS les produits actifs (pas seulement ceux avec stock > 0)
    execute_query(cursor,"SELECT * FROM products WHERE active=1 ORDER BY name")
    products = cursor.fetchall()
    
    # Debug : Afficher le nombre de produits
    print(f"📦 Nombre de produits chargés pour la caisse : {len(products)}")
    
    conn.close()
    
    return render_template('caisse.html', settings=settings, categories=categories, products=products)

# ================ API COMMANDE ====================

@app.route('/checkout')
def checkout_page():
    conn = get_db()
    cursor = conn.cursor()
    
    execute_query(cursor,"SELECT key, value FROM settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    
    execute_query(cursor,"SELECT * FROM categories WHERE active=1 ORDER BY order_position")
    categories = cursor.fetchall()
    
    for cat in categories:
        execute_query(cursor,"SELECT * FROM subcategories WHERE category_id=? ORDER BY name", (cat['id'],))
        cat['subcategories'] = cursor.fetchall()
    
    # Récupérer les infos du client connecté
    client_info = {}
    if session.get('client_logged_in'):
        execute_query(cursor,"SELECT fullname, email, phone FROM users WHERE id=?", (session.get('client_id'),))
        client = cursor.fetchone()
        if client:
            client_info = {
                'name': client['fullname'],
                'email': client['email'],
                'phone': client['phone']
            }
    
    conn.close()
    
    return render_template_string(HTML_CHECKOUT, 
                                  settings=settings,
                                  categories=categories,
                                  client_info=client_info)

@app.route('/api/checkout', methods=['POST'])
def api_checkout():
    data = request.json
    order_number = str(uuid.uuid4())[:8].upper()
    
    # Calculer le total avec réduction
    subtotal = sum(item['price'] * item['quantity'] for item in data['items'])
    discount_amount = data.get('discount_amount', 0)
    total = subtotal - discount_amount
    
    # Calculer le facteur de réduction proportionnel
    discount_factor = 1 - (discount_amount / subtotal) if subtotal > 0 else 1
    
    items_json = json.dumps(data['items'])
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Rendre l'email optionnel (peut être vide ou None)
    client_email = data.get('client_email', '') or ''
    
    # Insérer la commande avec le total réduit
    execute_query(cursor,"""
        INSERT INTO orders (order_number, client_name, client_phone, client_email, client_address, items, total, status, stock_deducted)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0)
    """, (order_number, data['client_name'], data['client_phone'], client_email, 
          data['client_address'], items_json, total))
    
    order_id = cursor.lastrowid
    
    # ========== AJOUTER LE LOG DANS user_logs ==========
    # Utiliser l'ID du client connecté ou 0 pour anonyme
    user_id = session.get('client_id', 0)
    
    execute_query(cursor,"""
        INSERT INTO user_logs (user_id, action, ip_address)
        VALUES (?, ?, ?)
    """, (user_id, f"commande: {order_number} - {data['client_name']} - {total:.2f} DNT", request.remote_addr))
    # ====================================
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'order_number': order_number})


# ==================== API AVIS ADMIN ====================

@app.route('/admin/reviews')
@login_required
def admin_reviews():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"""
        SELECT r.*, p.name as product_name 
        FROM reviews r
        LEFT JOIN products p ON r.product_id = p.id
        ORDER BY r.date DESC
    """)
    reviews = cursor.fetchall()
    conn.close()
    return jsonify(reviews)

@app.route('/admin/review/<int:review_id>', methods=['DELETE'])
@login_required
def admin_review_delete(review_id):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"DELETE FROM reviews WHERE id=?", (review_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ==================== API PARAMÈTRES ====================

@app.route('/admin/settings')
@login_required
def admin_settings():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT key, value FROM settings")
    settings_rows = cursor.fetchall()
    settings = {row['key']: row['value'] for row in settings_rows}
    conn.close()
    return jsonify(settings)

@app.route('/admin/settings', methods=['POST'])
@login_required
def admin_settings_save():
    conn = get_db()
    cursor = conn.cursor()
    
    for key, value in request.form.items():
        # Version compatible PostgreSQL et SQLite
        if os.environ.get('DATABASE_URL'):
            # PostgreSQL
            execute_query(cursor, """
                INSERT INTO settings (key, value) 
                VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (key, value))
        else:
            # SQLite
            execute_query(cursor, "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ==================== PAGES FRONT ====================

@app.route('/products')
def products_page():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM products WHERE active=1 ORDER BY created_at DESC")
    products = cursor.fetchall()
    execute_query(cursor,"SELECT key, value FROM settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    execute_query(cursor,"SELECT * FROM categories WHERE active=1 ORDER BY order_position")
    categories = cursor.fetchall()
    
    for cat in categories:
        execute_query(cursor,"SELECT * FROM subcategories WHERE category_id=? ORDER BY name", (cat['id'],))
        cat['subcategories'] = cursor.fetchall()
    
    conn.close()
    return render_template_string('index.html', 
                                  products=products, 
                                  categories=categories,
                                  settings=settings, 
                                  page_title='products')

@app.route('/promotions')
def promotions_page():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM products WHERE prix_promo IS NOT NULL AND prix_promo > 0 AND active=1")
    products = cursor.fetchall()
    execute_query(cursor,"SELECT key, value FROM settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    execute_query(cursor,"SELECT * FROM categories WHERE active=1 ORDER BY order_position")
    categories = cursor.fetchall()
    
    for cat in categories:
        execute_query(cursor,"SELECT * FROM subcategories WHERE category_id=? ORDER BY name", (cat['id'],))
        cat['subcategories'] = cursor.fetchall()
    
    conn.close()
    return render_template('index.html', 
                          products=products,
                          categories=categories,
                          settings=settings, 
                          page_title='promotions')
@app.route('/about')
def about_page():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT value FROM settings WHERE key='about_text'")
    row = cursor.fetchone()
    about_text = row['value'] if row else "New Decors est votre spécialiste de la décoration d'intérieur en Tunisie."
    
    execute_query(cursor,"SELECT * FROM team_members WHERE active=1 ORDER BY order_position")
    team_members = cursor.fetchall()
    
    execute_query(cursor,"SELECT key, value FROM settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    
    execute_query(cursor,"SELECT * FROM categories WHERE active=1 ORDER BY order_position")
    categories = cursor.fetchall()
    
    for cat in categories:
        execute_query(cursor,"SELECT * FROM subcategories WHERE category_id=? ORDER BY name", (cat['id'],))
        cat['subcategories'] = cursor.fetchall()
    
    conn.close()
    
    return render_template_string(HTML_ABOUT, 
                                  about_text=about_text,
                                  settings=settings,
                                  categories=categories,
                                  team_members=team_members)

@app.route('/contact')
def contact_page():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT key, value FROM settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    
    execute_query(cursor,"SELECT * FROM categories WHERE active=1 ORDER BY order_position")
    categories = cursor.fetchall()
    
    for cat in categories:
        execute_query(cursor,"SELECT * FROM subcategories WHERE category_id=? ORDER BY name", (cat['id'],))
        cat['subcategories'] = cursor.fetchall()
    
    conn.close()
    
    return render_template_string(HTML_CONTACT, 
                                  settings=settings,
                                  categories=categories)

@app.route('/product/<slug>')
def product_detail(slug):
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupérer le produit
    execute_query(cursor,"SELECT * FROM products WHERE slug=? AND active=1", (slug,))
    product = cursor.fetchone()
    if not product:
        return "Produit non trouvé", 404
     
    if not product['image']:
        product['image'] = 'default.jpg'
    
    # Récupérer les images de la galerie
    execute_query(cursor,"SELECT * FROM product_images WHERE product_id=? ORDER BY order_position", (product['id'],))
    product_images = cursor.fetchall()
    
    # Récupérer la catégorie
    execute_query(cursor,"""
        SELECT c.id, c.name, c.slug FROM categories c
        LEFT JOIN subcategories s ON s.category_id = c.id
        WHERE s.id = ?
    """, (product['subcategory_id'],))
    category = cursor.fetchone()
    
    # Produits similaires
    if category:
        execute_query(cursor,"""
            SELECT p.* FROM products p
            LEFT JOIN subcategories s ON p.subcategory_id = s.id
            WHERE s.category_id = ? AND p.id != ? AND p.active=1
            LIMIT 4
        """, (category['id'], product['id']))
        similar_products = cursor.fetchall()
    else:
        similar_products = []
    
    # Avis
    execute_query(cursor,"SELECT * FROM reviews WHERE product_id=? AND approved=1 ORDER BY date DESC", (product['id'],))
    reviews = cursor.fetchall()
    
    # Catégories pour le menu avec sous-catégories
    execute_query(cursor,"SELECT * FROM categories WHERE active=1 ORDER BY order_position")
    categories = cursor.fetchall()
    
    for cat in categories:
        execute_query(cursor,"SELECT * FROM subcategories WHERE category_id=? ORDER BY name", (cat['id'],))
        cat['subcategories'] = cursor.fetchall()
    
    # Paramètres
    execute_query(cursor,"SELECT key, value FROM settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    
    conn.close()
    
    avg_rating = sum(r['rating'] for r in reviews) / len(reviews) if reviews else 0
    
    return render_template('product_detail.html',
                              product=product,
                              product_images=product_images,
                              category=category,
                              similar_products=similar_products,
                              reviews=reviews,
                              avg_rating=avg_rating,
                              categories=categories,
                              settings=settings)

@app.route('/category/<slug>')
def category_page(slug):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT id, name, description FROM categories WHERE slug=?", (slug,))
    cat = cursor.fetchone()
    if not cat:
        return "Catégorie non trouvée", 404
    
    execute_query(cursor,"""
        SELECT p.* FROM products p
        LEFT JOIN subcategories s ON p.subcategory_id = s.id
        WHERE s.category_id = ? AND p.active=1
        ORDER BY p.created_at DESC
    """, (cat['id'],))
    products = cursor.fetchall()
    
    execute_query(cursor,"SELECT * FROM categories WHERE active=1 ORDER BY order_position")
    categories = cursor.fetchall()
    
    for c in categories:
        execute_query(cursor,"SELECT * FROM subcategories WHERE category_id=? ORDER BY name", (c['id'],))
        c['subcategories'] = cursor.fetchall()
    
    execute_query(cursor,"SELECT key, value FROM settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    conn.close()
    
    return render_template('index.html', 
                              products=products, 
                              categories=categories,
                              settings=settings, 
                              category_name=cat['name'],
                              category_description=cat['description'] or '')

# ==================== API ÉQUIPE ====================

@app.route('/admin/team', methods=['GET'])
@login_required
def admin_team():
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT * FROM team_members  ORDER BY order_position")
    team = cursor.fetchall()
    conn.close()
    return jsonify(team)

@app.route('/admin/team', methods=['POST'])
@login_required
def admin_team_save():
    team_id = request.form.get('id')
    name = request.form.get('name')
    position = request.form.get('position')
    bio = request.form.get('bio', '')
    email = request.form.get('email', '')
    order_position = int(request.form.get('order_position', 0))
    active = 1 if request.form.get('active') else 0
    
    image_file = request.files.get('image')
    image_name = None
    if image_file and image_file.filename:
        image_name = save_image(image_file, 'medium')
    
    conn = get_db()
    cursor = conn.cursor()
    
    if team_id:
        if image_name:
            execute_query(cursor,"""
                UPDATE team_members SET name=?, position=?, bio=?, email=?, image=?, order_position=?, active=?
                WHERE id=?
            """, (name, position, bio, email, image_name, order_position, active, team_id))
        else:
            execute_query(cursor,"""
                UPDATE team_members SET name=?, position=?, bio=?, email=?, order_position=?, active=?
                WHERE id=?
            """, (name, position, bio, email, order_position, active, team_id))
    else:
        execute_query(cursor,"""
            INSERT INTO team_members (name, position, bio, email, image, order_position, active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, position, bio, email, image_name, order_position, active))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/team/<int:team_id>', methods=['DELETE'])
@login_required
def admin_team_delete(team_id):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"DELETE FROM team_members WHERE id=?", (team_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ============ API HISTORIQUE =========

@app.route('/admin/history/sales', methods=['POST'])
@login_required
def admin_history_sales():
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    sale_type = data.get('sale_type', 'all')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupérer toutes les dates entre start_date et end_date
    execute_query(cursor,"""
        WITH RECURSIVE dates(date) AS (
            SELECT ?
            UNION ALL
            SELECT date(date, '+1 day')
            FROM dates
            WHERE date < ?
        )
        SELECT date FROM dates
    """, (start_date, end_date))
    all_dates = [row['date'] for row in cursor.fetchall()]
    
    result_dict = {}
    for d in all_dates:
        result_dict[d] = {'sale_date': d, 'nb_orders': 0, 'nb_direct_sales': 0, 'total_ca': 0}
    
    # Ventes depuis stock_out
    if sale_type == 'all' or sale_type == 'order':
        execute_query(cursor,"""
            SELECT 
                date(so.date) as sale_date,
                COUNT(*) as nb_orders,
                COALESCE(SUM(so.total), 0) as total_ca
            FROM stock_out so
            WHERE date(so.date) BETWEEN ? AND ? AND so.sale_type = 'order'
            GROUP BY date(so.date)
        """, (start_date, end_date))
        for row in cursor.fetchall():
            if row['sale_date'] in result_dict:
                result_dict[row['sale_date']]['nb_orders'] = row['nb_orders']
                result_dict[row['sale_date']]['total_ca'] += row['total_ca']
    
    if sale_type == 'all' or sale_type == 'direct':
        execute_query(cursor,"""
            SELECT 
                date(so.date) as sale_date,
                COUNT(*) as nb_direct_sales,
                COALESCE(SUM(so.total), 0) as total_ca
            FROM stock_out so
            WHERE date(so.date) BETWEEN ? AND ? AND so.sale_type = 'direct'
            GROUP BY date(so.date)
        """, (start_date, end_date))
        for row in cursor.fetchall():
            if row['sale_date'] in result_dict:
                result_dict[row['sale_date']]['nb_direct_sales'] = row['nb_direct_sales']
                result_dict[row['sale_date']]['total_ca'] += row['total_ca']
    
    # Ajouter les commandes en ligne depuis orders (pour les commandes pending qui ne sont pas encore dans stock_out)
    if sale_type == 'all' or sale_type == 'order':
        execute_query(cursor,"""
            SELECT 
                date(o.date) as sale_date,
                COUNT(*) as nb_orders_pending,
                COALESCE(SUM(o.total), 0) as total_ca_pending
            FROM orders o
            WHERE date(o.date) BETWEEN ? AND ? AND o.status = 'pending'
            GROUP BY date(o.date)
        """, (start_date, end_date))
        for row in cursor.fetchall():
            if row['sale_date'] in result_dict:
                result_dict[row['sale_date']]['nb_orders'] += row['nb_orders_pending']
                result_dict[row['sale_date']]['total_ca'] += row['total_ca_pending']
    
    # Convertir en liste triée par date décroissante
    results = sorted(result_dict.values(), key=lambda x: x['sale_date'], reverse=True)
    
    conn.close()
    return jsonify(results)

@app.route('/admin/history/purchases', methods=['POST'])
@login_required
def admin_history_purchases():
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    conn = get_db()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            date(date) as purchase_date,
            COUNT(*) as nb_purchases,
            SUM(quantity) as total_quantity,
            SUM(total) as total_amount
        FROM stock_in
        WHERE date(date) BETWEEN ? AND ?
        GROUP BY date(date)
        ORDER BY date(date) DESC
    """
    execute_query(cursor,query, (start_date, end_date))
    purchases = cursor.fetchall()
    conn.close()
    return jsonify(purchases)

@app.route('/admin/history/products', methods=['POST'])
@login_required
def admin_history_products():
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    conn = get_db()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            p.name as product_name,
            p.reference,
            SUM(so.quantity) as total_sold,
            SUM(so.total) as total_revenue,
            SUM(so.profit) as total_profit
        FROM stock_out so
        JOIN products p ON so.product_id = p.id
        WHERE date(so.date) BETWEEN ? AND ?
        GROUP BY so.product_id
        ORDER BY total_sold DESC
        LIMIT 20
    """
    execute_query(cursor,query, (start_date, end_date))
    products = cursor.fetchall()
    conn.close()
    return jsonify(products)
@app.route('/admin/history/export')
@login_required
def admin_history_export():
    import csv
    from io import StringIO
    from flask import make_response
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    sale_type = request.args.get('sale_type', 'all')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupérer d'abord les ventes
    if sale_type != 'all':
        execute_query(cursor,"""
            SELECT so.*, p.name as product_name
            FROM stock_out so
            LEFT JOIN products p ON so.product_id = p.id
            WHERE date(so.date) BETWEEN ? AND ? AND so.sale_type = ?
            ORDER BY so.date DESC
        """, (start_date, end_date, sale_type))
    else:
        execute_query(cursor,"""
            SELECT so.*, p.name as product_name
            FROM stock_out so
            LEFT JOIN products p ON so.product_id = p.id
            WHERE date(so.date) BETWEEN ? AND ?
            ORDER BY so.date DESC
        """, (start_date, end_date))
    
    data = cursor.fetchall()
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output, delimiter=';')
    
    # En-têtes
    writer.writerow(['Date', 'Type', 'Client', 'Téléphone', 'Email', 'Produit', 'Quantité', 'Prix unitaire', 'Total', 'Bénéfice', 'Vendeur'])
    
    for row in data:
        # Déterminer le type
        type_vente = 'Commande en ligne' if row.get('sale_type') == 'order' else 'Vente directe'
        
        writer.writerow([
            row['date'],
            type_vente,
            row['client_name'],
            row['client_phone'],
            row['client_email'] or '-',
            row['product_name'] or 'Produit inconnu',
            row['quantity'],
            f"{row['sale_price']:.2f}",
            f"{row['total']:.2f}",
            f"{row['profit']:.2f}",
            row.get('seller_name') or 'Système'
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = f'attachment; filename=export_ventes_{start_date}_{end_date}.csv'
    return response
@app.route('/admin/history/summary')
@login_required
def admin_history_summary():
    """Récupère toutes les données pour le résumé global"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Récupérer les ventes
    execute_query(cursor,"""
        SELECT 
            date(date) as sale_date,
            COUNT(CASE WHEN sale_type = 'order' THEN 1 END) as nb_orders,
            COUNT(CASE WHEN sale_type = 'direct' THEN 1 END) as nb_direct_sales,
            SUM(total) as total_ca,
            SUM(CASE WHEN sale_type = 'direct' THEN total ELSE 0 END) as direct_ca,
            SUM(profit) as total_profit
        FROM stock_out
        WHERE date(date) BETWEEN ? AND ?
        GROUP BY date(date)
        ORDER BY date(date) DESC
    """, (start_date, end_date))
    sales = cursor.fetchall()
    
    # 2. Récupérer les achats
    execute_query(cursor,"""
        SELECT 
            date(date) as purchase_date,
            COUNT(*) as nb_purchases,
            SUM(quantity) as total_quantity,
            SUM(total) as total_amount
        FROM stock_in
        WHERE date(date) BETWEEN ? AND ?
        GROUP BY date(date)
        ORDER BY date(date) DESC
    """, (start_date, end_date))
    purchases = cursor.fetchall()
    
    # 3. Récupérer les top produits
    execute_query(cursor,"""
        SELECT 
            p.name as product_name,
            p.reference,
            SUM(so.quantity) as total_sold,
            SUM(so.total) as total_revenue,
            SUM(so.profit) as total_profit
        FROM stock_out so
        JOIN products p ON so.product_id = p.id
        WHERE date(so.date) BETWEEN ? AND ?
        GROUP BY so.product_id
        ORDER BY total_sold DESC
        LIMIT 10
    """, (start_date, end_date))
    products = cursor.fetchall()
    
    # 4. Récupérer les performances vendeurs
    execute_query(cursor,"""
        SELECT 
            COALESCE(seller_name, 'Client en ligne') as seller_name,
            COUNT(*) as total_sales,
            SUM(quantity) as total_quantity,
            SUM(total) as total_ca,
            SUM(profit) as total_profit
        FROM stock_out
        WHERE date(date) BETWEEN ? AND ?
        GROUP BY seller_name
        ORDER BY total_ca DESC
    """, (start_date, end_date))
    sellers = cursor.fetchall()
    
    conn.close()
    
    return jsonify({
        'sales': sales,
        'purchases': purchases,
        'products': products,
        'sellers': sellers
    })
@app.route('/admin/history/sales/detailed')
@login_required
def admin_history_sales_detailed():
    """Récupère les ventes ligne par ligne"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    sale_type = request.args.get('sale_type', 'all')
    
    conn = get_db()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            so.date,
            so.sale_type,
            so.client_name,
            so.client_phone,
            so.client_email,
            p.name as product_name,
            p.reference as product_reference,
            so.quantity,
            so.sale_price,
            so.total,
            so.profit,
            so.seller_name as vendeur,
            so.order_number
        FROM stock_out so
        LEFT JOIN products p ON so.product_id = p.id
        WHERE date(so.date) BETWEEN ? AND ?
    """
    params = [start_date, end_date]
    
    if sale_type != 'all':
        query += " AND so.sale_type = ?"
        params.append(sale_type)
    
    query += " ORDER BY so.date DESC, so.id DESC"
    
    execute_query(cursor,query, params)
    sales = cursor.fetchall()
    conn.close()
    
    return jsonify(sales)

# ============ LOGS SYSTEME (utilisant user_logs) ============

@app.route('/admin/check-role')
@login_required
def admin_check_role():
    return jsonify({'is_admin': session.get('role') == 'admin'})

@app.route('/admin/logs/filters')
@login_required
def admin_logs_filters():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Non autorisé'}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT id, username FROM users ORDER BY username")
    users = cursor.fetchall()
    conn.close()
    
    return jsonify({'users': users})

@app.route('/admin/logs', methods=['POST'])
@login_required
def admin_logs():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Non autorisé'}), 403
    
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    user_id = data.get('user_id')
    action_type = data.get('action_type')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # ========== REQUÊTE PRINCIPALE ==========
    query = """
        SELECT 
            ul.id,
            ul.user_id,
            u.username,
            ul.action,
            ul.ip_address,
            ul.date as created_at
        FROM user_logs ul
        LEFT JOIN users u ON ul.user_id = u.id
        WHERE 1=1
    """
    params = []
    
    if start_date:
        query += " AND date(ul.date) >= %s"
        params.append(start_date)
    if end_date:
        query += " AND date(ul.date) <= %s"
        params.append(end_date)
    if user_id and user_id != 'all':
        query += " AND ul.user_id = %s"
        params.append(user_id)
    if action_type and action_type != 'all':
        query += " AND ul.action LIKE %s"
        params.append(f"%{action_type}%")
    
    query += " ORDER BY ul.date DESC LIMIT 500"
    
    # Exécution
    if params:
        execute_query(cursor, query, params)
    else:
        execute_query(cursor, query)
    logs = cursor.fetchall()
    
    # ========== STATISTIQUES ==========
    # Total des logs (avec filtres)
    stats_query = "SELECT COUNT(*) as total FROM user_logs ul WHERE 1=1"
    stats_params = []
    
    if start_date:
        stats_query += " AND date(ul.date) >= %s"
        stats_params.append(start_date)
    if end_date:
        stats_query += " AND date(ul.date) <= %s"
        stats_params.append(end_date)
    if user_id and user_id != 'all':
        stats_query += " AND ul.user_id = %s"
        stats_params.append(user_id)
    
    if stats_params:
        execute_query(cursor, stats_query, stats_params)
    else:
        execute_query(cursor, stats_query)
    total = cursor.fetchone()['total']
    
    # Stats par type (sans filtres de type pour éviter les doublons)
    execute_query(cursor, "SELECT COUNT(*) as total FROM user_logs WHERE action LIKE '%vente%' OR action LIKE '%sale%'")
    sales = cursor.fetchone()['total']
    
    execute_query(cursor, "SELECT COUNT(*) as total FROM user_logs WHERE action LIKE '%achat%' OR action LIKE '%purchase%' OR action LIKE '%stock-in%'")
    purchases = cursor.fetchone()['total']
    
    execute_query(cursor, "SELECT COUNT(*) as total FROM user_logs WHERE action LIKE '%promo%'")
    promos = cursor.fetchone()['total']
    
    execute_query(cursor, "SELECT COUNT(*) as total FROM user_logs WHERE action LIKE '%commande%' OR action LIKE '%order%'")
    orders = cursor.fetchone()['total']
    
    execute_query(cursor, "SELECT COUNT(*) as total FROM user_logs WHERE action LIKE '%login%' OR action LIKE '%logout%'")
    users_count = cursor.fetchone()['total']
    
    conn.close()
    
    return jsonify({
        'logs': logs,
        'stats': {
            'total': total,
            'sales': sales,
            'purchases': purchases,
            'promos': promos,
            'orders': orders,
            'users': users_count
        }
    })
    
    def run_count_query(extra_condition):
        if extra_condition:
            full_query = f"SELECT COUNT(*) as total FROM user_logs ul{where_clause} AND {extra_condition}"
        else:
            full_query = f"SELECT COUNT(*) as total FROM user_logs ul{where_clause}"
        
        # Vérifier si on a des paramètres
        if filter_params:
            execute_query(cursor, full_query, filter_params)
        else:
            execute_query(cursor, full_query)
        
        result = cursor.fetchone()
        return result['total'] if result else 0
    
    total = run_count_query("")
    sales = run_count_query("(ul.action LIKE '%vente%' OR ul.action LIKE '%sale%')")
    purchases = run_count_query("(ul.action LIKE '%achat%' OR ul.action LIKE '%purchase%' OR ul.action LIKE '%stock-in%')")
    promos = run_count_query("ul.action LIKE '%promo%'")
    orders = run_count_query("(ul.action LIKE '%commande%' OR ul.action LIKE '%order%')")
    users_count = run_count_query("(ul.action LIKE '%login%' OR ul.action LIKE '%logout%')")
    
    conn.close()
    
    return jsonify({
        'logs': logs,
        'stats': {
            'total': total,
            'sales': sales,
            'purchases': purchases,
            'promos': promos,
            'orders': orders,
            'users': users_count
        }
    })
@app.route('/admin/logs/clear', methods=['DELETE'])
@login_required
def admin_logs_clear():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Non autorisé'}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"DELETE FROM user_logs")
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# ==================== impression ====================
@app.route('/admin/stock-out/print')
@login_required
def admin_stock_out_print():
    """Page d'impression des ventes"""
    if session.get('role') not in ['admin', 'vendeur']:
        return redirect(url_for('index'))
    
    # Récupérer les paramètres
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    sale_type = request.args.get('sale_type', 'all')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Construire la requête
    query = """
        SELECT 
            so.date,
            so.sale_type,
            so.client_name,
            so.client_phone,
            p.name as product_name,
            so.quantity,
            so.sale_price,
            so.total,
            so.profit,
            so.seller_name
        FROM stock_out so
        LEFT JOIN products p ON so.product_id = p.id
        WHERE 1=1
    """
    params = []
    
    if start_date:
        query += " AND date(so.date) >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date(so.date) <= ?"
        params.append(end_date)
    if sale_type != 'all':
        query += " AND so.sale_type = ?"
        params.append(sale_type)
    
    query += " ORDER BY so.date DESC"
    
    execute_query(cursor,query, params)
    sales = cursor.fetchall()
    
    # Calculer les totaux
    total_quantity = sum(s['quantity'] for s in sales) if sales else 0
    total_revenue = sum(s['total'] for s in sales) if sales else 0
    total_profit = sum(s['profit'] for s in sales) if sales else 0
    
    conn.close()
    
    # Récupérer les paramètres pour l'affichage
    type_label = {
        'all': 'Tous',
        'direct': 'Ventes directes',
        'order': 'Commandes en ligne'
    }.get(sale_type, 'Tous')
    
    from datetime import datetime
    now = datetime.now()
    
    return render_template_string(HTML_PRINT_STOCK, 
                                  sales=sales,
                                  start_date=start_date,
                                  end_date=end_date,
                                  sale_type=type_label,
                                  total_quantity=total_quantity,
                                  total_revenue=total_revenue,
                                  total_profit=total_profit,
                                  now=now)
@app.route('/admin/migrate-to-supabase')
@login_required
def migrate_to_supabase():
    if session.get('role') != 'admin':
        return "Non autorisé", 403
    
    # Lire la base SQLite
    sqlite_conn = sqlite3.connect('new_decors.db')
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    
    # Connexion Supabase
    supabase_conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    supabase_cursor = supabase_conn.cursor()
    
    tables = ['users', 'products', 'categories', 'subcategories', 'orders']
    results = {}
    
    for table in tables:
        try:
            sqlite_execute_query(cursor,f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()
            
            for row in rows:
                columns = list(row.keys())
                values = [row[col] for col in columns]
                placeholders = ','.join(['%s'] * len(columns))
                columns_str = ','.join(columns)
                
                supabase_execute_query(cursor,f"""
                    INSERT INTO {table} ({columns_str}) 
                    VALUES ({placeholders})
                    ON CONFLICT (id) DO NOTHING
                """, values)
            
            supabase_conn.commit()
            results[table] = f"{len(rows)} lignes migrées"
        except Exception as e:
            results[table] = f"Erreur: {str(e)[:50]}"
    
    sqlite_conn.close()
    supabase_conn.close()
    
    return jsonify(results)
def init_db_if_needed():
    """Initialise la base de données si elle n'existe pas"""
    if not os.path.exists(DATABASE):
        print("📦 Base de données non trouvée, création...")
        init_db()
        print("✅ Base de données créée avec succès")
    else:
        print("✅ Base de données déjà existante")
# Pour Render (Gunicorn) - s'exécute au démarrage
if os.environ.get('RENDER'):
    print("🚀 Démarrage sur Render...")
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        # Vérifier si les tables existent déjà
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1 FROM users LIMIT 1")
            print("✅ Tables PostgreSQL déjà existantes")
        except:
            print("📦 Création des tables PostgreSQL...")
            init_postgres_tables()
        finally:
            conn.close()
        print("✅ PostgreSQL prêt")
    else:
        init_db_if_needed()
        migrate_orders()
        print("✅ SQLite prêt")

if __name__ == '__main__':
    # Éviter de réinitialiser la base au démarrage local si elle existe déjà
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        init_db_if_needed()
        migrate_orders()
    
    # Afficher le chemin de la base de données au démarrage
    print(f"📁 Base de données utilisée: {DATABASE}")
    print(f"📁 Dossier existe: {os.path.exists(os.path.dirname(DATABASE) if os.path.dirname(DATABASE) else '.')}")
          
    print("""
    ╔══════════════════════════════════════════════╗
    ║     NEW DECORS - Site E-commerce Complet     ║
    ╠══════════════════════════════════════════════╣
    ║  🌐 Site: http://localhost:5000             ║
    ║  🔐 Admin: http://localhost:5000/login      ║
    ║  👤 Identifiant: admin / admin123           ║
    ╚══════════════════════════════════════════════╝
    """)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
