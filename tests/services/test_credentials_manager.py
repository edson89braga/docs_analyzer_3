# tests/utils/test_credentials_manager.py

import pytest
import os
import json
from unittest.mock import patch, MagicMock, mock_open

# Importa o módulo a ser testado
from src.services import credentials_manager
from cryptography.fernet import Fernet, InvalidToken

# --- Fixtures ---

@pytest.fixture
def mock_keyring(mocker):
    """Fixture para mockar as funções do keyring."""
    mock_get = mocker.patch('keyring.get_password', return_value=None)
    mock_set = mocker.patch('keyring.set_password')
    mock_del = mocker.patch('keyring.delete_password')
    # Retorna um dicionário com os mocks para controle nos testes
    return {'get': mock_get, 'set': mock_set, 'delete': mock_del}

@pytest.fixture
def patch_constants(monkeypatch, tmp_path):
    """Fixture para substituir constantes de caminho e criar diretório temporário."""
    # Cria um diretório de dados temporário dentro do tmp_path do pytest
    temp_app_data_dir = tmp_path / "app_data"
    temp_app_data_dir.mkdir()
    temp_enc_file_path = temp_app_data_dir / credentials_manager.ENCRYPTED_SERVICE_KEY_FILENAME

    # Monkeypatch as constantes no módulo credentials_manager
    monkeypatch.setattr(credentials_manager, 'APP_DATA_DIR', str(temp_app_data_dir))
    monkeypatch.setattr(credentials_manager, 'ENCRYPTED_SERVICE_KEY_PATH', str(temp_enc_file_path))
    # Retorna o caminho do arquivo .enc temporário para uso nos testes
    return str(temp_enc_file_path)


@pytest.fixture
def test_fernet_key():
    """Retorna uma chave Fernet válida e fixa para testes."""
    # Chave gerada uma vez e codificada em base64 para consistência
    # (Em uma situação real, você geraria uma offline e colaria aqui)
    # Exemplo: key = Fernet.generate_key(); print(key.decode())
    return b'q3vA4v7wJ9dR8oL2pGc0mFhN5kZsXyHbI1uW6tRgOkY='

@pytest.fixture
def fernet_instance(test_fernet_key):
    """Retorna uma instância Fernet com a chave de teste."""
    return Fernet(test_fernet_key)

# --- Testes para get_encryption_key ---

def test_get_encryption_key_found(mock_keyring, test_fernet_key):
    """Testa get_encryption_key quando a chave existe no keyring."""
    mock_keyring['get'].return_value = test_fernet_key.decode('utf-8')
    key = credentials_manager.get_encryption_key()
    assert key == test_fernet_key
    mock_keyring['get'].assert_called_once_with(
        credentials_manager.KEYRING_SERVICE_FIREBASE,
        credentials_manager.KEYRING_USER_ENCRYPTION_KEY
    )

def test_get_encryption_key_not_found(mock_keyring):
    """Testa get_encryption_key quando a chave não existe no keyring."""
    mock_keyring['get'].return_value = None
    key = credentials_manager.get_encryption_key()
    assert key is None
    mock_keyring['get'].assert_called_once()

def test_get_encryption_key_keyring_error(mock_keyring):
    """Testa get_encryption_key quando o keyring levanta uma exceção."""
    mock_keyring['get'].side_effect = Exception("Keyring access denied")
    key = credentials_manager.get_encryption_key()
    assert key is None
    mock_keyring['get'].assert_called_once()

# --- Testes para load_encrypted_service_key ---

def test_load_encrypted_service_key_success(patch_constants):
    """Testa carregar o arquivo .enc quando ele existe."""
    enc_file_path = patch_constants
    expected_content = b"dummy_encrypted_content"
    with open(enc_file_path, "wb") as f:
        f.write(expected_content)

    content = credentials_manager.load_encrypted_service_key()
    assert content == expected_content

def test_load_encrypted_service_key_not_found(patch_constants):
    """Testa carregar o arquivo .enc quando ele não existe."""
    # patch_constants garante que o diretório existe, mas o arquivo não
    content = credentials_manager.load_encrypted_service_key()
    assert content is None

@patch('builtins.open', side_effect=IOError("Permission denied"))
def test_load_encrypted_service_key_read_error(mock_open, patch_constants):
    """Testa carregar o arquivo .enc quando há um erro de I/O."""
    # Simula que o arquivo existe para passar a verificação os.path.exists
    with patch('os.path.exists', return_value=True):
        content = credentials_manager.load_encrypted_service_key()
        assert content is None
        mock_open.assert_called_once() # Verifica se tentou abrir

# --- Testes para encrypt / decrypt (públicos) ---

def test_encrypt_success(mocker, mock_keyring, test_fernet_key):
    """Testa a função pública encrypt."""
    mock_keyring['get'].return_value = test_fernet_key.decode('utf-8')
    plain_text = "senha_super_secreta"
    encrypted_data = credentials_manager.encrypt(plain_text)

    assert encrypted_data is not None
    # Verifica se pode ser descriptografado com a mesma chave (indiretamente)
    fernet = Fernet(test_fernet_key)
    assert fernet.decrypt(encrypted_data).decode('utf-8') == plain_text

