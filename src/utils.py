import os, keyring
from rich import print

from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)

import functools, urllib, ssl
def with_proxy(skip_ssl_verify: bool = True):
    """
    Decorador de fábrica que aplica configurações de proxy e, opcionalmente,
    desativa a verificação de certificado SSL para a função decorada.

    Busca as configurações de proxy usando config_manager.

    Args:
        skip_ssl_verify (bool, optional): Se True (padrão), desativa a
            verificação de certificado SSL. Se False, mantém a verificação padrão.

    Returns:
        Callable: O decorador real a ser aplicado à função.
    """
    from src import config_manager
    def decorator(func):
        """O decorador real que envolve a função."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """A função wrapper que aplica e restaura as configurações."""
            # Salva o estado original do ambiente e SSL
            previous_http_proxy = os.environ.get('HTTP_PROXY', '')
            previous_https_proxy = os.environ.get('HTTPS_PROXY', '')
            previous_wdm_ssl_verify = os.environ.get('WDM_SSL_VERIFY', '') # Era '1', mas '' é mais seguro como padrão não definido
            previous_pyhttps_verify = os.environ.get('PYTHONHTTPSVERIFY', '') # Era '1', mas '' é mais seguro
            previous_ssl_cert_file = os.environ.get('SSL_CERT_FILE', '')
            previous_requests_ca = os.environ.get('REQUESTS_CA_BUNDLE', '')
            original_ssl_context = ssl._create_default_https_context
            logger.debug(f"with_proxy: Estado inicial salvo. skip_ssl_verify={skip_ssl_verify}")

            # Tentar aplicar configurações de proxy e SSL
            proxy_config = None
            try:
                # Obter configurações do config_manager
                proxy_config = config_manager.get_proxy_settings()

                if proxy_config and proxy_config.get('proxy_enabled'):
                    ip = proxy_config.get('ip')
                    port = proxy_config.get('port')
                    username = proxy_config.get('username')
                    password_saved = proxy_config.get('password_saved')

                    if not ip or not port:
                        logger.warning("Proxy habilitado mas IP ou Porta não definidos no config_manager. Proxy não será aplicado.")
                    else:
                        logger.info(f"Proxy habilitado via config_manager: {ip}:{port}, User: {username}, Password Saved: {password_saved}")
                        proxy_url_base = f"http://{ip}:{port}"
                        proxy_url_auth = None

                        # Buscar senha somente se houver usuário e indicação de senha salva
                        if username and password_saved:
                            try:
                                password = keyring.get_password(
                                    config_manager.PROXY_KEYRING_SERVICE, # Usar constante do config_manager
                                    config_manager.PROXY_PASSWORD_USER    # Usar constante do config_manager
                                )
                                if password:
                                    logger.debug("Senha do proxy recuperada do Keyring.")
                                    # Cuidado com caracteres especiais na senha/usuário para URLs
                                    safe_user = urllib.parse.quote(username)
                                    safe_pass = urllib.parse.quote(password)
                                    proxy_url_auth = f"http://{safe_user}:{safe_pass}@{ip}:{port}"
                                else:
                                    logger.warning(f"Proxy user '{username}' definido e senha marcada como salva, mas senha não encontrada no Keyring.")
                                    # Decide se continua sem autenticação ou falha? Por ora, continua sem.
                            except Exception as e:
                                logger.error(f"Erro ao buscar senha do proxy do Keyring: {e}", exc_info=True)
                                # Falha ao buscar senha, continua sem autenticação

                        # Definir variáveis de ambiente do proxy
                        final_proxy_url = proxy_url_auth if proxy_url_auth else proxy_url_base
                        os.environ['HTTP_PROXY'] = final_proxy_url
                        os.environ['HTTPS_PROXY'] = final_proxy_url
                        logger.debug(f"Variáveis de ambiente HTTP_PROXY/HTTPS_PROXY definidas para: {final_proxy_url}")

                        # Aplicar desativação de SSL *condicionalmente*
                        if skip_ssl_verify:
                            logger.warning("Desativando verificação de certificado SSL devido à configuração do proxy e skip_ssl_verify=True.")
                            # 1. Variáveis de ambiente comuns
                            os.environ['WDM_SSL_VERIFY'] = '0'
                            os.environ['PYTHONHTTPSVERIFY'] = '0'
                            # Limpar caminhos de certificado pode ajudar em alguns casos
                            os.environ['SSL_CERT_FILE'] = ''
                            os.environ['REQUESTS_CA_BUNDLE'] = ''

                            # 2. Desabilitar avisos de SSL inseguro (urllib3)
                            try:
                                import urllib3
                                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                                logger.debug("Avisos InsecureRequestWarning do urllib3 desativados.")
                            except ImportError:
                                logger.debug("urllib3 não encontrado para desativar warnings.")
                            except Exception as e:
                                logger.error(f"Erro ao tentar desativar warnings do urllib3: {e}", exc_info=True)


                            # 3. Modificar o contexto SSL global (último recurso, impacta tudo)
                            try:
                                ssl._create_default_https_context = ssl._create_unverified_context
                                logger.debug("Contexto SSL padrão (_create_default_https_context) modificado para _create_unverified_context.")
                            except Exception as e:
                                 logger.error(f"Erro ao tentar modificar o contexto SSL padrão: {e}", exc_info=True)

                            # 4. Configurar o módulo requests se estiver disponível
                            try:
                                import requests
                                # Tentar desativar na sessão padrão e via urllib3 dentro do requests
                                requests.packages.urllib3.disable_warnings()
                                requests.Session().verify = False # Afeta novas sessões criadas a partir daqui
                                logger.debug("Configurações de verificação SSL para 'requests' (se importado) ajustadas.")
                            except ImportError:
                                logger.debug("'requests' não encontrado para configuração SSL específica.")
                            except Exception as e:
                                logger.error(f"Erro ao tentar configurar 'requests' para SSL: {e}", exc_info=True)
                        else:
                             logger.info("Verificação de certificado SSL mantida (skip_ssl_verify=False).")
                else:
                    logger.debug("Proxy desabilitado ou não configurado no config_manager.")

                # Executa a função original decorada
                return func(*args, **kwargs)

            except Exception as e:
                 # Logar qualquer erro inesperado ocorrido DENTRO da lógica do proxy/ssl setup
                 logger.error(f"Erro inesperado dentro do setup do decorador with_proxy: {e}", exc_info=True)
                 raise # Re-lançar a exceção para não mascarar problemas

            finally:
                # Restaura TUDO para o estado original, não importa o que aconteceu
                logger.debug("with_proxy: Restaurando estado original do ambiente e SSL...")
                os.environ['HTTP_PROXY'] = previous_http_proxy
                os.environ['HTTPS_PROXY'] = previous_https_proxy
                os.environ['WDM_SSL_VERIFY'] = previous_wdm_ssl_verify
                os.environ['PYTHONHTTPSVERIFY'] = previous_pyhttps_verify
                os.environ['SSL_CERT_FILE'] = previous_ssl_cert_file
                os.environ['REQUESTS_CA_BUNDLE'] = previous_requests_ca
                ssl._create_default_https_context = original_ssl_context

                # Remover chaves se elas não existiam antes
                if not previous_http_proxy: os.environ.pop('HTTP_PROXY', None)
                if not previous_https_proxy: os.environ.pop('HTTPS_PROXY', None)
                if not previous_wdm_ssl_verify: os.environ.pop('WDM_SSL_VERIFY', None)
                if not previous_pyhttps_verify: os.environ.pop('PYTHONHTTPSVERIFY', None)
                if not previous_ssl_cert_file: os.environ.pop('SSL_CERT_FILE', None)
                if not previous_requests_ca: os.environ.pop('REQUESTS_CA_BUNDLE', None)

                logger.debug("with_proxy: Restauração concluída.")

        return wrapper
    return decorator    # @with_proxy(skip_ssl_verify=False)

### ========================================================================================================
import requests, tiktoken, unidecode
import collections.abc
from time import time
from rich.console import Console
from rich.table import Table

def timing_decorator(calc_by_item=False):
    """Decorador para calcular o tempo de execução de funções decoradas.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time()  # Marca o tempo de início
            result = func(*args, **kwargs)  # Chama a função decorada
            end_time = time()  # Marca o tempo de término
            total_time = end_time - start_time
            print('\n')
            logger.info(f"F: {func.__name__} - Tempo execução total : {total_time:.4f}s")
            if calc_by_item and args and type(args) != str and isinstance(args[0], collections.abc.Iterable):
                logger.info(f"F: {func.__name__} - Tempo p/item - Loops: {len(args[0])} : {total_time/len(args[0]):.4f}s")
            print('\n')
            return result
        return wrapper
    return decorator

