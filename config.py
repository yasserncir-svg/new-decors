# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Base de données
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///new_decors.db')
    
    # Uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
    
    # Secrets
    SECRET_KEY = os.environ.get('SECRET_KEY', 'new_decors_secret_key_2024')
    
    # Environnement
    DEBUG = os.environ.get('DEBUG', 'False') == 'True'
    
    # Pour Render
    RENDER = os.environ.get('RENDER', 'False') == 'True'

config = Config()
