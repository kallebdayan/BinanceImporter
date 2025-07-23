# config.py
"""
Arquivo de configuração para o importador da Binance
"""

import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração do banco de dados
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_NAME', 'binanceimporter'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'charset': 'utf8mb4',
    'autocommit': False,
    'use_unicode': True
}

# Configurações da API
BINANCE_CONFIG = {
    'base_url': 'https://api.binance.com',
    'timeout': 30,
    'max_retries': 3,
    'retry_delay': 1
}

# Configurações de logging
LOGGING_CONFIG = {
    'level': 'DEBUG',
#    'level': 'INFO',
    'format': '%(asctime)s - %(levelname)s - %(message)s',
    'encoding': 'utf-8',
    'log_file': 'binance_importer.log',
    'max_log_size': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5
}