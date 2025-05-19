# admin_llm_providers.py
import argparse
import json
import os
import sys
from typing import List, Dict, Any, Optional

# Adiciona o diretório 'src' ao sys.path para permitir importações de módulos do projeto
# Isso é necessário porque este script está na raiz e precisa importar de 'src'
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Agora podemos importar do src
from src.services.firebase_manager import inicializar_firebase, FbManagerFirestore
from src.services.firebase_client import _to_firestore_value, _from_firestore_value # Para conversão
from src.settings import FIREBASE_WEB_API_KEY # Apenas para uma verificação, não usado diretamente para admin

# --- Constantes ---
PROVIDERS_COLLECTION_ADMIN = "llm_providers_config"
DEFAULT_PROVIDERS_DOC_ID_ADMIN = "default_list"
PROVIDERS_FIELD_NAME_IN_DOC = "all_providers" # Nome do campo array no documento

# --- Funções Auxiliares ---
def get_firestore_manager() -> Optional[FbManagerFirestore]:
    """Inicializa Firebase e retorna uma instância do FbManagerFirestore."""
    try:
        if not FIREBASE_WEB_API_KEY or FIREBASE_WEB_API_KEY == "SUA_FIREBASE_WEB_API_KEY_AQUI":
            # A chave web não é usada pelo admin SDK, mas sua ausência pode indicar
            # que o setup inicial do settings.py não foi feito.
            print("AVISO: FIREBASE_WEB_API_KEY não parece estar configurada em src/settings.py.")
            print("         Isso não afeta diretamente este script admin, mas verifique sua configuração geral.")

        inicializar_firebase() # Usa credentials_manager para chave de serviço
        return FbManagerFirestore()
    except Exception as e:
        print(f"ERRO CRÍTICO: Falha ao inicializar Firebase Admin SDK ou Firestore: {e}")
        print("Verifique se as credenciais de serviço (arquivo .enc e chave no Keyring) estão configuradas corretamente.")
        return None

def load_providers_from_file(filepath: str) -> Optional[List[Dict[str, Any]]]:
    """Carrega a lista de provedores de um arquivo JSON."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list) and all(isinstance(item, dict) for item in data):
            return data
        else:
            print(f"ERRO: O arquivo JSON deve conter uma lista de dicionários de provedores.")
            return None
    except FileNotFoundError:
        print(f"ERRO: Arquivo não encontrado: {filepath}")
        return None
    except json.JSONDecodeError:
        print(f"ERRO: Arquivo não é um JSON válido: {filepath}")
        return None
    except Exception as e:
        print(f"ERRO ao carregar arquivo de provedores: {e}")
        return None

def save_providers_to_file(providers_list: List[Dict[str, Any]], filepath: str):
    """Salva a lista de provedores em um arquivo JSON."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(providers_list, f, indent=2, ensure_ascii=False)
        print(f"Lista de provedores salva em: {filepath}")
    except Exception as e:
        print(f"ERRO ao salvar arquivo de provedores: {e}")

def display_providers(providers_list: List[Dict[str, Any]]):
    """Exibe a lista de provedores de forma legível."""
    if not providers_list:
        print("Nenhum provedor configurado.")
        return
    print("\n--- Provedores LLM Configurados ---")
    for i, provider in enumerate(providers_list):
        print(f"\n{i+1}. Provedor: {provider.get('name_display', 'N/A')} (System Name: {provider.get('system_name', 'N/A')})")
        print(f"   API URL: {provider.get('api_url', 'N/A')}")
        models = provider.get('models', [])
        if models:
            print(f"   Modelos ({len(models)}):")
            for model in models:
                print(f"     - ID: {model.get('id', 'N/A')}, Nome: {model.get('name', 'N/A')}")
                costs = [
                    f"Input: ${model.get('input_coust_million', 0):.2f}/M",
                    f"Output: ${model.get('output_coust_million', 0):.2f}/M",
                    #f"Cache: ${model.get('cache_coust_million', 0):.2f}/M" # Se existir
                ]
                print(f"       Custos: {', '.join(costs)}")
        else:
            print("   Nenhum modelo configurado para este provedor.")
    print("----------------------------------")

