#!/usr/bin/env python3
"""
BinanceImporter - Coletor de Candles
Coleta dados de candles da API da Binance para análise técnica
"""

import os
import sys
import time
import logging
import requests
import schedule
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import mysql.connector
from mysql.connector import Error as MySQLError
import json
from decimal import Decimal
import threading
from queue import Queue, Empty
import signal

# Importar configurações
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import DATABASE_CONFIG, BINANCE_CONFIG, LOGGING_CONFIG

class DatabaseManager:
    """Gerenciador de conexões com o banco de dados"""
    
    def __init__(self):
        self.connection = None
        self.connect()
    
    def connect(self):
        """Estabelece conexão com o banco de dados"""
        try:
            self.connection = mysql.connector.connect(**DATABASE_CONFIG)
            logging.info("Conexão com banco de dados estabelecida")
        except MySQLError as e:
            logging.error(f"Erro ao conectar com banco de dados: {e}")
            raise
    
    def disconnect(self):
        """Fecha conexão com banco de dados"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logging.info("Conexão com banco de dados fechada")
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = False):
        """Executa query no banco de dados"""
        try:
            if not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor(dictionary=True if fetch else False)
            cursor.execute(query, params)
            
            if fetch:
                result = cursor.fetchall()
                cursor.close()
                return result
            else:
                self.connection.commit()
                cursor.close()
                return cursor.rowcount
                
        except MySQLError as e:
            logging.error(f"Erro ao executar query: {e}")
            self.connection.rollback()
            raise
    
    def execute_many(self, query: str, data: List[tuple]):
        """Executa múltiplas inserções"""
        try:
            if not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            cursor.executemany(query, data)
            self.connection.commit()
            rows_affected = cursor.rowcount
            cursor.close()
            return rows_affected
            
        except MySQLError as e:
            logging.error(f"Erro ao executar inserções em lote: {e}")
            self.connection.rollback()
            raise

class BinanceAPI:
    """Cliente para API da Binance"""
    
    def __init__(self):
        self.base_url = BINANCE_CONFIG['base_url']
        self.timeout = BINANCE_CONFIG['timeout']
        self.max_retries = BINANCE_CONFIG['max_retries']
        self.retry_delay = BINANCE_CONFIG['retry_delay']
        self.session = requests.Session()
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Faz requisição para API com retry automático"""
        url = f"{self.base_url}{endpoint}"
        
        if params:
            param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{param_str}"
        else:
            full_url = url
        
        logging.debug(f"REQ URL: {full_url}")

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                logging.warning(f"Tentativa {attempt + 1} falhou para {endpoint}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    logging.error(f"Todas as tentativas falharam para {endpoint}")
                    raise
    



    def get_klines(self, symbol: str, interval: str, start_time: int = None, 
                   end_time: int = None, limit: int = 1000) -> List[List]:
        """Obtém dados de candles (klines) da Binance"""
        endpoint = "/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': min(limit, 1000)  # Máximo permitido pela API
        }
        
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        return self._make_request(endpoint, params)