def test_encrypt_no_key(mocker, mock_keyring):
    """Testa encrypt quando a chave Fernet não está no Keyring."""
    mock_keyring['get'].return_value = None
    encrypted_data = credentials_manager.encrypt("some data")
    assert encrypted_data is None

def test_decrypt_success(mocker, mock_keyring, test_fernet_key, fernet_instance):
    """Testa a função pública decrypt."""
    mock_keyring['get'].return_value = test_fernet_key.decode('utf-8')
    plain_text = "dados_originais"
    encrypted_data = fernet_instance.encrypt(plain_text.encode('utf-8'))

    decrypted_text = credentials_manager.decrypt(encrypted_data)
    assert decrypted_text == plain_text

def test_decrypt_no_key(mocker, mock_keyring):
    """Testa decrypt quando a chave Fernet não está no Keyring."""
    mock_keyring['get'].return_value = None
    decrypted_text = credentials_manager.decrypt(b"some_bytes")
    assert decrypted_text is None

def test_decrypt_invalid_token(mocker, mock_keyring, test_fernet_key):
    """Testa decrypt com dados inválidos/corrompidos."""
    mock_keyring['get'].return_value = test_fernet_key.decode('utf-8')
    invalid_encrypted_data = b"gAAAAAB..." # Bytes inválidos que causam InvalidToken

    decrypted_text = credentials_manager.decrypt(invalid_encrypted_data)
    assert decrypted_text is None

# --- Testes para are_credentials_set_up ---

@pytest.mark.parametrize("key_exists, file_exists, expected", [
    (True, True, True),
    (True, False, False),
    (False, True, False),
    (False, False, False),
])
def test_are_credentials_set_up(mocker, mock_keyring, patch_constants, key_exists, file_exists, expected):
    """Testa a verificação de setup em todas as combinações."""
    mock_key = b"some_key" if key_exists else None
    mocker.patch.object(credentials_manager, 'get_encryption_key', return_value=mock_key)
    mocker.patch('os.path.exists', return_value=file_exists)

    assert credentials_manager.are_credentials_set_up() == expected

# --- Testes para get_decrypted_service_key_json ---

def test_get_decrypted_key_success(mocker, mock_keyring, patch_constants, test_fernet_key, fernet_instance):
    """Testa o fluxo completo de sucesso para obter a chave JSON."""
    valid_json_str = '{"type": "service_account", "project_id": "test-proj"}'
    encrypted_content = fernet_instance.encrypt(valid_json_str.encode('utf-8'))

    mock_keyring['get'].return_value = test_fernet_key.decode('utf-8')
    # Simula a existência e conteúdo do arquivo .enc
    mocker.patch.object(credentials_manager, 'load_encrypted_service_key', return_value=encrypted_content)

    result_json = credentials_manager.get_decrypted_service_key_json()
    assert result_json == valid_json_str

def test_get_decrypted_key_fail_no_key(mocker, mock_keyring, patch_constants):
    """Testa falha ao obter JSON porque a chave Fernet não existe."""
    mock_keyring['get'].return_value = None
    mocker.patch('os.path.exists', return_value=True) # Simula que o arquivo existe
    mocker.patch('builtins.open', mock_open(read_data=b"some_data"))

    assert credentials_manager.get_decrypted_service_key_json() is None

def test_get_decrypted_key_fail_no_file(mocker, mock_keyring, patch_constants, test_fernet_key):
    """Testa falha ao obter JSON porque o arquivo .enc não existe."""
    mock_keyring['get'].return_value = test_fernet_key.decode('utf-8')
    mocker.patch('os.path.exists', return_value=False) # Arquivo não existe

    assert credentials_manager.get_decrypted_service_key_json() is None

def test_get_decrypted_key_fail_invalid_token(mocker, mock_keyring, patch_constants, test_fernet_key):
    """Testa falha ao obter JSON devido a token inválido na descriptografia."""
    mock_keyring['get'].return_value = test_fernet_key.decode('utf-8')
    mocker.patch.object(credentials_manager, 'load_encrypted_service_key', return_value=b"invalid_token_data")

    assert credentials_manager.get_decrypted_service_key_json() is None

def test_get_decrypted_key_fail_not_json(mocker, mock_keyring, patch_constants, test_fernet_key, fernet_instance):
    """Testa falha ao obter JSON porque o conteúdo descriptografado não é JSON."""
    not_json_str = "isso nao e json"
    encrypted_content = fernet_instance.encrypt(not_json_str.encode('utf-8'))

    mock_keyring['get'].return_value = test_fernet_key.decode('utf-8')
    mocker.patch.object(credentials_manager, 'load_encrypted_service_key', return_value=encrypted_content)

    assert credentials_manager.get_decrypted_service_key_json() is None

# --- Testes para setup_credentials_from_file ---

