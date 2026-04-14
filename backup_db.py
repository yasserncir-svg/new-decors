#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de sauvegarde automatique de la base de données
"""

import os
import shutil
from datetime import datetime

def backup_database():
    """Sauvegarde la base de données avant les mises à jour"""
    db_file = 'new_decors.db'
    backup_dir = 'backups'
    
    # Créer le dossier backups s'il n'existe pas
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        # Ajouter un fichier .gitkeep pour garder le dossier dans Git
        with open(os.path.join(backup_dir, '.gitkeep'), 'w') as f:
            f.write('')
    
    if os.path.exists(db_file):
        # Créer un nom de fichier avec la date
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(backup_dir, f'backup_{timestamp}.db')
        
        # Copier la base de données
        shutil.copy2(db_file, backup_file)
        print(f"✅ Base sauvegardée : {backup_file}")
        
        # Garder seulement les 10 dernières sauvegardes
        backups = sorted([f for f in os.listdir(backup_dir) if f.startswith('backup_') and f.endswith('.db')])
        if len(backups) > 10:
            for old_backup in backups[:-10]:
                os.remove(os.path.join(backup_dir, old_backup))
                print(f"🗑️ Ancienne sauvegarde supprimée : {old_backup}")
        
        return backup_file
    else:
        print("⚠️ Base de données non trouvée")
        return None

def restore_database(backup_file):
    """Restaure une sauvegarde"""
    if os.path.exists(backup_file):
        shutil.copy2(backup_file, 'new_decors.db')
        print(f"✅ Base restaurée depuis : {backup_file}")
        return True
    else:
        print(f"❌ Fichier de sauvegarde non trouvé : {backup_file}")
        return False

def list_backups():
    """Liste toutes les sauvegardes disponibles"""
    backup_dir = 'backups'
    if not os.path.exists(backup_dir):
        print("📁 Aucun dossier de sauvegarde")
        return []
    
    backups = sorted([f for f in os.listdir(backup_dir) if f.startswith('backup_') and f.endswith('.db')], reverse=True)
    
    if backups:
        print("\n📋 Sauvegardes disponibles :")
        for i, backup in enumerate(backups, 1):
            size = os.path.getsize(os.path.join(backup_dir, backup)) / 1024
            print(f"  {i}. {backup} ({size:.1f} KB)")
    else:
        print("📭 Aucune sauvegarde trouvée")
    
    return backups

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'restore' and len(sys.argv) > 2:
            restore_database(sys.argv[2])
        elif sys.argv[1] == 'list':
            list_backups()
        else:
            print("Usage:")
            print("  python backup_db.py              # Sauvegarde")
            print("  python backup_db.py list         # Liste des sauvegardes")
            print("  python backup_db.py restore <file> # Restauration")
    else:
        backup_database()
