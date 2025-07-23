#!/usr/bin/env python3
"""
BinanceImporter - Gerador de Indicadores Técnicos
Calcula indicadores técnicos baseados nos dados de candles coletados
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import mysql.connector
from mysql.connector import Error as MySQLError
from datetime import datetime, timedelta

# Importar configurações
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import DATABASE_CONFIG, LOGGING_CONFIG

class TechnicalIndicators:
    """Classe para calcular indicadores técnicos"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    @staticmethod
    def sma(prices: List[float], period: int) -> List[float]:
        """Média Móvel Simples"""
        if len(prices) < period:
            return [None] * len(prices)
        
        sma_values = []
        for i in range(len(prices)):
            if i < period - 1:
                sma_values.append(None)
            else:
                sma_values.append(sum(prices[i-period+1:i+1]) / period)
        
        return sma_values
    
    @staticmethod
    def ema(prices: List[float], period: int) -> List[float]:
        """Média Móvel Exponencial"""
        if len(prices) < period:
            return [None] * len(prices)
        
        alpha = 2 / (period + 1)
        ema_values = [None] * (period - 1)
        
        # Primeira EMA é a SMA
        ema_values.append(sum(prices[:period]) / period)
        
        # Calcular EMAs subsequentes
        for i in range(period, len(prices)):
            ema_values.append(alpha * prices[i] + (1 - alpha) * ema_values[-1])
        
        return ema_values
    
    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> List[float]:
        """Índice de Força Relativa"""
        if len(prices) < period + 1:
            return [None] * len(prices)
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [max(delta, 0) for delta in deltas]
        losses = [abs(min(delta, 0)) for delta in deltas]
        
        rsi_values = [None] * (period)
        
        # Primeira média
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        if avg_loss == 0:
            rsi_values.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))
        
        # RSI subsequentes
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi_values.append(100)
            else:
                rs = avg_gain / avg_loss
                rsi_values.append(100 - (100 / (1 + rs)))
        
        return rsi_values
    
    @staticmethod
    def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[float], List[float], List[float]]:
        """MACD (Moving Average Convergence Divergence)"""
        ema_fast = TechnicalIndicators.ema(prices, fast)
        ema_slow = TechnicalIndicators.ema(prices, slow)
        
        # Linha MACD
        macd_line = []
        for i in range(len(prices)):
            if ema_fast[i] is None or ema_slow[i] is None:
                macd_line.append(None)
            else:
                macd_line.append(ema_fast[i] - ema_slow[i])
        
        # Linha de sinal
        signal_line = TechnicalIndicators.ema([x for x in macd_line if x is not None], signal)
        
        # Ajustar tamanho da linha de sinal
        none_count = len([x for x in macd_line if x is None])
        signal_line = [None] * none_count + signal_line
        
        # Histograma
        histogram = []
        for i in range(len(macd_line)):
            if macd_line[i] is None or signal_line[i] is None:
                histogram.append(None)
            else:
                histogram.append(macd_line[i] - signal_line[i])
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2) -> Tuple[List[float], List[float], List[float]]:
        """Bandas de Bollinger"""
        sma_values = TechnicalIndicators.sma(prices, period)
        
        upper_band = []
        lower_band = []
        
        for i in range(len(prices)):
            if sma_values[i] is None:
                upper_band.append(None)
                lower_band.append(None)
            else:
                # Calcular desvio padrão
                data_slice = prices[i-period+1:i+1]
                std = np.std(data_slice)
                
                upper_band.append(sma_values[i] + (std_dev * std))
                lower_band.append(sma_values[i] - (std_dev * std))
        
        return upper_band, sma_values, lower_band
    
    @staticmethod
    def stochastic(highs: List[float], lows: List[float], closes: List[float], k_period: int = 14, d_period: int = 3) -> Tuple[List[float], List[float]]:
        """Oscilador Estocástico"""
        if len(highs) != len(lows) or len(lows) != len(closes):
            raise ValueError("Arrays devem ter o mesmo tamanho")
        
        k_values = []
        
        for i in range(len(closes)):
            if i < k_period - 1:
                k_values.append(None)
            else:
                highest_high = max(highs[i-k_period+1:i+1])
                lowest_low = min(lows[i-k_period+1:i+1])
                
                if highest_high == lowest_low:
                    k_values.append(50)  # Evitar divisão por zero
                else:
                    k_values.append(((closes[i] - lowest_low) / (highest_high - lowest_low)) * 100)
        
        # %D é a média móvel simples de %K
        d_values = TechnicalIndicators.sma([x for x in k_values if x is not None], d_period)
        
        # Ajustar tamanho
        none_count = len([x for x in k_values if x is None])
        d_values = [None] * none_count + d_values
        
        return k_values, d_values
    
    def calculate_all_indicators(self, symbol: str, interval: str, limit: int = 1000) -> Dict:
        """Calcula todos os indicadores para um símbolo"""
        # Buscar dados de candles
        query = """
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM candles 
        WHERE symbol = %s AND interval_type = %s 
        ORDER BY open_time DESC 
        LIMIT %s
        """
        
        candles = self.db.execute_query(query, (symbol, interval, limit), fetch=True)
        
        if not candles:
            return {}
        
        # Reverter ordem para cronológica
        candles = list(reversed(candles))
        
        # Extrair dados
        opens = [float(c['open_price']) for c in candles]
        highs = [float(c['high_price']) for c in candles]
        lows = [float(c['low_price']) for c in candles]
        closes = [float(c['close_price']) for c in candles]
        volumes = [float(c['volume']) for c in candles]
        timestamps = [c['open_time'] for c in candles]
        
        # Calcular indicadores
        indicators = {
            'symbol': symbol,
            'interval': interval,
            'timestamp': timestamps[-1],
            'current_price': closes[-1],
            'sma_20': TechnicalIndicators.sma(closes, 20)[-1],
            'sma_50': TechnicalIndicators.sma(closes, 50)[-1],
            'ema_12': TechnicalIndicators.ema(closes, 12)[-1],
            'ema_26': TechnicalIndicators.ema(closes, 26)[-1],
            'rsi_14': TechnicalIndicators.rsi(closes, 14)[-1],
        }
        
        # MACD
        macd_line, signal_line, histogram = TechnicalIndicators.macd(closes)
        indicators['macd_line'] = macd_line[-1]
        indicators['macd_signal'] = signal_line[-1]
        indicators['macd_histogram'] = histogram[-1]
        
        # Bandas de Bollinger
        bb_upper, bb_middle, bb_lower = TechnicalIndicators.bollinger_bands(closes)
        indicators['bb_upper'] = bb_upper[-1]
        indicators['bb_middle'] = bb_middle[-1]
        indicators['bb_lower'] = bb_lower[-1]
        
        # Estocástico
        stoch_k, stoch_d = TechnicalIndicators.stochastic(highs, lows, closes)
        indicators['stoch_k'] = stoch_k[-1]
        indicators['stoch_d'] = stoch_d[-1]
        
        # Indicadores de volume
        if len(volumes) >= 20:
            indicators['volume_sma_20'] = sum(volumes[-20:]) / 20
            indicators['volume_ratio'] = volumes[-1] / indicators['volume_sma_20']
        
        # Suporte e resistência (máximos e mínimos locais)
        if len(highs) >= 20:
            indicators['resistance_20'] = max(highs[-20:])
            indicators['support_20'] = min(lows[-20:])
        
        return indicators

