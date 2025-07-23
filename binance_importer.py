#!/usr/bin/env python3
"""
Script para importar dados de criptomoedas da API da Binance para MySQL
Autor: Assistente IA
Data: 2025
"""
import os
import requests
import mysql.connector
from config import DATABASE_CONFIG
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import time

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('binance_importer.log'),
        logging.StreamHandler()
    ]
)

class BinanceImporter:
    def __init__(self, db_config: Dict[str, str]):
        """
        Inicializa o importador da Binance
        
        Args:
            db_config: Configuração do banco de dados MySQL
        """
        self.db_config = DATABASE_CONFIG
        self.base_url = "https://api.binance.com"
        self.connection = None
        print(db_config)
        
    def connect_database(self) -> bool:
        """Conecta ao banco de dados MySQL"""
        try:
            self.connection = mysql.connector.connect(**self.db_config)
            logging.info("Conectado ao banco de dados MySQL")
            return True
        except mysql.connector.Error as e:
            logging.error(f"Erro ao conectar ao banco: {e}")
            return False
    
    def close_connection(self):
        """Fecha conexão com o banco de dados"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logging.info("Conexão com banco de dados fechada")
    
    def fetch_exchange_info(self) -> Optional[Dict[str, Any]]:
        """
        Busca informações do exchange da Binance
        
        Returns:
            Dicionário com dados do exchange ou None em caso de erro
        """
        try:
            url = f"{self.base_url}/api/v3/exchangeInfo"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logging.info(f"Dados do exchange obtidos. Total de símbolos: {len(data.get('symbols', []))}")
            return data
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro ao buscar dados da Binance: {e}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"Erro ao decodificar JSON: {e}")
            return None
    
    def extract_filter_value(self, filters: List[Dict], filter_type: str, field: str) -> Optional[float]:
        """
        Extrai valor específico dos filtros de um símbolo
        
        Args:
            filters: Lista de filtros do símbolo
            filter_type: Tipo do filtro (PRICE_FILTER, LOT_SIZE, etc.)
            field: Campo do filtro (minPrice, maxPrice, etc.)
            
        Returns:
            Valor do campo ou None se não encontrado
        """
        for filter_item in filters:
            if filter_item.get('filterType') == filter_type:
                value = filter_item.get(field)
                if value and value != '0.00000000':
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        pass
        return None
    
    def prepare_symbol_data(self, symbol_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepara dados de um símbolo para inserção no banco
        
        Args:
            symbol_data: Dados brutos do símbolo da API
            
        Returns:
            Dicionário com dados formatados para o banco
        """
        filters = symbol_data.get('filters', [])
        
        # Extrai valores dos filtros
        min_price = self.extract_filter_value(filters, 'PRICE_FILTER', 'minPrice')
        max_price = self.extract_filter_value(filters, 'PRICE_FILTER', 'maxPrice')
        tick_size = self.extract_filter_value(filters, 'PRICE_FILTER', 'tickSize')
        
        multiplier_up = self.extract_filter_value(filters, 'PERCENT_PRICE', 'multiplierUp')
        multiplier_down = self.extract_filter_value(filters, 'PERCENT_PRICE', 'multiplierDown')
        
        min_qty = self.extract_filter_value(filters, 'LOT_SIZE', 'minQty')
        max_qty = self.extract_filter_value(filters, 'LOT_SIZE', 'maxQty')
        step_size = self.extract_filter_value(filters, 'LOT_SIZE', 'stepSize')
        
        min_notional = self.extract_filter_value(filters, 'MIN_NOTIONAL', 'minNotional')
        if not min_notional:
            min_notional = self.extract_filter_value(filters, 'NOTIONAL', 'minNotional')
        
        apply_to_market = False
        for filter_item in filters:
            if filter_item.get('filterType') == 'MIN_NOTIONAL':
                apply_to_market = filter_item.get('applyToMarket', False)
                break
        
        max_num_orders = self.extract_filter_value(filters, 'MAX_NUM_ORDERS', 'maxNumOrders')
        max_num_algo_orders = self.extract_filter_value(filters, 'MAX_NUM_ALGO_ORDERS', 'maxNumAlgoOrders')
        
        return {
            'symbol': symbol_data.get('symbol'),
            'status': symbol_data.get('status'),
            'base_asset': symbol_data.get('baseAsset'),
            'base_asset_precision': symbol_data.get('baseAssetPrecision'),
            'quote_asset': symbol_data.get('quoteAsset'),
            'quote_precision': symbol_data.get('quotePrecision'),
            'quote_asset_precision': symbol_data.get('quoteAssetPrecision'),
            'base_commission_precision': symbol_data.get('baseCommissionPrecision'),
            'quote_commission_precision': symbol_data.get('quoteCommissionPrecision'),
            'order_types': json.dumps(symbol_data.get('orderTypes', [])),
            'iceberg_allowed': symbol_data.get('icebergAllowed', False),
            'oco_allowed': symbol_data.get('ocoAllowed', False),
            'quote_order_qty_market_allowed': symbol_data.get('quoteOrderQtyMarketAllowed', False),
            'allow_trailing_stop': symbol_data.get('allowTrailingStop', False),
            'cancel_replace_allowed': symbol_data.get('cancelReplaceAllowed', False),
            'is_spot_trading_allowed': symbol_data.get('isSpotTradingAllowed', False),
            'is_margin_trading_allowed': symbol_data.get('isMarginTradingAllowed', False),
            'filters': json.dumps(filters),
            'permissions': json.dumps(symbol_data.get('permissions', [])),
            'default_self_trade_prevention_mode': symbol_data.get('defaultSelfTradePreventionMode'),
            'allowed_self_trade_prevention_modes': json.dumps(symbol_data.get('allowedSelfTradePreventionModes', [])),
            'min_price': min_price,
            'max_price': max_price,
            'tick_size': tick_size,
            'multiplier_up': multiplier_up,
            'multiplier_down': multiplier_down,
            'min_qty': min_qty,
            'max_qty': max_qty,
            'step_size': step_size,
            'min_notional': min_notional,
            'apply_to_market': apply_to_market,
            'max_num_orders': int(max_num_orders) if max_num_orders else None,
            'max_num_algo_orders': int(max_num_algo_orders) if max_num_algo_orders else None
        }
    
    def insert_symbol(self, symbol_data: Dict[str, Any]) -> bool:
        """
        Insere ou atualiza um símbolo no banco de dados
        
        Args:
            symbol_data: Dados formatados do símbolo
            
        Returns:
            True se sucesso, False caso contrário
        """
        if not self.connection:
            logging.error("Conexão com banco não estabelecida")
            return False
        
        cursor = self.connection.cursor()
        
        insert_query = """
        INSERT INTO coins (
            symbol, status, base_asset, base_asset_precision, quote_asset, 
            quote_precision, quote_asset_precision, base_commission_precision, 
            quote_commission_precision, order_types, iceberg_allowed, oco_allowed, 
            quote_order_qty_market_allowed, allow_trailing_stop, cancel_replace_allowed, 
            is_spot_trading_allowed, is_margin_trading_allowed, filters, permissions, 
            default_self_trade_prevention_mode, allowed_self_trade_prevention_modes,
            min_price, max_price, tick_size, multiplier_up, multiplier_down, 
            min_qty, max_qty, step_size, min_notional, apply_to_market, 
            max_num_orders, max_num_algo_orders
        ) VALUES (
            %(symbol)s, %(status)s, %(base_asset)s, %(base_asset_precision)s, %(quote_asset)s,
            %(quote_precision)s, %(quote_asset_precision)s, %(base_commission_precision)s,
            %(quote_commission_precision)s, %(order_types)s, %(iceberg_allowed)s, %(oco_allowed)s,
            %(quote_order_qty_market_allowed)s, %(allow_trailing_stop)s, %(cancel_replace_allowed)s,
            %(is_spot_trading_allowed)s, %(is_margin_trading_allowed)s, %(filters)s, %(permissions)s,
            %(default_self_trade_prevention_mode)s, %(allowed_self_trade_prevention_modes)s,
            %(min_price)s, %(max_price)s, %(tick_size)s, %(multiplier_up)s, %(multiplier_down)s,
            %(min_qty)s, %(max_qty)s, %(step_size)s, %(min_notional)s, %(apply_to_market)s,
            %(max_num_orders)s, %(max_num_algo_orders)s
        ) ON DUPLICATE KEY UPDATE
            status = VALUES(status),
            base_asset_precision = VALUES(base_asset_precision),
            quote_precision = VALUES(quote_precision),
            quote_asset_precision = VALUES(quote_asset_precision),
            base_commission_precision = VALUES(base_commission_precision),
            quote_commission_precision = VALUES(quote_commission_precision),
            order_types = VALUES(order_types),
            iceberg_allowed = VALUES(iceberg_allowed),
            oco_allowed = VALUES(oco_allowed),
            quote_order_qty_market_allowed = VALUES(quote_order_qty_market_allowed),
            allow_trailing_stop = VALUES(allow_trailing_stop),
            cancel_replace_allowed = VALUES(cancel_replace_allowed),
            is_spot_trading_allowed = VALUES(is_spot_trading_allowed),
            is_margin_trading_allowed = VALUES(is_margin_trading_allowed),
            filters = VALUES(filters),
            permissions = VALUES(permissions),
            default_self_trade_prevention_mode = VALUES(default_self_trade_prevention_mode),
            allowed_self_trade_prevention_modes = VALUES(allowed_self_trade_prevention_modes),
            min_price = VALUES(min_price),
            max_price = VALUES(max_price),
            tick_size = VALUES(tick_size),
            multiplier_up = VALUES(multiplier_up),
            multiplier_down = VALUES(multiplier_down),
            min_qty = VALUES(min_qty),
            max_qty = VALUES(max_qty),
            step_size = VALUES(step_size),
            min_notional = VALUES(min_notional),
            apply_to_market = VALUES(apply_to_market),
            max_num_orders = VALUES(max_num_orders),
            max_num_algo_orders = VALUES(max_num_algo_orders),
            updated_at = CURRENT_TIMESTAMP
        """
        
        try:
            cursor.execute(insert_query, symbol_data)
            self.connection.commit()
            return True
        except mysql.connector.Error as e:
            logging.error(f"Erro ao inserir símbolo {symbol_data.get('symbol')}: {e}")
            self.connection.rollback()
            return False
        finally:
            cursor.close()
    
    def import_all_symbols(self) -> bool:
        """
        Importa todos os símbolos da Binance para o banco de dados
        
        Returns:
            True se sucesso, False caso contrário
        """
        # Busca dados da API
        exchange_data = self.fetch_exchange_info()
        if not exchange_data:
            return False
        
        symbols = exchange_data.get('symbols', [])
        if not symbols:
            logging.warning("Nenhum símbolo encontrado na resposta da API")
            return False
        
        # Conecta ao banco
        if not self.connect_database():
            return False
        
        # Processa cada símbolo
        success_count = 0
        error_count = 0
        
        for symbol_data in symbols:
            try:
                formatted_data = self.prepare_symbol_data(symbol_data)
                if self.insert_symbol(formatted_data):
                    success_count += 1
                    if success_count % 100 == 0:
                        logging.info(f"Processados {success_count} símbolos...")
                else:
                    error_count += 1
                    
                # Pequena pausa para não sobrecarregar o banco
                time.sleep(0.01)
                
            except Exception as e:
                logging.error(f"Erro ao processar símbolo {symbol_data.get('symbol', 'UNKNOWN')}: {e}")
                error_count += 1
        
        # Executa sincronização para tokens USDT
        self.sync_usdt_tokens()
        
        logging.info(f"Importação concluída. Sucessos: {success_count}, Erros: {error_count}")
        return error_count == 0
    
    def sync_usdt_tokens(self):
        """Executa a procedure de sincronização de tokens USDT"""
        try:
            cursor = self.connection.cursor()
            cursor.callproc('SyncExistingUSDTTokens')
            
            # Lê o resultado da procedure
            for result in cursor.stored_results():
                row = result.fetchone()
                if row:
                    logging.info(f"Sincronização de tokens: {row[0]}")
            
            self.connection.commit()
            cursor.close()
            
        except mysql.connector.Error as e:
            logging.error(f"Erro na sincronização de tokens USDT: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """
        Retorna estatísticas da importação
        
        Returns:
            Dicionário com estatísticas
        """
        if not self.connection:
            return {}
        
        cursor = self.connection.cursor(dictionary=True)
        
        stats = {}
        
        # Total de moedas
        cursor.execute("SELECT COUNT(*) as total FROM coins")
        result = cursor.fetchone()
        stats['total_coins'] = result['total'] if result else 0
        
        # Moedas USDT ativas
        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM coins 
            WHERE quote_asset = 'USDT' 
              AND status = 'TRADING' 
              AND is_spot_trading_allowed = TRUE
        """)
        result = cursor.fetchone()
        stats['usdt_active'] = result['total'] if result else 0
        
        # Total de tokens sincronizados
        cursor.execute("SELECT COUNT(*) as total FROM tokens")
        result = cursor.fetchone()
        stats['tokens_synced'] = result['total'] if result else 0
        
        cursor.close()
        return stats