# --- Funções CRUD ---
def read_providers_from_firestore(fs_manager: FbManagerFirestore) -> List[Dict[str, Any]]:
    """Lê a lista de provedores do Firestore."""
    if not fs_manager.db:
        print("ERRO: Cliente Firestore não disponível.")
        return []
    try:
        doc_ref = fs_manager.db.collection(PROVIDERS_COLLECTION_ADMIN).document(DEFAULT_PROVIDERS_DOC_ID_ADMIN)
        doc_snapshot = doc_ref.get()
        if doc_snapshot.exists:
            doc_data = doc_snapshot.to_dict()
            if doc_data and PROVIDERS_FIELD_NAME_IN_DOC in doc_data:
                # O campo 'all_providers' no Firestore estará no formato de valor do Firestore.
                # Precisamos convertê-lo para um array Python.
                # FbManagerFirestore não tem _from_firestore_value, então usamos o do firebase_client.
                # Este é um pequeno acoplamento, mas aceitável para este script admin.
                firestore_array_value = doc_data[PROVIDERS_FIELD_NAME_IN_DOC]
                # Se o campo já é um array python (o SDK Admin pode fazer isso), use diretamente.
                # Se for o formato REST (mapValue, arrayValue, etc.), precisa de conversão.
                # Assumindo que o SDK Admin Python retorna um array de dicts diretamente:
                if isinstance(firestore_array_value, list):
                     print("Lista de provedores lida do Firestore com sucesso (formato Python nativo).")
                     return firestore_array_value # Já está no formato Python
                else:
                    # Se for um Dict representando um ArrayValue do Firestore (via API REST ou tipo não Python)
                    # Este caso é menos provável com o SDK Admin Python, mas para robustez:
                    if isinstance(firestore_array_value, dict) and 'arrayValue' in firestore_array_value:
                        py_list = _from_firestore_value(firestore_array_value)
                        if isinstance(py_list, list):
                            print("Lista de provedores lida e convertida do Firestore com sucesso.")
                            return py_list
                    print(f"AVISO: Campo '{PROVIDERS_FIELD_NAME_IN_DOC}' não é uma lista Python ou formato Firestore ArrayValue esperado.")
                    return [] # Ou tratar como erro
            else:
                print(f"Documento '{DEFAULT_PROVIDERS_DOC_ID_ADMIN}' existe, mas campo '{PROVIDERS_FIELD_NAME_IN_DOC}' não encontrado ou vazio.")
                return []
        else:
            print(f"Documento de configuração de provedores '{DEFAULT_PROVIDERS_DOC_ID_ADMIN}' não encontrado no Firestore.")
            return []
    except Exception as e:
        print(f"ERRO ao ler provedores do Firestore: {e}")
        return []

def write_providers_to_firestore(fs_manager: FbManagerFirestore, providers_list: List[Dict[str, Any]]) -> bool:
    """Escreve (sobrescreve) a lista de provedores no Firestore."""
    if not fs_manager.db:
        print("ERRO: Cliente Firestore não disponível.")
        return False
    try:
        # Para o SDK Admin Python, podemos passar a lista de dicionários Python diretamente.
        # O SDK cuidará da conversão para os tipos do Firestore.
        data_to_set = {PROVIDERS_FIELD_NAME_IN_DOC: providers_list}
        doc_ref = fs_manager.db.collection(PROVIDERS_COLLECTION_ADMIN).document(DEFAULT_PROVIDERS_DOC_ID_ADMIN)
        doc_ref.set(data_to_set) # Sobrescreve o documento inteiro
        print(f"Lista de provedores escrita com sucesso no Firestore em '{PROVIDERS_COLLECTION_ADMIN}/{DEFAULT_PROVIDERS_DOC_ID_ADMIN}'.")
        return True
    except Exception as e:
        print(f"ERRO ao escrever provedores no Firestore: {e}")
        return False

# --- Handlers para os Comandos CLI ---
def handle_list(args, fs_manager: FbManagerFirestore):
    providers = read_providers_from_firestore(fs_manager)
    display_providers(providers)
    if args.output_file:
        save_providers_to_file(providers, args.output_file)

def handle_upload(args, fs_manager: FbManagerFirestore):
    if not args.input_file:
        print("ERRO: --input-file é obrigatório para o comando 'upload'.")
        return
    
    new_providers_list = load_providers_from_file(args.input_file)
    if new_providers_list is None:
        return # Erro já impresso por load_providers_from_file

    if write_providers_to_firestore(fs_manager, new_providers_list):
        print(f"Upload da lista de provedores do arquivo '{args.input_file}' para o Firestore realizado com sucesso.")
        display_providers(new_providers_list) # Mostra o que foi enviado
    else:
        print(f"Falha no upload da lista de provedores do arquivo '{args.input_file}'.")

def handle_add_provider(args, fs_manager: FbManagerFirestore):
    print("Funcionalidade 'add' (adicionar um provedor individualmente via CLI) não implementada ainda.")
    print("Use 'upload' com um arquivo JSON completo para modificar a lista de provedores.")
    # Para implementar:
    # 1. Ler a lista atual do Firestore.
    # 2. Criar um novo dict de provedor com base nos args (system_name, display_name, api_url).
    # 3. Adicionar modelos interativamente ou a partir de outro JSON.
    # 4. Adicionar o novo provedor à lista.
    # 5. Escrever a lista atualizada de volta ao Firestore.

def handle_delete_provider(args, fs_manager: FbManagerFirestore):
    print("Funcionalidade 'delete' (deletar um provedor individualmente via CLI) não implementada ainda.")
    print("Use 'upload' com um arquivo JSON completo (sem o provedor que deseja remover) para modificar a lista.")
    # Para implementar:
    # 1. Ler a lista atual.
    # 2. Encontrar e remover o provedor com base no system_name fornecido.
    # 3. Confirmar a remoção.
    # 4. Escrever a lista atualizada.

