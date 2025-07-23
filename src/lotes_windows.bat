REM ===========================================
REM run.bat - Script Principal para Windows
REM ===========================================

@echo off
echo === BinanceImporter - Iniciando Sistema ===

REM Ativar ambiente virtual
call venv\Scripts\activate.bat

REM Verificar conexão com banco
python -c "
from config import DATABASE_CONFIG
import mysql.connector
try:
    conn = mysql.connector.connect(**DATABASE_CONFIG)
    print('✓ Conexão com banco de dados OK')
    conn.close()
except Exception as e:
    print(f'✗ Erro de conexão: {e}')
    input('Pressione Enter para sair...')
    exit(1)
"

if errorlevel 1 (
    echo Erro na verificação do banco de dados
    pause
    exit /b 1
)

REM Executar coleta inicial
echo Executando coleta inicial...
python candle_collector.py single 1h 200

REM Iniciar coleta contínua em background
echo Iniciando coleta contínua...
start "Coletor Candles" /MIN python candle_collector.py continuous 1h,4h,1d

REM Aguardar 30 segundos
timeout /t 30 /nobreak >nul

REM Iniciar cálculo de indicadores em loop
echo Iniciando cálculo de indicadores...
:loop
python technical_indicators.py calculate 1h
echo %date% %time%: Indicadores calculados
timeout /t 900 /nobreak >nul
goto loop

REM ===========================================
REM install.bat - Instalação para Windows
REM ===========================================

@echo off
echo === BinanceImporter - Instalação ===

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python não encontrado. Instale Python 3.8+ primeiro
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Criar ambiente virtual
echo Criando ambiente virtual...
python -m venv venv

REM Ativar ambiente virtual
call venv\Scripts\activate.bat

REM Atualizar pip
python -m pip install --upgrade pip

REM Instalar dependências
echo Instalando dependências Python...
pip install requests>=2.28.0 mysql-connector-python>=8.0.32 python-dotenv>=1.0.0 schedule>=1.2.0 numpy>=1.21.0 pandas>=1.3.0

REM Criar arquivo .env se não existir
if not exist .env (
    echo Criando arquivo .env de exemplo...
    (
        echo # Configurações do Banco de Dados
        echo DB_HOST=localhost
        echo DB_PORT=3306
        echo DB_NAME=binanceimporter
        echo DB_USER=root
        echo DB_PASSWORD=sua_senha_aqui
    ) > .env
    echo IMPORTANTE: Edite o arquivo .env com suas configurações!
)

echo.
echo === Instalação Concluída ===
echo.
echo Próximos passos:
echo 1. Edite o arquivo .env com suas configurações de banco
echo 2. Execute a estrutura do banco no MySQL
echo 3. Execute: run.bat
echo.
pause

REM ===========================================
REM test.bat - Teste de Conectividade
REM ===========================================

@echo off
echo === Teste de Conectividade ===

call venv\Scripts\activate.bat

python test_connection.py

pause

REM ===========================================
REM quick_start.bat - Início Rápido
REM ===========================================

@echo off
echo === BinanceImporter - Início Rápido ===

REM Ativar ambiente virtual
call venv\Scripts\activate.bat

echo.
echo Escolha uma opção:
echo 1. Coleta única (1 hora, 100 candles)
echo 2. Coleta única personalizada
echo 3. Coleta contínua
echo 4. Calcular indicadores
echo 5. Ver sinais de trading
echo 6. Preencher dados faltantes
echo 7. Sair
echo.

set /p choice="Digite sua escolha (1-7): "

if "%choice%"=="1" (
    python candle_collector.py single 1h 100
    goto end
)

if "%choice%"=="2" (
    set /p interval="Intervalo (1m,5m,15m,1h,4h,1d): "
    set /p limit="Limite de candles: "
    python candle_collector.py single %interval% %limit%
    goto end
)

if "%choice%"=="3" (
    set /p intervals="Intervalos separados por vírgula [1h,4h]: "
    if "%intervals%"=="" set intervals=1h,4h
    echo Iniciando coleta contínua... Pressione Ctrl+C para parar
    python candle_collector.py continuous %intervals%
    goto end
)

if "%choice%"=="4" (
    set /p interval="Intervalo [1h]: "
    if "%interval%"=="" set interval=1h
    python technical_indicators.py calculate %interval%
    goto end
)

if "%choice%"=="5" (
    set /p symbol="Símbolo (opcional): "
    set /p interval="Intervalo [1h]: "
    if "%interval%"=="" set interval=1h
    if "%symbol%"=="" (
        python technical_indicators.py signals %interval%
    ) else (
        python technical_indicators.py signals %symbol% %interval%
    )
    goto end
)

if "%choice%"=="6" (
    set /p symbol="Símbolo (ex: BTCUSDT): "
    set /p interval="Intervalo [1h]: "
    set /p days="Dias para trás [30]: "
    if "%interval%"=="" set interval=1h
    if "%days%"=="" set days=30
    python candle_collector.py fill %symbol% %interval% %days%
    goto end
)

if "%choice%"=="7" (
    goto end
)

echo Opção inválida!

:end
echo.
echo Pressione qualquer tecla para continuar...
pause >nul

REM ===========================================
REM monitor.bat - Monitoramento do Sistema
REM ===========================================

@echo off
echo === Monitor do Sistema ===

call venv\Scripts\activate.bat

:monitor_loop
cls
echo === Status do Sistema - %date% %time% ===
echo.

REM Verificar se processos estão rodando
tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq Coletor*" >nul 2>&1
if errorlevel 1 (
    echo ❌ Coletor não está rodando
) else (
    echo ✅ Coletor ativo
)

REM Verificar últimas coletas
python -c "
from candle_collector import DatabaseManager
import mysql.connector

try:
    db = DatabaseManager()
    
    # Verificar última coleta
    query = '''
    SELECT symbol, FROM_UNIXTIME(MAX(last_collected_time)/1000) as ultima_coleta
    FROM collection_control 
    WHERE status = 'active'
    ORDER BY last_collected_time DESC 
    LIMIT 5
    '''
    
    result = db.execute_query(query, fetch=True)
    
    print('Últimas coletas:')
    for r in result:
        print(f'  {r[\"symbol\"]}: {r[\"ultima_coleta\"]}')
    
    # Verificar erros
    query = '''
    SELECT COUNT(*) as erros 
    FROM collection_control 
    WHERE status = 'error'
    '''
    
    errors = db.execute_query(query, fetch=True)[0]['erros']
    print(f'\\nTokens com erro: {errors}')
    
    db.disconnect()
    
except Exception as e:
    print(f'Erro ao verificar status: {e}')
"

echo.
echo Pressione Ctrl+C para sair ou aguarde 60 segundos...
timeout /t 60 /nobreak >nul 2>&1
if not errorlevel 1 goto monitor_loop

REM ===========================================
REM backup.bat - Backup dos Dados
REM ===========================================

@echo off
echo === Backup dos Dados ===

set DATE=%date:~-4,4%%date:~-10,2%%date:~-7,2%
set DB_NAME=binanceimporter

echo Criando backup para %DATE%...

REM Backup da estrutura
mysqldump -u root -p --no-data %DB_NAME% > backup_structure_%DATE%.sql

REM Backup dos dados (últimos 30 dias)
mysqldump -u root -p %DB_NAME% candles collection_control technical_indicators --where="created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)" > backup_data_%DATE%.sql

echo Backup concluído: backup_data_%DATE%.sql
pause