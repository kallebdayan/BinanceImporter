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
    'user': os.getenv('DB_USER', 'binanceimporter'),
    'password': os.getenv('DB_PASSWORD', 'Ak50z6Xe7kkxNE)S'),
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
    'level': 'INFO',
    'format': '%(asctime)s - %(levelname)s - %(message)s',
    'log_file': 'binance_importer.log',
    'max_log_size': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5
}

# scheduler.py
"""
Script para automatizar a execução do importador da Binance
"""

import schedule
import time
import logging
from datetime import datetime
import subprocess
import sys
import os

# Configuração de logging para o scheduler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler()
    ]
)

class BinanceScheduler:
    def __init__(self):
        self.script_path = os.path.join(os.path.dirname(__file__), 'binance_importer.py')
        
    def run_import(self):
        """Executa o script de importação"""
        try:
            logging.info("Iniciando execução programada do importador...")
            
            result = subprocess.run([
                sys.executable, self.script_path
            ], capture_output=True, text=True, timeout=1800)  # 30 minutos timeout
            
            if result.returncode == 0:
                logging.info("Importação executada com sucesso")
                if result.stdout:
                    logging.info(f"Output: {result.stdout}")
            else:
                logging.error(f"Erro na importação. Return code: {result.returncode}")
                if result.stderr:
                    logging.error(f"Error: {result.stderr}")
                    
        except subprocess.TimeoutExpired:
            logging.error("Timeout na execução do importador (30 minutos)")
        except Exception as e:
            logging.error(f"Erro ao executar importador: {e}")
    
    def start_scheduler(self):
        """Inicia o agendador"""
        # Executa a cada 4 horas
        schedule.every(4).hours.do(self.run_import)
        
        # Executa diariamente às 06:00
        schedule.every().day.at("06:00").do(self.run_import)
        
        # Executa primeira vez imediatamente
        logging.info("Executando importação inicial...")
        self.run_import()
        
        logging.info("Scheduler iniciado. Pressione Ctrl+C para parar.")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Verifica a cada minuto
        except KeyboardInterrupt:
            logging.info("Scheduler interrompido pelo usuário")

if __name__ == "__main__":
    scheduler = BinanceScheduler()
    scheduler.start_scheduler()


# requirements.txt
"""
Dependências do projeto
"""
# requirements.txt content:
"""
requests>=2.28.0
mysql-connector-python>=8.0.32
python-dotenv>=1.0.0
schedule>=1.2.0
"""


# .env.example
"""
Exemplo de arquivo de configuração de ambiente
Copie para .env e ajuste os valores
"""
# .env.example content:
"""
# Configurações do Banco de Dados MySQL
DB_HOST=localhost
DB_PORT=3306
DB_NAME=binance_crypto
DB_USER=seu_usuario
DB_PASSWORD=sua_senha

# Configurações opcionais
LOG_LEVEL=INFO
MAX_RETRIES=3
TIMEOUT=30
"""


# monitor.py
"""
Script para monitorar o status do banco e das importações
"""

import mysql.connector
from config import DATABASE_CONFIG
import logging
from datetime import datetime, timedelta

