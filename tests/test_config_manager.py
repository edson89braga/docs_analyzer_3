# tests/utils/test_config_manager.py

import pytest
from unittest.mock import patch, call

# Importa o módulo a ser testado
from src import config_manager

# --- Fixtures ---

@pytest.fixture
def mock_keyring(mocker):
    """Fixture para mockar as funções do keyring."""
    # Usamos um dict para simular o armazenamento do keyring por serviço/usuário
    keyring_store = {}

    def mock_get_password(service, username):
        return keyring_store.get((service, username), None)

    def mock_set_password(service, username, password):
        keyring_store[(service, username)] = password

    def mock_delete_password(service, username):
        # Simula a exceção se a senha não existir
        if (service, username) not in keyring_store:
            # Importa a exceção específica se existir, senão usa uma genérica
            try:
                 from keyring.errors import PasswordDeleteError
                 raise PasswordDeleteError("not found")
            except ImportError:
                 raise Exception("PasswordDeleteError not found or simulated error")
        del keyring_store[(service, username)]

    mock_get = mocker.patch('keyring.get_password', side_effect=mock_get_password)
    mock_set = mocker.patch('keyring.set_password', side_effect=mock_set_password)
    mock_del = mocker.patch('keyring.delete_password', side_effect=mock_delete_password)

    # Fornece acesso ao store e aos mocks para os testes
    return {'get': mock_get, 'set': mock_set, 'delete': mock_del, 'store': keyring_store}

# --- Testes para get_proxy_settings ---

def test_get_proxy_settings_not_configured(mock_keyring):
    """Testa quando nenhuma configuração de proxy existe no keyring."""
    settings = config_manager.get_proxy_settings()
    assert settings == {'proxy_enabled': False, 'password_saved': False, 'ip': None, 'port': None, 'username': None}
    calls = [
        call(config_manager.PROXY_KEYRING_SERVICE, config_manager.PROXY_ENABLED_USER),
        call(config_manager.PROXY_KEYRING_SERVICE, config_manager.PROXY_PASSWORD_SAVED_USER),
    ]
    mock_keyring['get'].assert_has_calls(calls, any_order=True)

def test_get_proxy_settings_disabled(mock_keyring):
    """Testa quando o proxy está explicitamente desabilitado."""
    service = config_manager.PROXY_KEYRING_SERVICE
    # <<< Define 'enabled' como false, mas 'password_saved' pode ou não existir >>>
    mock_keyring['store'][(service, config_manager.PROXY_ENABLED_USER)] = "false"
    # Mock get_password para retornar o valor de enabled e None para password_saved
    get_calls = {
        (service, config_manager.PROXY_ENABLED_USER): "false",
        (service, config_manager.PROXY_PASSWORD_SAVED_USER): None,
    }
    mock_keyring['get'].side_effect = lambda s, u: get_calls.get((s, u))

    settings = config_manager.get_proxy_settings()

    assert settings == {'proxy_enabled': False, 'password_saved': False, 'ip': None, 'port': None, 'username': None}
    # Verifica que NÃO tentou buscar ip, port, user
    assert call(service, config_manager.PROXY_IP_USER) not in mock_keyring['get'].call_args_list
    assert call(service, config_manager.PROXY_PORT_USER) not in mock_keyring['get'].call_args_list
    assert call(service, config_manager.PROXY_USERNAME_USER) not in mock_keyring['get'].call_args_list

def test_get_proxy_settings_enabled_no_auth(mock_keyring):
    """Testa quando habilitado com IP/Porta, mas sem usuário."""
    service = config_manager.PROXY_KEYRING_SERVICE
    mock_keyring['store'][(service, config_manager.PROXY_ENABLED_USER)] = "true"
    mock_keyring['store'][(service, config_manager.PROXY_PASSWORD_SAVED_USER)] = "false" # Exemplo: não salvou senha
    mock_keyring['store'][(service, config_manager.PROXY_IP_USER)] = "192.168.1.100"
    mock_keyring['store'][(service, config_manager.PROXY_PORT_USER)] = "8080"
    # Garante que username retorna None
    mock_keyring['get'].side_effect = lambda s, u: mock_keyring['store'].get((s, u), None)


    settings = config_manager.get_proxy_settings()
    assert settings == {
        'proxy_enabled': True,
        'password_saved': False, # Espera o valor lido
        'ip': '192.168.1.100',
        'port': '8080',
        'username': None,
    }
    # Verifica chamadas esperadas
    calls = [
        call(service, config_manager.PROXY_ENABLED_USER),
        call(service, config_manager.PROXY_PASSWORD_SAVED_USER),
        call(service, config_manager.PROXY_IP_USER),
        call(service, config_manager.PROXY_PORT_USER),
        call(service, config_manager.PROXY_USERNAME_USER),
    ]
    mock_keyring['get'].assert_has_calls(calls, any_order=True)
    assert call(service, config_manager.PROXY_PASSWORD_USER) not in mock_keyring['get'].call_args_list