@patch('src.services.credentials_manager._generate_encryption_key') # Mock a geração da chave
def test_setup_credentials_success(mock_gen_key, mock_keyring, patch_constants, test_fernet_key, fernet_instance):
    """Testa o fluxo completo de setup bem-sucedido."""
    mock_gen_key.return_value = test_fernet_key # Força o uso da chave conhecida
    valid_json_str = '{"client_email": "test@example.com"}'
    enc_file_path = patch_constants

    # Executa o setup
    success = credentials_manager.setup_credentials_from_file(valid_json_str)

    assert success is True
    # Verifica se a chave foi salva no keyring
    mock_keyring['set'].assert_any_call(
        credentials_manager.KEYRING_SERVICE_FIREBASE,
        credentials_manager.KEYRING_USER_ENCRYPTION_KEY,
        test_fernet_key.decode('utf-8')
    )
    # Verifica se o arquivo foi criado
    assert os.path.exists(enc_file_path)
    # Verifica o conteúdo do arquivo (descriptografando)
    with open(enc_file_path, "rb") as f:
        file_content = f.read()
    decrypted = fernet_instance.decrypt(file_content).decode('utf-8')
    assert decrypted == valid_json_str

def test_setup_credentials_fail_invalid_json(mock_keyring, patch_constants):
    """Testa falha no setup se o JSON de entrada for inválido."""
    invalid_json_str = '{"email": "test@example.com",}' # JSON inválido (vírgula extra)
    success = credentials_manager.setup_credentials_from_file(invalid_json_str)
    assert success is False
    mock_keyring['set'].assert_not_called() # Não deve tentar salvar nada
    assert not os.path.exists(patch_constants) # Arquivo não deve ser criado

@patch('src.services.credentials_manager._generate_encryption_key')
@patch('keyring.set_password', side_effect=Exception("Keyring write error"))
def test_setup_credentials_fail_keyring_save(mock_set_pwd, mock_gen_key, mock_keyring, patch_constants, test_fernet_key):
    """Testa falha no setup se salvar no Keyring falhar."""
    mock_gen_key.return_value = test_fernet_key
    valid_json_str = '{"a": 1}'

    success = credentials_manager.setup_credentials_from_file(valid_json_str)
    assert success is False
    mock_set_pwd.assert_called_once() # Tentou salvar
    assert not os.path.exists(patch_constants) # Arquivo não deve ser criado

@patch('src.services.credentials_manager._generate_encryption_key')
@patch('builtins.open', side_effect=IOError("Cannot write file")) # Mock para falhar escrita
def test_setup_credentials_fail_file_save(mock_open, mock_gen_key, mock_keyring, patch_constants, test_fernet_key):
    """Testa falha no setup se salvar o arquivo .enc falhar."""
    mock_gen_key.return_value = test_fernet_key
    valid_json_str = '{"b": 2}'

    # Simula que o diretório existe para não falhar no makedirs
    with patch('os.makedirs'):
        success = credentials_manager.setup_credentials_from_file(valid_json_str)

    assert success is False
    # Keyring set DEVE ter sido chamado
    mock_keyring['set'].assert_called_with(
         credentials_manager.KEYRING_SERVICE_FIREBASE,
         credentials_manager.KEYRING_USER_ENCRYPTION_KEY,
         test_fernet_key.decode('utf-8')
    )
    # Verifica se tentou abrir o arquivo para escrita
    mock_open.assert_called_once()
    # O arquivo não deve existir realmente (pois open falhou)
    assert not os.path.exists(patch_constants)


'''
Fixtures:
    mock_keyring: Usa mocker.patch (do pytest-mock) para substituir as funções do keyring. Retorna um dict com os mocks para controle.
    patch_constants: Usa monkeypatch (do pytest) para substituir os caminhos APP_DATA_DIR e ENCRYPTED_SERVICE_KEY_PATH dentro do módulo testado, apontando para um diretório/arquivo temporário criado pelo fixture tmp_path do pytest. Isso isola os testes do sistema de arquivos real.
    test_fernet_key, fernet_instance: Fornecem uma chave e instância Fernet consistentes para testes de cripto/descripto.

get_encryption_key: Testa os cenários onde a chave é encontrada, não encontrada, ou um erro ocorre no Keyring. Verifica se o mock foi chamado corretamente.

load_encrypted_service_key: Testa carregar um arquivo existente, não existente e um erro de leitura (mockando open). Usa patch_constants para gerenciar o arquivo.

encrypt/decrypt: Testam as funções públicas de criptografia, incluindo casos de sucesso, chave ausente e token inválido (para decrypt).

are_credentials_set_up: Usa @pytest.mark.parametrize para testar todas as 4 combinações de existência da chave Keyring e do arquivo .enc. Mocka as funções dependentes (get_encryption_key, os.path.exists).

get_decrypted_service_key_json: Testa o fluxo completo de obtenção, incluindo sucesso e falhas em cada etapa (sem chave, sem arquivo, token inválido, não JSON).

setup_credentials_from_file: Testa o fluxo completo de configuração, incluindo sucesso (verificando chamadas ao Keyring e conteúdo do arquivo .enc) e falhas (JSON inválido, erro ao salvar no Keyring, erro ao salvar o arquivo .enc). Mocka a geração da chave Fernet para ter um resultado previsível.

'''
