import os, keyring, logging, re
from rich import print
from typing import Union, Optional

#from src.logger.logger import LoggerSetup
#logger = LoggerSetup.get_logger(__name__)
logger = logging.getLogger(__name__)

from src.settings import (PROXY_URL_DEFAULT, PROXY_PORT_DEFAULT, K_PROXY_ENABLED, K_PROXY_IP_URL, K_PROXY_PORT, K_PROXY_USERNAME, 
                            K_PROXY_PASSWORD, K_PROXY_PASSWORD_SAVED)

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

                if proxy_config.get(K_PROXY_ENABLED):
                    ip = proxy_config.get(K_PROXY_IP_URL)
                    port = proxy_config.get(K_PROXY_PORT)
                    username = proxy_config.get(K_PROXY_USERNAME)
                    password_saved = proxy_config.get(K_PROXY_PASSWORD_SAVED)

                    if not ip or not port:
                        logger.warning("Proxy habilitado mas IP ou Porta não definidos no config_manager. Proxy não será aplicado.")
                    else:
                        logger.info(f"Proxy habilitado via config_manager: {ip}:{port}, User: {username}, Password Saved: {password_saved}")
                        proxy_url_base = f"http://{ip}:{port}"
                        proxy_url_auth = None

                        # Buscar senha somente se houver usuário, além da habilitação do proxy
                        if username:
                            try:
                                password = keyring.get_password(
                                    config_manager.PROXY_KEYRING_SERVICE, # Usar constante do config_manager
                                    config_manager.K_PROXY_PASSWORD       # Usar constante do config_manager
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
import requests, tiktoken
import collections.abc
from unidecode import unidecode
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
            print(f"F: {func.__name__} - Tempo execução total : {total_time:.4f}s")
            #logger.info(f"F: {func.__name__} - Tempo execução total : {total_time:.4f}s")
            if calc_by_item and args and type(args) != str and isinstance(args[0], collections.abc.Iterable):
                print(f"F: {func.__name__} - Tempo p/item - Loops: {len(args[0])} : {total_time/len(args[0]):.4f}s")
                #logger.info(f"F: {func.__name__} - Tempo p/item - Loops: {len(args[0])} : {total_time/len(args[0]):.4f}s")
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

def update_dict_municipios_local():
    import json
    file_path = os.path.join('assets', 'dict_municipios.json')
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    ufs = get_uf_list()
    dict_municipios = {uf: [] for uf in ufs}
    try:
        for uf in dict_municipios:
            print(f'Capturando municipios de: {uf}...')
            dict_municipios[uf] = get_municipios_by_uf(uf)
            print(f'Concluído com lista de {len(dict_municipios[uf])} municipios.\n')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(dict_municipios, f, ensure_ascii=False, indent=4)
        print(f"Dicionário de municípios salvo em: {file_path}")
        return dict_municipios
    except Exception as e:
        print(f"Erro ao salvar dicionário de municípios: {e}")
        return {}

# Carregar o dicionário de municípios do arquivo JSON local
def load_dict_municipios_local():
    try:
        import json
        file_path = os.path.join('assets', 'dict_municipios.json')
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print(f"Arquivo de municípios não encontrado: {file_path}.")
            return update_dict_municipios_local()
    except Exception as e:
        print(f"Erro ao carregar dicionário de municípios: {e}")
        return {}

# Carregar os dados na inicialização do módulo
MUNICIPIOS_POR_UF = load_dict_municipios_local()
LISTA_UFS = sorted(list(MUNICIPIOS_POR_UF.keys()))

def clean_and_convert_to_float(value_str: Union[str, float, int, None], default_if_empty_or_error: float = 0.0) -> float:
    """
    Tenta limpar uma string que representa um valor monetário ou numérico
    e convertê-la para float.

    Args:
        value_str: A string a ser convertida. Pode também receber float/int/None.
        default_if_empty_or_error: Valor padrão a retornar se a string for vazia,
                                     None, ou a conversão falhar.

    Returns:
        O valor como float, ou o valor padrão em caso de erro/vazio.
    """
    if isinstance(value_str, (float, int)):
        return float(value_str)
    
    if value_str is None or not isinstance(value_str, str) or not value_str.strip():
        return default_if_empty_or_error

    # Remove caracteres não numéricos, exceto ponto e vírgula (para moeda) e sinal negativo
    # Mantém o sinal negativo no início, se houver
    cleaned_str = re.sub(r'[^\d,.-]', '', value_str)
    
    # Se ainda contém letras após a primeira limpeza (ex: "não informado"), considera erro
    if re.search(r'[a-zA-Z]', cleaned_str):
        return default_if_empty_or_error

    # Padroniza para usar ponto como separador decimal
    if ',' in cleaned_str and '.' in cleaned_str:
        # Se ambos existem, verifica qual é o último.
        # Ex: "1.234,56" -> "1234.56"
        # Ex: "1,234.56" -> "1234.56" (se o ponto for o decimal)
        if cleaned_str.rfind(',') > cleaned_str.rfind('.'): # Vírgula é decimal
            cleaned_str = cleaned_str.replace('.', '').replace(',', '.')
        else: # Ponto é decimal
            cleaned_str = cleaned_str.replace(',', '')
    elif ',' in cleaned_str: # Apenas vírgula, assume que é decimal
        cleaned_str = cleaned_str.replace(',', '.')
    
    # Remove múltiplos pontos, exceto o último (se for decimal)
    if cleaned_str.count('.') > 1:
        parts = cleaned_str.split('.')
        cleaned_str = "".join(parts[:-1]) + "." + parts[-1]

    try:
        return float(cleaned_str)
    except ValueError:
        return default_if_empty_or_error

ESTADO_PARA_SIGLA = {
    unidecode("acre").lower(): "AC",
    unidecode("alagoas").lower(): "AL",
    unidecode("amapa").lower(): "AP",
    unidecode("amazonas").lower(): "AM",
    unidecode("bahia").lower(): "BA",
    unidecode("ceara").lower(): "CE",
    unidecode("distrito federal").lower(): "DF",
    unidecode("espirito santo").lower(): "ES",
    unidecode("goias").lower(): "GO",
    unidecode("maranhao").lower(): "MA",
    unidecode("mato grosso").lower(): "MT",
    unidecode("mato grosso do sul").lower(): "MS",
    unidecode("minas gerais").lower(): "MG",
    unidecode("para").lower(): "PA",
    unidecode("paraiba").lower(): "PB",
    unidecode("parana").lower(): "PR",
    unidecode("pernambuco").lower(): "PE",
    unidecode("piaui").lower(): "PI",
    unidecode("rio de janeiro").lower(): "RJ",
    unidecode("rio grande do norte").lower(): "RN",
    unidecode("rio grande do sul").lower(): "RS",
    unidecode("rondonia").lower(): "RO",
    unidecode("roraima").lower(): "RR",
    unidecode("santa catarina").lower(): "SC",
    unidecode("sao paulo").lower(): "SP",
    unidecode("sergipe").lower(): "SE",
    unidecode("tocantins").lower(): "TO",
    # Adicionar siglas diretamente também, para o caso da LLM retornar a sigla
    "ac": "AC", "al": "AL", "ap": "AP", "am": "AM", "ba": "BA", "ce": "CE", "df": "DF", "es": "ES",
    "go": "GO", "ma": "MA", "mt": "MT", "ms": "MS", "mg": "MG", "pa": "PA", "pb": "PB", "pr": "PR",
    "pe": "PE", "pi": "PI", "rj": "RJ", "rn": "RN", "rs": "RS", "ro": "RO", "rr": "RR", "sc": "SC",
    "sp": "SP", "se": "SE", "to": "TO"
}

def get_sigla_uf(nome_estado_ou_sigla: Optional[str]) -> Optional[str]:
    """
    Converte um nome de estado (ou sigla) para sua sigla UF normalizada.
    Retorna None se não conseguir encontrar uma correspondência.
    """
    if not nome_estado_ou_sigla or not isinstance(nome_estado_ou_sigla, str):
        return None
    
    normalizado = unidecode(nome_estado_ou_sigla.strip()).lower()
    return ESTADO_PARA_SIGLA.get(normalizado)


### ========================================================================================================
  
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

cleanup_logger = logging.getLogger("temp_files_cleanup")

import shutil, atexit

def cleanup_old_temp_files(upload_temp_dir: str, max_age_seconds: int = 24 * 60 * 60):
    """
    Limpa arquivos e subdiretórios na pasta especificada que são mais antigos
    que max_age_seconds (padrão: 24 horas).

    Args:
        upload_temp_dir (str): O caminho para a pasta de uploads temporários.
        max_age_seconds (int): A idade máxima em segundos que um arquivo/diretório
                               pode ter para não ser removido.
    """
    if not os.path.isdir(upload_temp_dir):
        cleanup_logger.warning(f"Diretório temporário '{upload_temp_dir}' não encontrado. Nada a limpar.")
        return

    cleanup_logger.info(f"Iniciando limpeza de arquivos antigos em '{upload_temp_dir}' (mais de {max_age_seconds / 3600:.1f} horas).")
    current_time = time()
    items_removed_count = 0
    items_failed_to_remove_count = 0

    # Itera sobre todos os itens (arquivos e diretórios) na pasta temporária
    for item_name in os.listdir(upload_temp_dir):
        item_path = os.path.join(upload_temp_dir, item_name)
        try:
            # Obtém o tempo da última modificação do item
            item_mod_time = os.path.getmtime(item_path)
            item_age_seconds = current_time - item_mod_time

            if item_age_seconds > max_age_seconds:
                if os.path.isfile(item_path):
                    os.remove(item_path)
                    cleanup_logger.info(f"Arquivo antigo removido: {item_path} (idade: {item_age_seconds / 3600:.1f} horas)")
                    items_removed_count += 1
                elif os.path.isdir(item_path):
                    # Para diretórios, você pode querer remover recursivamente
                    # CUIDADO: shutil.rmtree remove o diretório e todo o seu conteúdo.
                    # Certifique-se de que é seguro fazer isso e que os diretórios
                    # realmente contêm apenas dados temporários que podem ser descartados.
                    shutil.rmtree(item_path)
                    cleanup_logger.info(f"Diretório antigo e seu conteúdo removidos: {item_path} (idade: {item_age_seconds / 3600:.1f} horas)")
                    items_removed_count += 1
                else:
                    cleanup_logger.debug(f"Item '{item_path}' não é arquivo nem diretório (ex: link simbólico). Ignorando.")

        except FileNotFoundError:
            # O arquivo pode ter sido removido por outro processo entre listdir e getmtime/remove
            cleanup_logger.debug(f"Item '{item_path}' não encontrado durante a limpeza (pode já ter sido removido).")
        except PermissionError:
            cleanup_logger.error(f"Erro de permissão ao tentar remover '{item_path}'. Verifique as permissões.")
            items_failed_to_remove_count += 1
        except Exception as e:
            cleanup_logger.error(f"Erro inesperado ao processar ou remover '{item_path}': {e}")
            items_failed_to_remove_count += 1

    cleanup_logger.info(f"Limpeza concluída. {items_removed_count} itens removidos, {items_failed_to_remove_count} falhas.")

def register_temp_files_cleanup(temp_dir_to_clean: str):
    # 2. No seu módulo principal, onde você quer que a limpeza seja registrada:
    """Registra a função de limpeza para ser chamada na saída do programa."""
    if not temp_dir_to_clean:
        cleanup_logger.error("Caminho do diretório temporário não fornecido para registro da limpeza. A limpeza no atexit não será registrada.")
        return
        
    cleanup_logger.info(f"Registrando a função de limpeza de arquivos temporários para o diretório '{temp_dir_to_clean}' no atexit.")
    # Usa functools.partial para passar argumentos para a função registrada com atexit
    # Ou uma lambda, mas partial é geralmente mais limpo para isso.
    from functools import partial
    cleanup_func_with_args = partial(cleanup_old_temp_files, temp_dir_to_clean)
    atexit.register(cleanup_func_with_args)

def format_seconds_to_min_sec(total_segundos):
    total_segundos = round(total_segundos)
    minutos = int(total_segundos) // 60
    segundos = int(total_segundos) % 60
    return f"{minutos:02d}m:{segundos:02d}s"

