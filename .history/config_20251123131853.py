import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # ✅ SECRET KEY (configure no Railway)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sua-chave-secreta-railway'
    
    # ✅ DATABASE URL (será fornecida pelo Railway)
    # NÃO definir fallback local - usar apenas Railway
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    # Se a URL começar com postgres://, converter para postgresql://
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
      
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-chave-secreta-railway'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    # Configurações da API
    API_KEYS = {
        "SUA_CHAVE_API_SECRETA": "ESP8266"
    }