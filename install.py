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
    print(DATABASE_CONFIG)
    
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