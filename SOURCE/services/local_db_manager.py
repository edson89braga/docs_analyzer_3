# FILE: src\services\local_db_manager.py

import logging, threading, sqlite3, json
from typing import Optional
from pathlib import Path

from SOURCE.config.provider import is_local_mode
from SOURCE.settings import APP_DATA_DIR

logger = logging.getLogger(__name__)

APP_DATA_DIR = Path(APP_DATA_DIR)
DB_FILE = APP_DATA_DIR / "local_storage.sqlite"

class LocalDBManager:
    """
    Gerencia um banco de dados SQLite local para persistência de dados do usuário,
    como prompts customizados e histórico de chats.
    Implementado como um singleton para garantir uma única conexão.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(LocalDBManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # O __init__ será chamado toda vez, mas a conexão só será estabelecida uma vez.
        if not hasattr(self, 'conn'):
            try:
                DB_FILE.parent.mkdir(parents=True, exist_ok=True)
                self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
                self.cursor = self.conn.cursor()
                self._create_tables()
                logger.info(f"Conexão com o banco de dados local estabelecida em: {DB_FILE}")
            except sqlite3.Error as e:
                logger.critical(f"Erro crítico ao conectar ou criar o banco de dados local: {e}", exc_info=True)
                self.conn = None

    def _create_tables(self):
        """Cria as tabelas necessárias se elas não existirem."""
        if not self.conn: return
        try:
            # Tabela para prompts customizados (chave-valor simples)
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS custom_prompts (
                    key TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Tabela para histórico de chats (a ser usada futuramente)
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_history (
                    session_id TEXT NOT NULL,
                    message_id REAL PRIMARY KEY,
                    author TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Tabela genérica para configurações da aplicação
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')            
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Erro ao criar tabelas no banco de dados local: {e}")

    def _get_scoped_key(self, key: str, user_id: str = None) -> str:
        """Garante isolamento de chaves entre usuários no modo servidor."""
        if not is_local_mode() and user_id:
            return f"{user_id}_{key}"
        return key

    def save_custom_prompt(self, key: str, content: str, user_id: str = None) -> bool:
        """Salva ou atualiza um prompt customizado no banco de dados."""
        if not self.conn: return False
        scoped_key = self._get_scoped_key(key, user_id)
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO custom_prompts (key, content, last_updated)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (scoped_key, content))
            self.conn.commit()
            logger.debug(f"Prompt customizado com chave '{key}' salvo no banco de dados local.")
            return True
        except sqlite3.Error as e:
            logger.error(f"Erro ao salvar prompt customizado '{key}': {e}")
            return False

    def get_custom_prompt(self, key: str, user_id: str = None) -> Optional[str]:
        """Recupera um prompt customizado do banco de dados."""
        if not self.conn: return None
        scoped_key = self._get_scoped_key(key, user_id)
        try:
            self.cursor.execute("SELECT content FROM custom_prompts WHERE key = ?", (scoped_key,))
            row = self.cursor.fetchone()
            if row:
                logger.debug(f"Prompt customizado com chave '{key}' recuperado do banco de dados local.")
                return row[0]
            return None
        except sqlite3.Error as e:
            logger.error(f"Erro ao recuperar prompt customizado '{key}': {e}")
            return None

    def save_setting(self, key: str, value: dict, user_id: str = None) -> bool:
        """Salva uma configuração (dicionário) como JSON no banco de dados."""
        if not self.conn: return False
        scoped_key = self._get_scoped_key(key, user_id)
        try:
            json_value = json.dumps(value)
            self.cursor.execute('''
                INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)
            ''', (scoped_key, json_value))
            self.conn.commit()
            logger.debug(f"Configuração '{key}' salva no banco de dados local.")
            return True
        except (sqlite3.Error, TypeError) as e:
            logger.error(f"Erro ao salvar configuração '{key}': {e}")
            return False

    def delete_setting(self, key: str, user_id: str = None) -> bool:
        """Deleta uma configuração da tabela app_settings."""
        if not self.conn: return False
        scoped_key = self._get_scoped_key(key, user_id)
        try:
            self.cursor.execute("DELETE FROM app_settings WHERE key = ?", (scoped_key,))
            self.conn.commit()
            # Verifica se alguma linha foi de fato afetada
            if self.cursor.rowcount > 0:
                logger.debug(f"Configuração '{key}' deletada do banco de dados local.")
            return True
        except sqlite3.Error as e:
            logger.error(f"Erro ao deletar configuração '{key}': {e}")
            return False

    def get_setting(self, key: str, user_id: str = None) -> Optional[dict]:
        """Recupera uma configuração do banco de dados e a converte de JSON."""
        if not self.conn: return None
        scoped_key = self._get_scoped_key(key, user_id)
        try:
            self.cursor.execute("SELECT value FROM app_settings WHERE key = ?", (scoped_key,))
            row = self.cursor.fetchone()
            if row and row[0]:
                logger.debug(f"Configuração '{key}' recuperada do banco de dados local.")
                return json.loads(row[0])
            return None
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Erro ao recuperar ou decodificar configuração '{key}': {e}")
            return None

    def close(self):
        """Fecha a conexão com o banco de dados."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Conexão com o banco de dados local fechada.")