def test_get_proxy_settings_enabled_with_user_pass_saved(mock_keyring): # <<< Renomeado e ajustado
    """Testa habilitado com usuário e flag 'password_saved' é true."""
    service = config_manager.PROXY_KEYRING_SERVICE
    mock_keyring['store'][(service, config_manager.PROXY_ENABLED_USER)] = "true"
    mock_keyring['store'][(service, config_manager.PROXY_PASSWORD_SAVED_USER)] = "true" # <<< Senha salva
    mock_keyring['store'][(service, config_manager.PROXY_IP_USER)] = "proxy.example.com"
    mock_keyring['store'][(service, config_manager.PROXY_PORT_USER)] = "3128"
    mock_keyring['store'][(service, config_manager.PROXY_USERNAME_USER)] = "testuser"
    # Define o side_effect para retornar os valores do store
    mock_keyring['get'].side_effect = lambda s, u: mock_keyring['store'].get((s, u))

    settings = config_manager.get_proxy_settings()
    # <<< ASSERT AJUSTADO >>>
    assert settings == {
        'proxy_enabled': True,
        'password_saved': True, # Espera True
        'ip': 'proxy.example.com',
        'port': '3128',
        'username': 'testuser',
    }
    # Verifica que get_password NÃO foi chamado para a SENHA real
    assert call(service, config_manager.PROXY_PASSWORD_USER) not in mock_keyring['get'].call_args_list

def test_get_proxy_settings_keyring_error(mock_keyring):
    """Testa quando keyring.get_password levanta uma exceção."""
    mock_keyring['get'].side_effect = Exception("Cannot connect to Keyring")
    settings = config_manager.get_proxy_settings()
    assert settings == {'proxy_enabled': False, 'password_saved': False, 'ip': None, 'port': None, 'username': None}

# --- Testes para save_proxy_settings ---

def test_save_proxy_settings_full_config_save_password(mock_keyring):
    """Testa salvar config completa com usuário e senha (e save=True)."""
    config_to_save = {
        'proxy_enabled': True,
        'ip': '10.0.0.1',
        'port': '8888',
        'username': 'proxyuser',
        'password': 'proxypassword',
        'password_saved': True # Flag indicando para salvar a senha
    }
    success = config_manager.save_proxy_settings(config_to_save)

    assert success is True
    service = config_manager.PROXY_KEYRING_SERVICE
    # Verifica se tudo foi salvo corretamente
    assert mock_keyring['store'][(service, config_manager.PROXY_ENABLED_USER)] == "true"
    assert mock_keyring['store'][(service, config_manager.PROXY_IP_USER)] == "10.0.0.1"
    assert mock_keyring['store'][(service, config_manager.PROXY_PORT_USER)] == "8888"
    assert mock_keyring['store'][(service, config_manager.PROXY_USERNAME_USER)] == "proxyuser"
    # Verifica se o flag password_saved foi salvo (se a função save_proxy_settings faz isso)
    assert mock_keyring['store'].get((service, config_manager.PROXY_PASSWORD_SAVED_USER)) == "true"
    # Verifica se a SENHA foi salva
    assert mock_keyring['store'][(service, config_manager.PROXY_PASSWORD_USER)] == "proxypassword"
    # Verifica chamadas ao mock set
    mock_keyring['set'].assert_any_call(service, config_manager.PROXY_ENABLED_USER, "true")
    mock_keyring['set'].assert_any_call(service, config_manager.PROXY_IP_USER, "10.0.0.1")
    mock_keyring['set'].assert_any_call(service, config_manager.PROXY_PORT_USER, "8888")
    mock_keyring['set'].assert_any_call(service, config_manager.PROXY_USERNAME_USER, "proxyuser")
    mock_keyring['set'].assert_any_call(service, config_manager.PROXY_PASSWORD_USER, "proxypassword")
    # mock_keyring['set'].assert_any_call(service, 'password_saved', "true") # Se salva o flag