def main():
    """Função principal"""
    # Configuração do banco de dados
    DB_CONFIG = {
        'host': 'localhost',
        'port': 3306,
        'database': 'binance_crypto',
        'user': 'seu_usuario',
        'password': 'sua_senha',
        'charset': 'utf8mb4',
        'autocommit': False,
        'use_unicode': True
    }
    
    # Inicializa o importador
    importer = BinanceImporter(DB_CONFIG)
    
    try:
        logging.info("Iniciando importação de dados da Binance...")
        
        # Executa a importação
        success = importer.import_all_symbols()
        
        if success:
            # Mostra estatísticas
            stats = importer.get_stats()
            logging.info("=== ESTATÍSTICAS DA IMPORTAÇÃO ===")
            logging.info(f"Total de moedas importadas: {stats.get('total_coins', 0)}")
            logging.info(f"Moedas USDT ativas: {stats.get('usdt_active', 0)}")
            logging.info(f"Tokens sincronizados: {stats.get('tokens_synced', 0)}")
            logging.info("Importação concluída com sucesso!")
        else:
            logging.error("Importação falhou. Verifique os logs para detalhes.")
            
    except Exception as e:
        logging.error(f"Erro geral na execução: {e}")
    finally:
        importer.close_connection()


if __name__ == "__main__":
    main()