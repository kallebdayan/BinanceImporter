# ===========================================
# run.sh (Script de Execução Linux/Mac)
# ===========================================

#!/bin/bash

# Ativar ambiente virtual
source venv/bin/activate

# Função para parar processos em caso de erro
cleanup() {
    echo "Parando processos..."
    pkill -f "candle_collector.py"
    pkill -f "technical_indicators.py"
    exit 0
}

# Capturar sinais para cleanup
trap cleanup SIGINT SIGTERM

echo "=== BinanceImporter - Iniciando Sistema ==="

# Verificar se o banco de dados está acessível
python -c "
from config import DATABASE_CONFIG
import mysql.connector
try:
    conn = mysql.connector.connect(**DATABASE_CONFIG)
    print('✓ Conexão com banco de dados OK')
    conn.close()
except Exception as e:
    print(f'✗ Erro de conexão: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "Erro na verificação do banco de dados"
    exit 1
fi

# Executar coleta inicial
echo "Executando coleta inicial..."
python candle_collector.py single 1h 200

# Iniciar coleta contínua em background
echo "Iniciando coleta contínua..."
nohup python candle_collector.py continuous 1h,4h,1d > collector.log 2>&1 &
COLLECTOR_PID=$!

# Aguardar um pouco e iniciar cálculo de indicadores
sleep 30
echo "Iniciando cálculo de indicadores..."

# Loop principal para cálculo de indicadores
while true; do
    python technical_indicators.py calculate 1h
    
    # Mostrar status
    echo "$(date): Indicadores calculados"
    
    # Aguardar 15 minutos
    sleep 900
done &

INDICATORS_PID=$!

# Aguardar sinais
wait

# ===========================================
# run.bat (Script de Execução Windows)
# ===========================================

@echo off
echo === BinanceImporter - Iniciando Sistema ===

rem Ativar ambiente virtual
call venv\Scripts\activate.bat

rem Verificar conexão com banco
python -c "
from config import DATABASE_CONFIG
import mysql.connector
try:
    conn = mysql.connector.connect(**DATABASE_CONFIG)
    print('✓ Conexão com banco de dados OK')
    conn.close()
except Exception as e:
    print(f'✗ Erro de conexão: {e}')
    pause
    exit(1)
"

if errorlevel 1 (
    echo Erro na verificação do banco de dados
    pause
    exit /b 1
)

rem Executar coleta inicial
echo Executando coleta inicial...
python candle_collector.py single 1h 200

rem Iniciar coleta contínua
echo Iniciando coleta contínua...
start /B python candle_collector.py continuous 1h,4h,1d

rem Aguardar e iniciar indicadores
timeout /t 30 /nobreak

echo Iniciando cálculo de indicadores...
:loop
python technical_indicators.py calculate 1h
echo %date% %time%: Indicadores calculados
timeout /t 900 /nobreak
goto loop

# ===========================================
# install.sh (Script de Instalação)
# ===========================================

#!/bin/bash

echo "=== BinanceImporter - Instalação ==="

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 não encontrado. Por favor, instale Python 3.8+"
    exit 1
fi

# Criar ambiente virtual
echo "Criando ambiente virtual..."
python3 -m venv venv

# Ativar ambiente virtual
source venv/bin/activate

# Atualizar pip
pip install --upgrade pip

# Instalar dependências
echo "Instalando dependências Python..."
pip install -r requirements.txt

# Verificar MySQL
echo "Verificando MySQL..."
if ! command -v mysql &> /dev/null; then
    echo "AVISO: MySQL não encontrado no PATH"
    echo "Certifique-se de que o MySQL está instalado e rodando"
fi

# Criar arquivo .env se não existir
if [ ! -f .env ]; then
    echo "Criando arquivo .env de exemplo..."
    cat > .env << EOL
# Configurações do Banco de Dados
DB_HOST=localhost
DB_PORT=3306
DB_NAME=binanceimporter
DB_USER=root
DB_PASSWORD=sua_senha_aqui
EOL
    echo "IMPORTANTE: Edite o arquivo .env com suas configurações!"
fi

echo ""
echo "=== Instalação Concluída ==="
echo ""
echo "Próximos passos:"
echo "1. Edite o arquivo .env com suas configurações de banco"
echo "2. Execute a estrutura do banco: mysql -u root -p binanceimporter < database_structure.sql"
echo "3. Execute: ./run.sh (Linux/Mac) ou run.bat (Windows)"
echo ""

# ===========================================
# test_connection.py (Teste de Conectividade)
# ===========================================

#!/usr/bin/env python3
"""
Script para testar conectividade com API da Binance e banco de dados
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_database():
    """Testa conexão com banco de dados"""
    try:
        from config import DATABASE_CONFIG
        import mysql.connector
        
        print("Testando conexão com banco de dados...")
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        cursor = conn.cursor()
        
        # Testar query simples
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        
        print(f"✓ Conexão OK - MySQL {version[0]}")
        
        # Verificar se tabelas existem
        cursor.execute("SHOW TABLES LIKE 'tokens'")
        if cursor.fetchone():
            print("✓ Tabela 'tokens' encontrada")
        else:
            print("✗ Tabela 'tokens' não encontrada")
            
        cursor.execute("SHOW TABLES LIKE 'candles'")
        if cursor.fetchone():
            print("✓ Tabela 'candles' encontrada")
        else:
            print("✗ Tabela 'candles' não encontrada")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Erro de conexão com banco: {e}")
        return False

def test_binance_api():
    """Testa conectividade com API da Binance"""
    try:
        import requests
        from config import BINANCE_CONFIG
        
        print("Testando API da Binance...")
        
        url = f"{BINANCE_CONFIG['base_url']}/api/v3/ping"
        response = requests.get(url, timeout=BINANCE_CONFIG['timeout'])
        
        if response.status_code == 200:
            print("✓ API da Binance acessível")
            
            # Testar endpoint de dados
            url = f"{BINANCE_CONFIG['base_url']}/api/v3/klines"
            params = {'symbol': 'BTCUSDT', 'interval': '1h', 'limit': 1}
            response = requests.get(url, params=params, timeout=BINANCE_CONFIG['timeout'])
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    print("✓ Endpoint de klines funcionando")
                    print(f"  Último candle BTC: {data[0][4]} USDT")
                    return True
            
        print(f"✗ Erro na API: Status {response.status_code}")
        return False
        
    except Exception as e:
        print(f"✗ Erro ao acessar API da Binance: {e}")
        return False

def test_tokens_table():
    """Verifica se há tokens na tabela"""
    try:
        from candle_collector import DatabaseManager
        
        print("Verificando tokens ativos...")
        db = DatabaseManager()
        
        query = "SELECT COUNT(*) as total FROM tokens WHERE status = 'TRADING'"
        result = db.execute_query(query, fetch=True)
        
        total = result[0]['total'] if result else 0
        print(f"✓ {total} tokens ativos encontrados")
        
        if total > 0:
            query = "SELECT symbol FROM tokens WHERE status = 'TRADING' LIMIT 5"
            tokens = db.execute_query(query, fetch=True)
            print("  Exemplos:", ", ".join([t['symbol'] for t in tokens]))
        
        db.disconnect()
        return total > 0
        
    except Exception as e:
        print(f"✗ Erro ao verificar tokens: {e}")
        return False

def main():
    """Função principal de teste"""
    print("=== Teste de Conectividade BinanceImporter ===\n")
    
    # Testar carregamento de configurações
    try:
        from config import DATABASE_CONFIG, BINANCE_CONFIG
        print("✓ Configurações carregadas")
    except Exception as e:
        print(f"✗ Erro ao carregar configurações: {e}")
        return False
    
    print()
    
    # Executar testes
    db_ok = test_database()
    print()
    api_ok = test_binance_api()
    print()
    tokens_ok = test_tokens_table()
    
    print("\n=== Resultado dos Testes ===")
    print(f"Banco de dados: {'✓' if db_ok else '✗'}")
    print(f"API Binance: {'✓' if api_ok else '✗'}")
    print(f"Dados de tokens: {'✓' if tokens_ok else '✗'}")
    
    if db_ok and api_ok:
        print("\n🎉 Sistema pronto para uso!")
        if not tokens_ok:
            print("💡 Execute primeiro o importador de tokens para popular a base")
    else:
        print("\n❌ Corrija os problemas antes de prosseguir")
        
    return db_ok and api_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)