class CandleCollector:
    """Coletor principal de dados de candles"""
    
    # Intervalos suportados pela Binance
    INTERVALS = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
    
    # Mapeamento de intervalos para milliseconds
    INTERVAL_MS = {
        '1m': 60000, '3m': 180000, '5m': 300000, '15m': 900000, '30m': 1800000,
        '1h': 3600000, '2h': 7200000, '4h': 14400000, '6h': 21600000, 
        '8h': 28800000, '12h': 43200000, '1d': 86400000, '3d': 259200000,
        '1w': 604800000, '1M': 2592000000
    }
    
    def __init__(self):
        self.db = DatabaseManager()
        self.api = BinanceAPI()
        self.stop_event = threading.Event()
        self.worker_threads = []
        self.task_queue = Queue()
        
    def get_active_tokens(self) -> List[Dict]:
        """Obtém lista de tokens ativos para trading"""
        query = """
        SELECT symbol, base_asset, quote_asset 
        FROM active_trading_tokens 
        ORDER BY symbol
        """
        return self.db.execute_query(query, fetch=True)
    
    def parse_kline_data(self, kline_data: List, symbol: str, interval: str) -> tuple:
        """Converte dados de kline da API para formato do banco"""
        return (
            symbol,
            interval,
            int(kline_data[0]),  # open_time
            int(kline_data[6]),  # close_time
            Decimal(str(kline_data[1])),  # open_price
            Decimal(str(kline_data[2])),  # high_price
            Decimal(str(kline_data[3])),  # low_price
            Decimal(str(kline_data[4])),  # close_price
            Decimal(str(kline_data[5])),  # volume
            Decimal(str(kline_data[7])),  # quote_asset_volume
            int(kline_data[8]),  # number_of_trades
            Decimal(str(kline_data[9])),  # taker_buy_base_asset_volume
            Decimal(str(kline_data[10]))  # taker_buy_quote_asset_volume
        )
    
    def insert_candles(self, candles_data: List[tuple]) -> int:
        """Insere dados de candles no banco com controle de duplicatas"""
        if not candles_data:
            return 0
        
        insert_query = """
        INSERT IGNORE INTO candles (
            symbol, interval_type, open_time, close_time, open_price, 
            high_price, low_price, close_price, volume, quote_asset_volume,
            number_of_trades, taker_buy_base_asset_volume, taker_buy_quote_asset_volume
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        return self.db.execute_many(insert_query, candles_data)
    
    def get_last_collected_time(self, symbol: str, interval: str) -> Optional[int]:
        """Obtém timestamp da última coleta da collection_control"""
        query = """
        SELECT last_collected_time FROM collection_control
        WHERE symbol = %s AND interval_type = %s
        """
        result = self.db.execute_query(query, (symbol, interval), fetch=True)
        return result[0]['last_collected_time'] if result else None


    def get_last_candle_time(self, symbol: str, interval: str) -> Optional[int]:
        """Obtém timestamp do último candle coletado"""
        query = """
        SELECT MAX(open_time) as last_time 
        FROM candles 
        WHERE symbol = %s AND interval_type = %s
        """
        result = self.db.execute_query(query, (symbol, interval), fetch=True)
        return result[0]['last_time'] if result and result[0]['last_time'] else None
    
    def update_collection_control(self, symbol: str, interval: str, 
                                 last_time: int, status: str = 'active', 
                                 error_msg: str = None):
        """Atualiza controle de coleta"""
        query = """
        INSERT INTO collection_control 
        (symbol, interval_type, last_collected_time, status, error_count, last_error)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            last_collected_time = VALUES(last_collected_time),
            status = VALUES(status),
            error_count = CASE WHEN VALUES(status) = 'error' THEN error_count + 1 ELSE 0 END,
            last_error = VALUES(last_error),
            updated_at = CURRENT_TIMESTAMP
        """
        
        error_count = 1 if status == 'error' else 0
        self.db.execute_query(query, (symbol, interval, last_time, status, error_count, error_msg))
    
    def log_collection(self, symbol: str, interval: str, collection_type: str, 
                      start_time: int, end_time: int, records: int, 
                      status: str, error_msg: str = None, exec_time: float = None):
        """Registra log de coleta"""
        query = """
        INSERT INTO collection_logs 
        (symbol, interval_type, collection_type, start_time, end_time, 
         records_collected, status, error_message, execution_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        self.db.execute_query(query, (
            symbol, interval, collection_type, start_time, end_time,
            records, status, error_msg, exec_time
        ))
    
    def collect_single_symbol(self, symbol: str, interval: str, 
                             start_time: int = None, end_time: int = None, 
                             limit: int = 1000) -> Tuple[int, str]:
        """Coleta dados para um símbolo específico"""
        collection_start = time.time()
        
        try:
            # Se não especificado, coleta últimos dados
            if start_time is None:
                last_time = self.get_last_collected_time(symbol, interval)
                if last_time:
                    start_time = last_time + self.INTERVAL_MS[interval]
                else:
                    # Primeira coleta - últimos 1000 candles
                    start_time = int((datetime.utcnow() - timedelta(days=30)).timestamp() * 1000)
            
            # Obtém dados da API
            klines = self.api.get_klines(symbol, interval, start_time, end_time, limit)
            
            if not klines:
                logging.info(f"Nenhum dado novo para {symbol} {interval}")
                return 0, "success"
            
            # Converte dados
            candles_data = []
            for kline in klines:
                # Ignora último candle se ainda não fechou (tempo atual)
                if kline[6] > int(time.time() * 1000):
                    continue
                candles_data.append(self.parse_kline_data(kline, symbol, interval))
            
            # Insere no banco
            inserted = self.insert_candles(candles_data)
            
            # Atualiza controle
            if candles_data:
                last_candle_time = max(c[2] for c in candles_data)  # open_time
                self.update_collection_control(symbol, interval, last_candle_time)
            
            # Log da coleta
            exec_time = time.time() - collection_start
            self.log_collection(
                symbol, interval, 'single', 
                start_time, end_time or int(time.time() * 1000),
                inserted, 'success', None, exec_time
            )
            
            logging.info(f"Coletados {inserted} candles para {symbol} {interval}")
            return inserted, "success"
            
        except Exception as e:
            error_msg = str(e)
            exec_time = time.time() - collection_start
            
            # Log do erro
            self.log_collection(
                symbol, interval, 'single',
                start_time or 0, end_time or int(time.time() * 1000),
                0, 'error', error_msg, exec_time
            )
            
            # Atualiza controle com erro
            last_time = self.get_last_candle_time(symbol, interval) or 0
            self.update_collection_control(symbol, interval, last_time, 'error', error_msg)
            
            logging.error(f"Erro ao coletar {symbol} {interval}: {error_msg}")
            return 0, error_msg
    
    def collect_all_tokens_single(self, interval: str = '1h', limit: int = 100):
        """Coleta única para todos os tokens ativos"""
        logging.info(f"Iniciando coleta única para intervalo {interval}")
        
        tokens = self.get_active_tokens()
        total_collected = 0
        errors = 0
        
        for token in tokens:
            if self.stop_event.is_set():
                break
                
            symbol = token['symbol']
            last_time = self.get_last_collected_time(symbol, interval)
            if last_time:
                start_time = last_time + self.INTERVAL_MS[interval]
            else:
                start_time = int((datetime.utcnow() - timedelta(days=30)).timestamp() * 1000)
            collected, status = self.collect_single_symbol(symbol, interval, start_time=start_time, limit=limit)
            
            total_collected += collected
            if status != "success":
                errors += 1
            
            # Pausa para evitar rate limiting
            time.sleep(0.1)
        
        logging.info(f"Coleta única finalizada: {total_collected} candles, {errors} erros")
        return total_collected, errors
    
    def worker_thread(self):
        """Thread worker para processar tarefas da queue"""
        while not self.stop_event.is_set():
            try:
                task = self.task_queue.get(timeout=1)
                if task is None:  # Sinal para parar
                    break

                symbol, interval = task
                last_time = self.get_last_collected_time(symbol, interval)
                if last_time:
                    start_time = last_time + self.INTERVAL_MS[interval]
                else:
                    start_time = int((datetime.utcnow() - timedelta(days=30)).timestamp() * 1000)

                logging.debug(f"[WORKER] {symbol} {interval} start_time={start_time}")
                self.collect_single_symbol(symbol, interval, start_time=start_time, limit=100)
                self.task_queue.task_done()

            except Empty:
                continue
            except Exception as e:
                logging.error(f"Erro no worker thread: {e}")
                self.task_queue.task_done()
                
            except Empty:
                continue
            except Exception as e:
                logging.error(f"Erro no worker thread: {e}")
    
    def start_continuous_collection(self, intervals: List[str] = ['1h'], 
                                   num_workers: int = 5):
        """Inicia coleta contínua usando threads"""
        logging.info(f"Iniciando coleta contínua para intervalos: {intervals}")
        
        # Inicia worker threads
        for i in range(num_workers):
            worker = threading.Thread(target=self.worker_thread, name=f"Worker-{i}")
            worker.daemon = True
            worker.start()
            self.worker_threads.append(worker)
        
        # Agenda coletas
        for interval in intervals:
            schedule.every(self._get_schedule_interval(interval)).do(
                self._schedule_collection, interval
            )
        
        # Loop principal
        try:
            while not self.stop_event.is_set():
                schedule.run_pending()
                time.sleep(60)  # Verifica a cada minuto
                
        except KeyboardInterrupt:
            logging.info("Interrompido pelo usuário")
        finally:
            self.stop_continuous_collection()
    
    def _get_schedule_interval(self, interval: str) -> int:
        """Retorna intervalo de agendamento baseado no timeframe"""
        if interval in ['1m', '3m', '5m']:
            return 5  # A cada 5 minutos
        elif interval in ['15m', '30m']:
            return 15  # A cada 15 minutos
        elif interval in ['1h', '2h']:
            return 60  # A cada hora
        else:
            return 240  # A cada 4 horas para timeframes maiores
    
    def _schedule_collection(self, interval: str):
        """Agenda coleta para um intervalo"""
        tokens = self.get_active_tokens()
        
        for token in tokens:
            if self.stop_event.is_set():
                break
            
            self.task_queue.put((token['symbol'], interval))
    
    def stop_continuous_collection(self):
        """Para coleta contínua"""
        logging.info("Parando coleta contínua...")
        
        self.stop_event.set()
        
        # Para workers
        for _ in self.worker_threads:
            self.task_queue.put(None)
        
        # Aguarda threads terminarem
        for worker in self.worker_threads:
            worker.join(timeout=5)
        
        self.worker_threads.clear()
        logging.info("Coleta contínua parada")
    
    def fill_missing_data(self, symbol: str, interval: str, days_back: int = 30):
        """Preenche dados faltantes para um símbolo"""
        logging.info(f"Preenchendo dados faltantes para {symbol} {interval}")
        
        end_time = int(time.time() * 1000)
        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
        
        current_time = start_time
        total_collected = 0
        
        while current_time < end_time and not self.stop_event.is_set():
            batch_end = min(current_time + (1000 * self.INTERVAL_MS[interval]), end_time)
            
            collected, _ = self.collect_single_symbol(
                symbol, interval, current_time, batch_end, 1000
            )
            
            total_collected += collected
            current_time = batch_end
            
            # Pausa para evitar rate limiting
            time.sleep(0.5)
        
        logging.info(f"Preenchimento concluído: {total_collected} candles para {symbol}")
        return total_collected

def setup_logging():
    """Configura sistema de logging com cores no terminal"""
    class ColorFormatter(logging.Formatter):
        COLOR_CODES = {
            'DEBUG': '\033[37m',   # Cinza
            'INFO': '\033[32m',    # Verde
            'WARNING': '\033[33m', # Amarelo
            'ERROR': '\033[31m',   # Vermelho
            'CRITICAL': '\033[41m' # Fundo vermelho
        }
        RESET = '\033[0m'

        def format(self, record):
            color = self.COLOR_CODES.get(record.levelname, self.RESET)
            message = super().format(record)
            return f"{color}{message}{self.RESET}"

    log_format = LOGGING_CONFIG.get('format', '%(asctime)s - %(levelname)s - %(message)s')
    level = getattr(logging, LOGGING_CONFIG.get('level', 'INFO'))

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter(log_format))

    file_handler = logging.FileHandler(LOGGING_CONFIG['log_file'])
    file_handler.setFormatter(logging.Formatter(log_format))

    logging.basicConfig(
        level=level,
        handlers=[console_handler, file_handler]
    )