class IndicatorManager:
    """Gerenciador de indicadores técnicos"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.calculator = TechnicalIndicators(self.db)
    
    def create_indicators_table(self):
        """Cria tabela para armazenar indicadores"""
        query = """
        CREATE TABLE IF NOT EXISTS `technical_indicators` (
          `id` bigint(20) NOT NULL AUTO_INCREMENT,
          `symbol` varchar(50) NOT NULL,
          `interval_type` varchar(10) NOT NULL,
          `timestamp` bigint(20) NOT NULL,
          `current_price` decimal(20,8) NOT NULL,
          `sma_20` decimal(20,8) DEFAULT NULL,
          `sma_50` decimal(20,8) DEFAULT NULL,
          `ema_12` decimal(20,8) DEFAULT NULL,
          `ema_26` decimal(20,8) DEFAULT NULL,
          `rsi_14` decimal(10,4) DEFAULT NULL,
          `macd_line` decimal(20,8) DEFAULT NULL,
          `macd_signal` decimal(20,8) DEFAULT NULL,
          `macd_histogram` decimal(20,8) DEFAULT NULL,
          `bb_upper` decimal(20,8) DEFAULT NULL,
          `bb_middle` decimal(20,8) DEFAULT NULL,
          `bb_lower` decimal(20,8) DEFAULT NULL,
          `stoch_k` decimal(10,4) DEFAULT NULL,
          `stoch_d` decimal(10,4) DEFAULT NULL,
          `volume_sma_20` decimal(20,8) DEFAULT NULL,
          `volume_ratio` decimal(10,4) DEFAULT NULL,
          `resistance_20` decimal(20,8) DEFAULT NULL,
          `support_20` decimal(20,8) DEFAULT NULL,
          `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
          PRIMARY KEY (`id`),
          UNIQUE KEY `unique_indicator` (`symbol`, `interval_type`, `timestamp`),
          KEY `idx_symbol` (`symbol`),
          KEY `idx_timestamp` (`timestamp`),
          CONSTRAINT `technical_indicators_ibfk_1` FOREIGN KEY (`symbol`) REFERENCES `tokens` (`symbol`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
        """
        
        self.db.execute_query(query)
        logging.info("Tabela de indicadores técnicos criada/verificada")
    
    def save_indicators(self, indicators: Dict):
        """Salva indicadores no banco de dados"""
        if not indicators:
            return
        
        query = """
        INSERT INTO technical_indicators (
            symbol, interval_type, timestamp, current_price, sma_20, sma_50,
            ema_12, ema_26, rsi_14, macd_line, macd_signal, macd_histogram,
            bb_upper, bb_middle, bb_lower, stoch_k, stoch_d, volume_sma_20,
            volume_ratio, resistance_20, support_20
        ) VALUES (
            %(symbol)s, %(interval)s, %(timestamp)s, %(current_price)s,
            %(sma_20)s, %(sma_50)s, %(ema_12)s, %(ema_26)s, %(rsi_14)s,
            %(macd_line)s, %(macd_signal)s, %(macd_histogram)s,
            %(bb_upper)s, %(bb_middle)s, %(bb_lower)s, %(stoch_k)s, %(stoch_d)s,
            %(volume_sma_20)s, %(volume_ratio)s, %(resistance_20)s, %(support_20)s
        ) ON DUPLICATE KEY UPDATE
            current_price = VALUES(current_price),
            sma_20 = VALUES(sma_20),
            sma_50 = VALUES(sma_50),
            ema_12 = VALUES(ema_12),
            ema_26 = VALUES(ema_26),
            rsi_14 = VALUES(rsi_14),
            macd_line = VALUES(macd_line),
            macd_signal = VALUES(macd_signal),
            macd_histogram = VALUES(macd_histogram),
            bb_upper = VALUES(bb_upper),
            bb_middle = VALUES(bb_middle),
            bb_lower = VALUES(bb_lower),
            stoch_k = VALUES(stoch_k),
            stoch_d = VALUES(stoch_d),
            volume_sma_20 = VALUES(volume_sma_20),
            volume_ratio = VALUES(volume_ratio),
            resistance_20 = VALUES(resistance_20),
            support_20 = VALUES(support_20)
        """
        
        self.db.execute_query(query, indicators)
    
    def calculate_for_all_tokens(self, interval: str = '1h'):
        """Calcula indicadores para todos os tokens ativos"""
        # Buscar tokens ativos
        query = "SELECT symbol FROM active_trading_tokens ORDER BY symbol"
        tokens = self.db.execute_query(query, fetch=True)
        
        total_processed = 0
        errors = 0
        
        logging.info(f"Calculando indicadores para {len(tokens)} tokens")
        
        for token in tokens:
            try:
                symbol = token['symbol']
                indicators = self.calculator.calculate_all_indicators(symbol, interval)
                
                if indicators:
                    self.save_indicators(indicators)
                    total_processed += 1
                    logging.info(f"Indicadores calculados para {symbol}")
                else:
                    logging.warning(f"Dados insuficientes para {symbol}")
                
            except Exception as e:
                errors += 1
                logging.error(f"Erro ao calcular indicadores para {symbol}: {e}")
        
        logging.info(f"Processamento concluído: {total_processed} tokens, {errors} erros")
        return total_processed, errors
    
    def get_signals(self, symbol: str = None, interval: str = '1h') -> List[Dict]:
        """Identifica sinais de trading baseados nos indicadores"""
        where_clause = "WHERE ti.interval_type = %s"
        params = [interval]
        
        if symbol:
            where_clause += " AND ti.symbol = %s"
            params.append(symbol)
        
        query = f"""
        SELECT 
            ti.symbol,
            ti.current_price,
            ti.rsi_14,
            ti.macd_line,
            ti.macd_signal,
            ti.macd_histogram,
            ti.bb_upper,
            ti.bb_middle,
            ti.bb_lower,
            ti.stoch_k,
            ti.stoch_d,
            ti.volume_ratio,
            ti.created_at
        FROM technical_indicators ti
        {where_clause}
        ORDER BY ti.created_at DESC
        LIMIT 100
        """
        
        indicators = self.db.execute_query(query, params, fetch=True)
        signals = []
        
        for ind in indicators:
            signal = {
                'symbol': ind['symbol'],
                'price': float(ind['current_price']),
                'timestamp': ind['created_at'],
                'signals': []
            }
            
            # Sinais RSI
            if ind['rsi_14']:
                rsi = float(ind['rsi_14'])
                if rsi < 30:
                    signal['signals'].append({'type': 'BUY', 'indicator': 'RSI', 'value': rsi, 'reason': 'Oversold'})
                elif rsi > 70:
                    signal['signals'].append({'type': 'SELL', 'indicator': 'RSI', 'value': rsi, 'reason': 'Overbought'})
            
            # Sinais MACD
            if ind['macd_line'] and ind['macd_signal']:
                macd_line = float(ind['macd_line'])
                macd_signal = float(ind['macd_signal'])
                
                if macd_line > macd_signal and macd_line > 0:
                    signal['signals'].append({'type': 'BUY', 'indicator': 'MACD', 'reason': 'Bullish crossover'})
                elif macd_line < macd_signal and macd_line < 0:
                    signal['signals'].append({'type': 'SELL', 'indicator': 'MACD', 'reason': 'Bearish crossover'})
            
            # Sinais Bandas de Bollinger
            if ind['bb_upper'] and ind['bb_lower']:
                price = float(ind['current_price'])
                bb_upper = float(ind['bb_upper'])
                bb_lower = float(ind['bb_lower'])
                
                if price <= bb_lower:
                    signal['signals'].append({'type': 'BUY', 'indicator': 'BB', 'reason': 'Price at lower band'})
                elif price >= bb_upper:
                    signal['signals'].append({'type': 'SELL', 'indicator': 'BB', 'reason': 'Price at upper band'})
            
            # Sinais Estocástico
            if ind['stoch_k'] and ind['stoch_d']:
                stoch_k = float(ind['stoch_k'])
                stoch_d = float(ind['stoch_d'])
                
                if stoch_k < 20 and stoch_d < 20:
                    signal['signals'].append({'type': 'BUY', 'indicator': 'STOCH', 'reason': 'Oversold'})
                elif stoch_k > 80 and stoch_d > 80:
                    signal['signals'].append({'type': 'SELL', 'indicator': 'STOCH', 'reason': 'Overbought'})
            
            if signal['signals']:
                signals.append(signal)
        
        return signals

# Importar DatabaseManager do arquivo principal
class DatabaseManager:
    """Gerenciador de conexões com o banco de dados"""
    
    def __init__(self):
        self.connection = None
        self.connect()
    
    def connect(self):
        """Estabelece conexão com o banco de dados"""
        try:
            self.connection = mysql.connector.connect(**DATABASE_CONFIG)
        except MySQLError as e:
            logging.error(f"Erro ao conectar com banco de dados: {e}")
            raise
    
    def disconnect(self):
        """Fecha conexão com banco de dados"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
    
    def execute_query(self, query: str, params=None, fetch: bool = False):
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

def main():
    """Função principal"""
    logging.basicConfig(
        level=getattr(logging, LOGGING_CONFIG['level']),
        format=LOGGING_CONFIG['format']
    )
    
    manager = IndicatorManager()
    
    # Criar tabela se não existir
    manager.create_indicators_table()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'calculate':
            interval = sys.argv[2] if len(sys.argv) > 2 else '1h'
            manager.calculate_for_all_tokens(interval)
            
        elif command == 'signals':
            symbol = sys.argv[2].upper() if len(sys.argv) > 2 else None
            interval = sys.argv[3] if len(sys.argv) > 3 else '1h'
            
            signals = manager.get_signals(symbol, interval)
            
            print(f"\n=== Sinais de Trading ===")
            for signal in signals[:10]:  # Mostrar apenas os 10 primeiros
                print(f"\nSímbolo: {signal['symbol']}")
                print(f"Preço: ${signal['price']:.8f}")
                print(f"Sinais:")
                for s in signal['signals']:
                    print(f"  - {s['type']} ({s['indicator']}): {s['reason']}")
        
        else:
            print("Comandos disponíveis:")
            print("  calculate [interval] - Calcular indicadores")
            print("  signals [symbol] [interval] - Mostrar sinais")
    
    else:
        print("Uso: python technical_indicators.py <command> [args]")
    
    manager.db.disconnect()

if __name__ == "__main__":
    main()