class BinanceMonitor:
    def __init__(self):
        self.db_config = DATABASE_CONFIG
        
    def connect_database(self):
        """Conecta ao banco de dados"""
        try:
            return mysql.connector.connect(**self.db_config)
        except mysql.connector.Error as e:
            logging.error(f"Erro ao conectar ao banco: {e}")
            return None
    
    def check_last_update(self):
        """Verifica quando foi a última atualização"""
        connection = self.connect_database()
        if not connection:
            return None
            
        cursor = connection.cursor(dictionary=True)
        
        try:
            # Última atualização na tabela coins
            cursor.execute("""
                SELECT MAX(updated_at) as last_update, COUNT(*) as total
                FROM coins
            """)
            coins_info = cursor.fetchone()
            
            # Última atualização na tabela tokens
            cursor.execute("""
                SELECT MAX(updated_at) as last_update, COUNT(*) as total
                FROM tokens
            """)
            tokens_info = cursor.fetchone()
            
            return {
                'coins': coins_info,
                'tokens': tokens_info
            }
            
        finally:
            cursor.close()
            connection.close()
    
    def get_trading_pairs_summary(self):
        """Retorna resumo dos pares de trading"""
        connection = self.connect_database()
        if not connection:
            return None
            
        cursor = connection.cursor(dictionary=True)
        
        try:
            # Resumo por quote asset
            cursor.execute("""
                SELECT 
                    quote_asset,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'TRADING' THEN 1 ELSE 0 END) as trading,
                    SUM(CASE WHEN is_spot_trading_allowed = TRUE THEN 1 ELSE 0 END) as spot_allowed
                FROM coins
                GROUP BY quote_asset
                ORDER BY total DESC
                LIMIT 10
            """)
            quote_summary = cursor.fetchall()
            
            # Top 10 base assets em USDT
            cursor.execute("""
                SELECT 
                    base_asset,
                    symbol,
                    status,
                    is_spot_trading_allowed,
                    is_margin_trading_allowed,
                    min_notional
                FROM coins
                WHERE quote_asset = 'USDT' AND status = 'TRADING'
                ORDER BY base_asset
                LIMIT 10
            """)
            usdt_pairs = cursor.fetchall()
            
            return {
                'quote_summary': quote_summary,
                'usdt_pairs': usdt_pairs
            }
            
        finally:
            cursor.close()
            connection.close()
    
    def generate_report(self):
        """Gera relatório completo do status"""
        print("=== RELATÓRIO DE MONITORAMENTO BINANCE ===")
        print(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Informações de última atualização
        last_update_info = self.check_last_update()
        if last_update_info:
            print("📊 ÚLTIMA ATUALIZAÇÃO:")
            
            coins_info = last_update_info['coins']
            if coins_info['last_update']:
                print(f"   Coins: {coins_info['last_update']} ({coins_info['total']} registros)")
            else:
                print(f"   Coins: Nunca atualizado ({coins_info['total']} registros)")
            
            tokens_info = last_update_info['tokens']
            if tokens_info['last_update']:
                print(f"   Tokens: {tokens_info['last_update']} ({tokens_info['total']} registros)")
            else:
                print(f"   Tokens: Nunca atualizado ({tokens_info['total']} registros)")
            print()
        
        # Resumo dos pares de trading
        summary = self.get_trading_pairs_summary()
        if summary:
            print("💱 RESUMO POR QUOTE ASSET:")
            for item in summary['quote_summary']:
                print(f"   {item['quote_asset']}: {item['total']} total, "
                      f"{item['trading']} trading, {item['spot_allowed']} spot")
            print()
            
            print("🎯 TOP PARES USDT ATIVOS:")
            for pair in summary['usdt_pairs']:
                margin_status = "✓" if pair['is_margin_trading_allowed'] else "✗"
                print(f"   {pair['symbol']} - Status: {pair['status']} "
                      f"- Margin: {margin_status} - Min: {pair['min_notional']}")
            print()
        
        print("=== FIM DO RELATÓRIO ===")

if __name__ == "__main__":
    monitor = BinanceMonitor()
    monitor.generate_report()


# install.py
"""
Script de instalação e configuração inicial
"""

import os
import subprocess
import sys
import mysql.connector
from pathlib import Path

def install_requirements():
    """Instala as dependências"""
    print("📦 Instalando dependências...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("✅ Dependências instaladas com sucesso!")

def create_env_file():
    """Cria arquivo .env se não existir"""
    env_file = Path(".env")
    if not env_file.exists():
        print("⚙️  Criando arquivo .env...")
        
        db_host = input("Host MySQL (localhost): ") or "localhost"
        db_port = input("Porta MySQL (3306): ") or "3306"
        db_name = input("Nome do banco (binance_crypto): ") or "binance_crypto"
        db_user = input("Usuário MySQL: ")
        db_password = input("Senha MySQL: ")
        
        env_content = f"""# Configurações do Banco de Dados MySQL
DB_HOST={db_host}
DB_PORT={db_port}
DB_NAME={db_name}
DB_USER={db_user}
DB_PASSWORD={db_password}

# Configurações opcionais
LOG_LEVEL=INFO
MAX_RETRIES=3
TIMEOUT=30
"""
        
        with open(".env", "w") as f:
            f.write(env_content)
        
        print("✅ Arquivo .env criado!")
    else:
        print("ℹ️  Arquivo .env já existe")

def test_database_connection():
    """Testa conexão com o banco de dados"""
    print("🔌 Testando conexão com banco de dados...")
    
    from config import DATABASE_CONFIG
    
    try:
        connection = mysql.connector.connect(**DATABASE_CONFIG)
        print("✅ Conexão com banco de dados estabelecida!")
        connection.close()
        return True
    except mysql.connector.Error as e:
        print(f"❌ Erro na conexão: {e}")
        return False

def create_database_structure():
    """Executa os scripts SQL para criar a estrutura"""
    print("🏗️  Criando estrutura do banco de dados...")
    
    # Aqui você executaria os comandos SQL da estrutura
    # Por simplicidade, apenas mostra a mensagem
    print("ℹ️  Execute manualmente os comandos SQL fornecidos para criar as tabelas")
    print("   e triggers no seu banco MySQL.")

def main():
    """Função principal de instalação"""
    print("🚀 INSTALADOR BINANCE CRYPTO IMPORTER")
    print("=" * 40)
    
    try:
        # 1. Instalar dependências
        install_requirements()
        
        # 2. Criar arquivo .env
        create_env_file()
        
        # 3. Testar conexão
        if test_database_connection():
            # 4. Informar sobre estrutura do banco
            create_database_structure()
            
            print("\n🎉 INSTALAÇÃO CONCLUÍDA!")
            print("\nPróximos passos:")
            print("1. Execute os comandos SQL para criar tabelas e triggers")
            print("2. Execute: python binance_importer.py (importação única)")
            print("3. Execute: python scheduler.py (importação automática)")
            print("4. Execute: python monitor.py (monitoramento)")
        else:
            print("\n❌ Configuração incompleta. Verifique as configurações do banco.")
            
    except Exception as e:
        print(f"\n❌ Erro durante instalação: {e}")

if __name__ == "__main__":
    main()