def signal_handler(signum, frame):
    """Handler para sinais do sistema"""
    logging.info(f"Recebido sinal {signum}, parando...")
    if 'collector' in globals():
        collector.stop_continuous_collection()
    sys.exit(0)

def main():
    """Função principal"""
    setup_logging()
    
    # Registra handlers para sinais
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    global collector
    collector = CandleCollector()
    
    logging.info("BinanceImporter - Coletor de Candles iniciado")
    
    try:
        if len(sys.argv) > 1:
            command = sys.argv[1].lower()
            
            if command == 'single':
                # Coleta única
                interval = sys.argv[2] if len(sys.argv) > 2 else '1h'
                limit = int(sys.argv[3]) if len(sys.argv) > 3 else 100
                collector.collect_all_tokens_single(interval, limit)
                
            elif command == 'continuous':
                # Coleta contínua
                intervals = sys.argv[2].split(',') if len(sys.argv) > 2 else ['1h']
                collector.start_continuous_collection(intervals)
                
            elif command == 'fill':
                # Preencher dados faltantes
                if len(sys.argv) < 4:
                    print("Uso: python candle_collector.py fill SYMBOL INTERVAL [DAYS]")
                    return
                
                symbol = sys.argv[2].upper()
                interval = sys.argv[3]
                days = int(sys.argv[4]) if len(sys.argv) > 4 else 30
                collector.fill_missing_data(symbol, interval, days)
                
            else:
                print("Comandos disponíveis:")
                print("  single [interval] [limit] - Coleta única")
                print("  continuous [intervals] - Coleta contínua")
                print("  fill SYMBOL INTERVAL [days] - Preencher dados faltantes")
        else:
            # Modo interativo
            while True:
                try:
                    print("\n=== BinanceImporter - Coletor de Candles ===")
                    print("1. Coleta única (todos os tokens)")
                    print("2. Coleta contínua")
                    print("3. Preencher dados faltantes")
                    print("4. Sair")

                    choice = input("\nEscolha uma opção: ").strip()                    
                    if choice == '1':
                        interval = input("Intervalo (1m,5m,15m,1h,4h,1d) [1h]: ").strip() or '1h'
                        limit = input("Limite de candles [100]: ").strip()
                        limit = int(limit) if limit else 100
                        
                        collector.collect_all_tokens_single(interval, limit)
                        
                    elif choice == '2':
                        intervals_input = input("Intervalos separados por vírgula [1h]: ").strip() or '1h'
                        intervals = [i.strip() for i in intervals_input.split(',')]
                        
                        print(f"Iniciando coleta contínua para: {intervals}")
                        print("Pressione Ctrl+C para parar")
                        collector.start_continuous_collection(intervals)
                        
                    elif choice == '3':
                        symbol = input("Símbolo (ex: BTCUSDT): ").strip().upper()
                        interval = input("Intervalo [1h]: ").strip() or '1h'
                        days = input("Dias para trás [30]: ").strip()
                        days = int(days) if days else 30
                        
                        collector.fill_missing_data(symbol, interval, days)
                        
                    elif choice == '4':
                        break
                        
                    else:
                        print("Opção inválida!")
                        
                except KeyboardInterrupt:
                    print("\nParando...")
                    break
                except Exception as e:
                    logging.error(f"Erro: {e}")
                    print(f"Erro: {e}")
    
    except Exception as e:
        logging.error(f"Erro fatal: {e}")
        print(f"Erro fatal: {e}")
    
    finally:
        collector.db.disconnect()
        logging.info("BinanceImporter finalizado")

if __name__ == "__main__":
    main()