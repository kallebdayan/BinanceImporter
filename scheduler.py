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