def main_cli():
    parser = argparse.ArgumentParser(description="Admin CRUD para configurações de Provedores LLM no Firebase.")
    subparsers = parser.add_subparsers(dest="command", title="Comandos", required=True)

    # Comando LIST
    list_parser = subparsers.add_parser("list", help="Lista os provedores LLM configurados no Firestore.")
    list_parser.add_argument("-o", "--output-file", type=str, help="Caminho do arquivo JSON para salvar a lista baixada.")
    list_parser.set_defaults(func=handle_list)

    # Comando UPLOAD
    upload_parser = subparsers.add_parser("upload", help="Sobrescreve a lista de provedores LLM no Firestore com base em um arquivo JSON local.")
    upload_parser.add_argument("-i", "--input-file", type=str, required=True, help="Caminho do arquivo JSON local contendo a lista de provedores.")
    upload_parser.set_defaults(func=handle_upload)

    # Comando ADD (Placeholder)
    # add_parser = subparsers.add_parser("add", help="Adiciona um novo provedor LLM (interativo ou via args).")
    # add_parser.add_argument("--system-name", required=True, help="Nome de sistema único para o provedor (ex: 'openai').")
    # add_parser.add_argument("--display-name", required=True, help="Nome de exibição do provedor (ex: 'OpenAI').")
    # add_parser.add_argument("--api-url", required=True, help="URL base da API do provedor.")
    # # Adicionar argumentos para modelos pode ser complexo via CLI, talvez um JSON para modelos?
    # add_parser.set_defaults(func=handle_add_provider)

    # Comando DELETE (Placeholder)
    # delete_parser = subparsers.add_parser("delete", help="Remove um provedor LLM pelo seu system_name.")
    # delete_parser.add_argument("--system-name", required=True, help="Nome de sistema do provedor a ser removido.")
    # delete_parser.set_defaults(func=handle_delete_provider)

    args = parser.parse_args()

    fs_manager_instance = get_firestore_manager()
    if not fs_manager_instance:
        sys.exit(1) # Sai se não conseguir inicializar o Firestore

    if hasattr(args, 'func'):
        args.func(args, fs_manager_instance)
    else:
        parser.print_help()

if __name__ == "__main__":
    print("Módulo Admin para Gerenciamento de Provedores LLM")
    print("Use -h ou --help para ver os comandos disponíveis.\n")
    # Exemplo de como popular um arquivo JSON inicial para upload:
    # exemplo_provedor_openai = {
    #     'system_name': 'openai',
    #     'name_display': 'OpenAI',
    #     'api_url': 'https://api.openai.com/v1',
    #     "models": [
    #         {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano (OpenAI)", 'input_coust_million': 0.1, 'output_coust_million': 0.4, 'cache_coust_million': 0.1},
    #         {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini (OpenAI)", 'input_coust_million': 0.4, 'output_coust_million': 1.6, 'cache_coust_million': 0.4},
    #         {"id": "o4-mini", "name": "OpenAI o4-mini", 'input_coust_million': 1.1, 'output_coust_million': 4.4, 'cache_coust_million': 1.1},
    #         {"id": "gpt-4.1", "name": "GPT-4.1 (OpenAI)", 'input_coust_million': 2.0, 'output_coust_million': 8.0, 'cache_coust_million': 2.0},
    #     ]
    # }
    # exemplo_provedor_azure = {
    #     'system_name': 'azure_openai_geral', # Use um system_name único
    #     'name_display': 'Azure OpenAI Service (Geral)',
    #     'api_url': 'https_SEU_RESOURCE_NAME_openai_azure_com', # Placeholder
    #     "models": [
    #         {"id": "gpt-35-turbo", "name": "GPT-3.5 Turbo (Azure)", 'input_coust_million': 0.0015, 'output_coust_million': 0.002, 'cache_coust_million': 0}, # Custos exemplo
    #         {"id": "gpt-4", "name": "GPT-4 (Azure)", 'input_coust_million': 0.03, 'output_coust_million': 0.06, 'cache_coust_million': 0}, # Custos exemplo
    #     ]
    # }
    # lista_para_salvar_exemplo = [exemplo_provedor_openai, exemplo_provedor_azure]
    # save_providers_to_file(lista_para_salvar_exemplo, "llm_providers_config_example.json")
    # print("\nExemplo de arquivo 'llm_providers_config_example.json' gerado. Edite-o e use com o comando 'upload'.")

    main_cli()

'''
Listar Configurações Atuais do Firestore:
>>> python admin_llm_providers.py list

Para salvar a lista em um arquivo:
>>> python admin_llm_providers.py list -o llm_providers_backup.json

Fazer Upload (Sobrescrever) Configurações no Firestore:
>>> python admin_llm_providers.py upload -i llm_providers_config_upload.json

# Comandos add e delete Individuais: Foram deixados como placeholders. Se precisar deles, a lógica envolveria ler a lista atual, 
  modificá-la em memória e depois escrever a lista completa de volta.

'''