def test_save_proxy_settings_dont_save_password(mock_keyring):
    """Testa salvar config com usuário, mas sem salvar a senha (save=False)."""
    config_to_save = {
        'proxy_enabled': True,
        'ip': '10.0.0.1',
        'port': '8888',
        'username': 'proxyuser',
        'password': 'some_password_in_ui_but_not_saved', # Senha no form, mas não salva
        'password_saved': False # Flag indicando para NÃO salvar a senha
    }
    # Simula uma senha previamente salva para garantir que delete seja chamado
    service = config_manager.PROXY_KEYRING_SERVICE
    mock_keyring['store'][(service, config_manager.PROXY_PASSWORD_USER)] = "old_password"

    success = config_manager.save_proxy_settings(config_to_save)

    assert success is True
    # Verifica se os outros dados foram salvos
    assert mock_keyring['store'][(service, config_manager.PROXY_USERNAME_USER)] == "proxyuser"
    # Verifica se o flag foi salvo (se aplicável)
    assert mock_keyring['store'].get((service, config_manager.PROXY_PASSWORD_SAVED_USER)) == "false"
    # Verifica se a SENHA foi DELETADA
    assert (service, config_manager.PROXY_PASSWORD_USER) not in mock_keyring['store']
    mock_keyring['delete'].assert_called_once_with(service, config_manager.PROXY_PASSWORD_USER)

def test_save_proxy_settings_no_user(mock_keyring):
    """Testa salvar config sem usuário (deve limpar user e pass)."""
    config_to_save = {
        'proxy_enabled': True,
        'ip': '10.0.0.1',
        'port': '8888',
        'username': None, # Sem usuário
        'password': None,
        'password_saved': False
    }
    # Simula user/pass previamente salvos
    service = config_manager.PROXY_KEYRING_SERVICE
    mock_keyring['store'][(service, config_manager.PROXY_USERNAME_USER)] = "olduser"
    mock_keyring['store'][(service, config_manager.PROXY_PASSWORD_USER)] = "oldpass"
    mock_keyring['store'][(service, config_manager.PROXY_PASSWORD_SAVED_USER)] = "true" 

    success = config_manager.save_proxy_settings(config_to_save)

    assert success is True
    # Verifica se user e pass foram DELETADOS
    assert (service, config_manager.PROXY_USERNAME_USER) not in mock_keyring['store']
    assert (service, config_manager.PROXY_PASSWORD_USER) not in mock_keyring['store']
    assert mock_keyring['store'].get((service, config_manager.PROXY_PASSWORD_SAVED_USER)) == "false"
    # Verifica se delete foi chamado para ambos
    mock_keyring['delete'].assert_any_call(service, config_manager.PROXY_USERNAME_USER)
    mock_keyring['delete'].assert_any_call(service, config_manager.PROXY_PASSWORD_USER)

def test_save_proxy_settings_disabled(mock_keyring):
    """Testa salvar config com proxy desabilitado."""
    config_to_save = {'enabled': False} # Não inclui outros campos
    service = config_manager.PROXY_KEYRING_SERVICE
    mock_keyring['store'][(service, config_manager.PROXY_PASSWORD_SAVED_USER)] = "true" # Flag salvo antes

    success = config_manager.save_proxy_settings(config_to_save)

    assert success is True
    assert mock_keyring['store'].get((service, config_manager.PROXY_ENABLED_USER)) == "false"
    # <<< Verifica se o flag foi salvo como false (pelo default do .get) >>>
    assert mock_keyring['store'].get((service, config_manager.PROXY_PASSWORD_SAVED_USER)) == "false"
    mock_keyring['delete'].assert_any_call(service, config_manager.PROXY_USERNAME_USER)
    mock_keyring['delete'].assert_any_call(service, config_manager.PROXY_PASSWORD_USER)

def test_save_proxy_settings_keyring_error(mock_keyring):
    """Testa quando keyring.set_password levanta uma exceção."""
    config_to_save = {'proxy_enabled': True, 'ip': '1.1.1.1', 'port': '80'}
    mock_keyring['set'].side_effect = Exception("Cannot write to Keyring")

    success = config_manager.save_proxy_settings(config_to_save)
    assert success is False

'''
Fixture mock_keyring: Adaptei o mock para simular melhor o armazenamento chave/valor do Keyring usando um dicionário (keyring_store). Isso permite verificar se set_password salvou o valor correto e se delete_password removeu a entrada. Ele também simula a exceção PasswordDeleteError (ou genérica) se delete for chamado para uma chave inexistente.

get_proxy_settings:
    Testa os cenários: não configurado, desabilitado, habilitado sem autenticação, habilitado com autenticação (verificando que a senha não é lida aqui), e erro no Keyring.
    Verifica os valores retornados e quais chamadas ao mock_keyring['get'] foram feitas (ou não feitas).

save_proxy_settings:
    Testa salvar a configuração completa, incluindo a senha quando password_saved é True. Verifica se todos os set_password ocorreram com os valores corretos.
    Testa o caso onde password_saved é False. Verifica se delete_password foi chamado para a senha.
    Testa o caso sem username. Verifica se delete_password foi chamado para usuário e senha.
    Testa salvar com enabled=False.
    Testa um erro durante o set_password.

'''