def count_tokens(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    """
    Calcula o número de tokens em um texto usando tiktoken.

    Args:
        text (str): O texto a ser tokenizado.
        model_name (str, optional): O nome do modelo para obter o encoding correto.
                                    Default é "gpt-3.5-turbo".
                                    Outros comuns: "gpt-4", "text-davinci-003".
                                    Se o modelo não for encontrado, tenta "cl100k_base".

    Returns:
        int: O número de tokens.
    """
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        # Se o modelo não for encontrado, usar um encoding padrão como cl100k_base
        # print(f"Aviso: Modelo '{model_name}' não encontrado para tiktoken. Usando 'cl100k_base'.") # Opcional
        encoding = tiktoken.get_encoding("cl100k_base")
    
    # O método encode não aceita 'verbose' ou 'add_special_tokens'.
    # Para controlar tokens especiais, você usaria:
    # encoding.encode(text, allowed_special={"<|endoftext|>", ...})
    # encoding.encode(text, disallowed_special=())
    # Para uma contagem simples, apenas o texto é suficiente.
    token_integers = encoding.encode(text)
    return len(token_integers)

def reduce_text_to_limit(text_full: str, token_limit: int, model_name: str = "gpt-3.5-turbo") -> str:
    """
    Reduz o texto completo para caber no limite de tokens especificado,
    decodificando os tokens de volta para texto.

    Args:
        text_full (str): Texto completo a ser reduzido.
        token_limit (int): Limite máximo de tokens permitido para o texto reduzido.
        model_name (str, optional): O nome do modelo para obter o encoding correto.
                                    Default é "gpt-3.5-turbo".

    Returns:
        str: Texto reduzido que (aproximadamente) cabe no limite de tokens,
             ou o texto original se já estiver dentro do limite.
    """
    if not text_full or token_limit <= 0:
        return ""

    try:
        # Obter o codificador para o modelo especificado
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        # Fallback para um encoding comum se o modelo não for encontrado
        # print(f"Aviso: Modelo '{model_name}' não encontrado para tiktoken. Usando 'cl100k_base' para reduce_text_to_limit.") # Opcional
        encoding = tiktoken.get_encoding("cl100k_base")
    
    # 1. Codificar o texto completo em tokens
    # Os parâmetros verbose e add_special_tokens não são usados aqui.
    all_tokens = encoding.encode(text_full)
    
    # 2. Verificar se o texto já está dentro do limite
    if len(all_tokens) <= token_limit:
        return text_full
    
    # 3. Truncar a lista de tokens para o limite especificado
    truncated_tokens = all_tokens[:token_limit]
    
    # 4. Decodificar os tokens truncados de volta para texto
    # O método decode pode levantar erros se os tokens truncados formarem uma sequência inválida de UTF-8.
    # Isso é raro com truncagem simples, mas pode acontecer se você cortar no meio de um caractere multi-byte.
    # tiktoken lida bem com isso geralmente, mas para robustez, um try-except pode ser adicionado.
    try:
        reduced_text = encoding.decode(truncated_tokens)
    except Exception as e:
        # print(f"Erro ao decodificar tokens truncados: {e}. Tentando decodificar com substituição de erros.") # Opcional
        # Tentar decodificar substituindo bytes problemáticos, se necessário (pode não ser ideal para todos os casos)
        reduced_text = encoding.decode_with_offsets(truncated_tokens)[0] # [0] para pegar o texto
        # Ou, uma abordagem mais simples é decodificar token por token e juntar,
        # ou aceitar a perda de um token final se a decodificação falhar.
        # Para a maioria dos casos de truncagem simples, a decodificação direta funciona.
        # Se for um problema persistente, pode ser necessário um tratamento mais sofisticado
        # para garantir que não se corte no meio de uma sequência de bytes de um caractere.
        # No entanto, tiktoken é geralmente robusto.
        # Se a decodificação simples falhar, uma estratégia é reduzir o número de tokens em 1 e tentar novamente.
        # Ex: reduced_text = encoding.decode(truncated_tokens[:-1])
        # Por ora, vamos manter a decodificação direta.
        pass # Mantendo o comportamento anterior em caso de erro, mas idealmente logar ou tratar.

    return reduced_text

def print_dict_as_table(data_dict, selected_keys, sort_key=None):
    """
    Imprime o dicionário de forma tabular, usando Rich, conforme as chaves selecionadas.
    
    :param data_dict: Dicionário a ser exibido.
    :param selected_keys: Lista de chaves que devem ser exibidas na tabela.
    :param sort_key: Chave pela qual os dados devem ser ordenados (opcional).
    """
    console = Console()
    
    # Cria uma tabela
    table = Table(show_header=True, header_style="bold magenta")
    
    # Adiciona colunas para as chaves selecionadas
    table.add_column("Key")
    for key in selected_keys:
        table.add_column(key.capitalize())
        
    items = data_dict.items()
    if sort_key:
        items = sorted(items, key=lambda item: item[1].get(sort_key, ""))
        
    # Preenche as linhas da tabela com os valores das chaves selecionadas
    for i, data in items:
        row = [str(data.get(key, "")) for key in selected_keys]
        row = [str(i)] + row
        table.add_row(*row)
        
    # Exibe a tabela no console
    console.print(table)

def get_string_intervalos(numeros, incrementa_1=False):
    """
    Converte uma lista de números em uma string de intervalos.
    
    :param numeros: Lista de números a serem agrupados
    :param incrementa_1: Se True, incrementa 1 em cada número (padrão: False)
    :return: String com os números agrupados em intervalos
    """
    numeros = sorted(set(numeros))
    if incrementa_1:
        numeros = [ind+1 for ind in numeros]
    intervalos = []
    i = 0
    while i < len(numeros):
        inicio = numeros[i]
        while i < len(numeros) - 1 and numeros[i + 1] == numeros[i] + 1: # se o próximo número é consecutivo
            i += 1
        fim = numeros[i]

        # Adiciona o intervalo ou o número isolado à lista de intervalos
        if inicio == fim:
            intervalos.append(str(inicio))
        else:
            intervalos.append(f"{inicio}-{fim}")
        i += 1

    return ', '.join(intervalos)

### ========================================================================================================

@timing_decorator()
def get_uf_list():
    # Função para buscar UFs
    url = "https://brasilapi.com.br/api/ibge/uf/v1"
    response = requests.get(url)
    if response.status_code == 200:
        return [uf['sigla'] for uf in response.json()]
    else:
        return []

@timing_decorator()
def get_municipios_by_uf(uf):
    # Função para buscar municípios por UF
    url = f"https://brasilapi.com.br/api/ibge/municipios/v1/{uf}"
    response = requests.get(url)
    if response.status_code == 200:
        return [municipio['nome'] for municipio in response.json()]
    else:
        return []
    
def convert_moeda(valor):
    """
    Converte um valor numérico para formato monetário brasileiro.
    
    :param valor: Valor numérico a ser formatado
    :return: String com valor formatado em reais
    """
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def convert_float_to_milhar(numero):
    """
    Converte um número float para formato com separador de milhar.
    
    :param numero: Número a ser formatado
    :return: String com número formatado
    """
    return f"{numero:,}".replace(",", ".")

def obter_string_normalizada(string_atual, lista_opções):
    """
    Normaliza uma string e a compara com uma lista de opções.
    
    :param string_atual: String a ser normalizada e comparada
    :param lista_opções: Lista de strings para comparação
    :return: String correspondente da lista ou None se não encontrar
    """
    # Normaliza o nome do município a ser buscado
    nome_normalizado = unidecode(string_atual.lower())

    for item in lista_opções:
        # Normaliza cada município na lista:
        item_normalizado = unidecode(item.lower())
        # Compara os municípios normalizados:
        if nome_normalizado == item_normalizado:
            return item  # Retorna o município correspondente
    
    return None

### ========================================================================================================

import unicodedata, re
def normalize_key(text: str) -> str:
    """
    Normaliza uma string para ser usada como chave:
    - Remove acentos.
    - Converte para minúsculas.
    - Substitui espaços e caracteres não alfanuméricos por underscore.
    - Remove underscores duplicados.
    """
    if not isinstance(text, str):
        text = str(text)
    # Converte para minúsculas
    text = text.lower()
    #
    text = text.replace('(%)', 'percentual')
    text = text.replace('(kg)', '').strip()
    if text.endswith('_id'):
        text = text[:-3]
    # Remove acentos (compatibilidade NFKD)
    nfkd_form = unicodedata.normalize('NFKD', text)
    text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Substitui espaços e não alfanuméricos por underscore
    text = re.sub(r'[^a-z0-9]+', '_', text)
    # Remove underscores no início/fim e múltiplos underscores
    text = re.sub(r'_+', '_', text).strip('_')
    return text
