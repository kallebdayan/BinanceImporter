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
