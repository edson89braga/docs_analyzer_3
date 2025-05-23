# -*- coding: utf-8 -*-
import json, csv, re, keyring # keyring.get_password('gpt_api_key', '-')
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from openai import OpenAI
#from fuzzywuzzy import process as fzw_process
from rich import print

aux, fzw_process = [None] *2

modelos_IA = ["gpt-4o-mini-2024-07-18", "gpt-4o-mini", "gpt-4o-2024-08-06", "o1-mini", "gpt-4o"]
pricing = {
    "o1-preview": {'in-1k': (6*15)/1000, 'out-1k': (6*60)/1000},
    "o1-mini": {'in-1k': (6*3)/1000, 'out-1k': (6*12)/1000}, 
    "gpt-4o": {'in-1k': (6*2.5)/1000, 'out-1k': (6*10)/1000},
    "gpt-4o-2024-08-06": {'in-1k': (6*2.5)/1000, 'out-1k': (6*10)/1000}, 
    "gpt-4o-mini": {'in-1k': (6*0.15)/1000, 'out-1k': (6*0.60)/1000}, 
    "gpt-4o-mini-2024-07-18": {'in-1k': (6*0.15)/1000, 'out-1k': (6*0.60)/1000}, 
    }

''' Tamanho prompt1 resumido + prompt2: 32666 caracteres, e 8326 tokens '''

def save_usage_to_csv(response, csv_filename='api_usage.csv'):
    """
    Salva as informações de uso da API em um arquivo CSV.

    Args:
        response: Objeto de resposta da API contendo informações de uso
        csv_filename (str, optional): Nome do arquivo CSV. Padrão: 'api_usage.csv'

    A função extrai os seguintes dados da resposta:
        - Modelo utilizado
        - Tokens de prompt
        - Tokens de conclusão
        - Total de tokens
        - Timestamp da requisição

    O arquivo CSV terá as seguintes colunas:
        ['timestamp', 'model', 'prompt_tokens', 'completion_tokens', 'total_tokens']
    """
    # Extrai informações de uso do response
    model_used = response.model
    prompt_tokens = response.usage.prompt_tokens
    completion_tokens = response.usage.completion_tokens
    total_tokens = response.usage.total_tokens
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    #cached_tokens = response.usage.prompt_tokens_details.cached_tokens
    
    # Verifica se o arquivo CSV já existe e, caso contrário, cria o cabeçalho
    try:
        with open(csv_filename, mode='x', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['timestamp', 'model', 'prompt_tokens', 'completion_tokens', 'total_tokens'])
    except FileExistsError:
        pass  # Arquivo já existe, não precisa recriar o cabeçalho
    
    # Adiciona as informações da API no arquivo CSV
    with open(csv_filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, model_used, prompt_tokens, completion_tokens, total_tokens])
        
class DocumentoAnalise(BaseModel):
    """
    Modelo Pydantic para representar a análise de um documento recebido pela Polícia Federal.

    Atributos:
        descricao_geral (str): Descrição geral do documento
        tipo_documento_origem (str): Tipo do documento de origem
        orgao_origem (str): Órgão que originou o documento
        uf_origem (str): UF de origem do documento
        municipio_origem (str): Município de origem do documento
        resumo_fato (str): Resumo dos fatos relatados
        tipo_local (str): Tipo de local onde ocorreu o fato
        uf_fato (str): UF onde ocorreu o fato
        municipio_fato (str): Município onde ocorreu o fato
        valor_apuracao (float): Valor estimado do prejuízo/apuração
        area_atribuicao (str): Área de atribuição do caso
        tipificacao_penal (str): Tipificação penal aplicável
        tipo_a_autuar (str): Tipo de autuação recomendado
        assunto_re (Optional[str]): Assunto do Registro Especial (se aplicável)
        destinacao (str): Delegacia de destino do caso
        pessoas_envolvidas (List[str]): Lista de pessoas envolvidas
        linha_do_tempo (Optional[List[str]]): Linha do tempo dos fatos
        observacoes (Optional[str]): Observações complementares
        
        justificativa_tipo_documento_origem (str): Justificativa para o tipo de documento
        justificativa_orgao_origem (str): Justificativa para o órgão de origem
        justificativa_municipio_uf_origem (str): Justificativa para município/UF de origem
        justificativa_tipo_local (str): Justificativa para o tipo de local
        justificativa_municipio_uf_fato (str): Justificativa para município/UF do fato
        justificativa_valor_apuracao (Optional[str]): Justificativa para o valor de apuração
        justificativa_area_atribuicao (str): Justificativa para a área de atribuição
        justificativa_tipificacao_penal (str): Justificativa para a tipificação penal
        justificativa_tipo_a_autuar (str): Justificativa para o tipo de autuação
        justificativa_assunto_re (Optional[str]): Justificativa para o assunto do RE
        justificativa_destinacao (str): Justificativa para a destinação

    Configurações:
        json_schema_extra: Exemplo de preenchimento do modelo
    """
    descricao_geral: str 
    tipo_documento_origem: str 
    orgao_origem: str 
    uf_origem: str 
    municipio_origem: str 
    resumo_fato: str 
    tipo_local: str 
    uf_fato: str 
    municipio_fato: str 
    valor_apuracao: float  
    area_atribuicao: str 
    tipificacao_penal: str 
    tipo_a_autuar: str 
    assunto_re: Optional[str] 
    destinacao: str 
    pessoas_envolvidas: List[str] 
    linha_do_tempo: Optional[List[str]] 
    observacoes: Optional[str] 

    justificativa_tipo_documento_origem: str 
    justificativa_orgao_origem: str 
    justificativa_municipio_uf_origem: str 
    justificativa_tipo_local: str 
    justificativa_municipio_uf_fato: str 
    justificativa_valor_apuracao: Optional[str] 
    justificativa_area_atribuicao: str 
    justificativa_tipificacao_penal: str 
    justificativa_tipo_a_autuar: str 
    justificativa_assunto_re: Optional[str] 
    justificativa_destinacao: str 

    class ConfigDict:
        json_schema_extra = {
            "example": {
                "descricao_geral": "Contrato de prestação de serviços de TI.",
                "tipo_documento_origem": "Ofício",
                "orgao_origem": "Prefeitura de São Paulo",
                "uf_origem": "SP",
                "municipio_origem": "São Paulo",
                "resumo_fato": "Irregularidades em contrato de serviços de TI.",
                "tipo_local": "Instituição pública",
                "uf_fato": "SP",
                "municipio_fato": "São Paulo",
                "valor_apuracao": 500000.00,
                "area_atribuicao": "Crimes Finaneceiros",
                "tipificacao_penal": "Art. 171-CP",
                "tipo_a_autuar": "NCV - Notícia-Crime em Verificação",
                "assunto_re": "Irregularidades contratuais",
                "destinacao": "DELECOR/SR/PF/SP",
                "pessoas_envolvidas": [
                    "João Silva - CPF: 123.456.789-00 - Contratante",
                    "Empresa XYZ - CNPJ: 12.345.678/0001-99 - Contratada"
                ],
                "linha_do_tempo": [
                    "01/01/2023: Assinatura do contrato",
                    "15/02/2023: Descoberta das irregularidades"
                ],
                "observacoes": "Investigação em andamento.",
                
                "justificativa_tipo_documento_origem": "Conforme Ofício nº 418/2023-PMSP citado",
                "justificativa_orgao_origem": "Conforme cabeçalho de identificação do Ofício nº 418/2023-PMSP",
                "justificativa_municipio_uf_origem": "A origem do ofício é identificada claramente no cabeçalho do documento, onde consta 'Prefeitura de São Paulo/SP' ",
                "justificativa_tipo_local": "Conforme se depreende do trecho '...' ",
                "justificativa_municipio_uf_fato": "Local da referida Instituição pública",
                "justificativa_valor_apuracao": "Conforme se depreende do trecho '...' ",
                "justificativa_area_atribuicao": "O documento analisa um esquema de desvio de verbas públicas relacionado a contratos de licitação, conforme descrito no trecho: '...'. A natureza das irregularidades identificadas, bem como a ênfase em fraudes e desvio de recursos, justificam a classificação do documento na área de atribuição de Crimes Financeiros.", 
                "justificativa_tipificacao_penal": "O documento descreve um esquema de fraude onde os envolvidos obtiveram vantagem ilícita ao enganar vítimas com promessas falsas de investimentos, caracterizando a prática de estelionato, conforme o disposto no Art. 171 do Código Penal.",
                "justificativa_tipo_a_autuar": "Tipo selecionado 'NCV' em razão de não haver indícios suficientes para instauração imediata de inquérito através de NC (Notícia-Crime), conforme orientação nos artigos 123 da IN 270/2023-DG/PF",
                "justificativa_assunto_re": "Não aplicável",
                "justificativa_destinacao": "Conforme competência atribuída pela IN 270/2023-DG/PF, Art. 483, inciso I-c "
            }
        }

#path_pdfs_Teste = r'C:\Users\edson.eab\Downloads\Testes_PDFs_to_gpt'
#name_pdf = '08500-012835-2024_69'

def analise_pdf_by_analista_pf(prompt1, texto_doc, model=modelos_IA[0], tentativas=3, tipo_requisicao='parsed', componentes_gui=None, callback=None):
    """
    Realiza a análise de um documento PDF utilizando modelos de IA.

    Args:
        prompt1 (list): Lista de prompts iniciais para a análise
        texto_doc (str): Texto extraído do documento a ser analisado
        model (str, optional): Modelo de IA a ser utilizado. Padrão: primeiro modelo da lista
        tentativas (int, optional): Número de tentativas em caso de falha. Padrão: 3
        tipo_requisicao (str, optional): Tipo de requisição ('parsed' ou outro). Padrão: 'parsed'
        componentes_gui (tuple, optional): Componentes da interface gráfica
        callback (function, optional): Função de callback para retorno dos resultados

    Returns:
        None

    A função realiza as seguintes operações:
        1. Configura o cliente da API OpenAI
        2. Realiza a requisição ao modelo de IA
        3. Processa a resposta e ajusta os dados conforme necessário
        4. Registra o uso da API em arquivo CSV
        5. Executa callback com os resultados (se fornecido)
    """
    if componentes_gui:
        page, alert_container, banner_alerta = componentes_gui
        def print_alerta(txt):
            print(txt)
            banner_alerta(page, alert_container, txt) 
            
        def print_info(txt):
            print(txt)
            banner_alerta(page, alert_container, txt, info_positiva=True)      
    else:
        def print_alerta(txt):
            return print(txt)
        def print_info(txt):
            return print(txt)
        
    """
    Função para analisar um PDF e obter resposta de um modelo GPT.

    :param arq_pdf: Nome do arquivo PDF (sem extensão)
    :param client: Cliente da API GPT
    :param prompt1: Lista de prompts para iniciar a interação
    :param path_pdf: Caminho onde o PDF está localizado (opcional)
    :return: None
    """  
    client = OpenAI(api_key=keyring.get_password('gpt_api_key', '-'))
    completion = None  
    try:

        if model in ["gpt-4o-mini-2024-07-18", "gpt-4o-2024-08-06"] and tipo_requisicao=='parsed':
            prompt = prompt1.copy()
            prompt.append({"role": "user", "content": texto_doc})
            for tentativa in range(tentativas):
                try:
                    startTime = aux.time()
                    completion = client.beta.chat.completions.parse( 
                        model=model,
                        messages=prompt,
                        response_format=DocumentoAnalise 
                    )
                    endTime = aux.time()
                    break
                except Exception as e:
                    print_alerta(f"Erro ao tentar resposta: {e}. Tentativa {tentativa + 1} de {tentativas}.")
                    aux.sleep(1)
            else:
                raise RuntimeError(f"Falha persistente após {tentativas} tentativas.")
            resposta_estruturada = completion.choices[0].message.parsed
        else:
            prompt = prompt1.copy() + prompt2.copy()
            prompt.append({"role": "user", "content": texto_doc})
            for tentativa in range(tentativas):
                try:
                    startTime = aux.time()
                    completion = client.chat.completions.create( 
                        model=model,
                        messages=prompt
                    )
                    endTime = aux.time()
                    break
                except Exception as e:
                    print_alerta(f"Erro ao gerar completions: {e}. Tentativa {tentativa + 1} de {tentativas}.")
                    aux.sleep(1)
            else:
                raise RuntimeError(f"Falha ao processar linha após {tentativas} tentativas.")
            resposta_estruturada = completion.choices[0].message.content

        bilhetagem = pricing[model]['in-1k'] * (completion.usage.prompt_tokens/1000) + pricing[model]['out-1k'] * (completion.usage.completion_tokens/1000)
        
        tempo_de_respostas = f'Tempo de reposta da IA: {round((endTime - startTime), 2)}s '
        tokens_consumidos = f'Tokens consumidos: {completion.usage.prompt_tokens}+{completion.usage.completion_tokens} = {aux.convert_float_to_milhar(completion.usage.total_tokens)}  ({aux.convert_moeda(bilhetagem)})'
        print(tempo_de_respostas, tokens_consumidos)
        print(f"Modelo utilizado: {model}")
        print('\n')
        save_usage_to_csv(completion)
        #resposta = completion.choices[0].message.content
        if type(resposta_estruturada) != DocumentoAnalise:
            resposta_estruturada = re.search(r'(\{.*?\})', resposta_estruturada, re.DOTALL)[0]
            resposta_estruturada = json.loads(resposta_estruturada)
            resposta_estruturada = DocumentoAnalise(**resposta_estruturada)
        #reposta_in_html = aux.gerar_html_documento(resposta_estruturada)
        #visualizar_html(reposta_in_html)
        
    except Exception as e:
        print_alerta(f"Erro durante a análise do PDF: {e}")
            
    if type(resposta_estruturada) != DocumentoAnalise:
        print(resposta_estruturada)
        raise AssertionError(' Retorno não é do tipo DocumentoAnalise !! ')
    
    for k in resposta_estruturada.__dict__: print(k, f" =={getattr(resposta_estruturada, k)}== ")
    print('\n')

    def atualizar_tipo_a_autuar(resposta_estruturada):
        """Atualiza o tipo a autuar para 'RDF' e zera a justificativa."""
        if "RDF" not in resposta_estruturada.tipo_a_autuar:
            resposta_estruturada.tipo_a_autuar = "RDF - Registro de Fato"
            resposta_estruturada.justificativa_tipo_a_autuar = "Local do fato fora desta circunscrição."

    # Converte a UF para upper e o município para lower uma vez:
    resposta_estruturada.uf_fato = resposta_estruturada.uf_fato.upper().strip()
    resposta_estruturada.uf_origem = resposta_estruturada.uf_origem.upper().strip()
    if not resposta_estruturada.assunto_re:
        resposta_estruturada.assunto_re = "Não aplicável"

    if resposta_estruturada.tipo_a_autuar not in tipo_a_autuar:
        tipo = [item for item in tipo_a_autuar if item.startswith(f"{resposta_estruturada.tipo_a_autuar} - ")]
        if tipo:
            resposta_estruturada.tipo_a_autuar = tipo[0]
    
    delegacia_atual, justificativa_destinacao_atual = set_delegacia_destino(uf_fato, municipio_fato, delegacia_atual, justificativa_destinacao_atual)

    if resposta_estruturada.orgao_origem not in origens_doc:
        tp_result_semelhante = fzw_process.extractOne(resposta_estruturada.orgao_origem, origens_doc)
        opção_selecionada, score = tp_result_semelhante
        if score > 85:
            resposta_estruturada.orgao_origem = opção_selecionada
            
    if callback:
        numeros_consumidos = [tempo_de_respostas, tokens_consumidos]
        callback(resposta_estruturada, numeros_consumidos)
        
    return None
    if not completion: return
    answer = completion.choices[0].message.content
    while True:
        question = []
        while not question:
            while True:
                linha = input('[blue bold]Interação Extraordinária: \t')
                if linha == "":  # Se o usuário pressionar 'Enter' em uma linha vazia
                    break
                question.append(linha)
            question = "\n".join(question)
        if question.lower().strip() in ['x', 'sair', 'encerrar', 'exit']:
            break
        prompt = prompt + [{"role": "assistant", "content": answer}] + [{"role": "user", "content": question}]
        completion = client.chat.completions.create(
            model = model,
            messages = prompt
            )
        answer = completion.choices[0].message.content
        print('\n')
        print(f'[green bold]Assistente GPT:[/] {answer}')
        print(f'\nTokens consumidos: {completion.usage.prompt_tokens}+{completion.usage.completion_tokens} = {completion.usage.total_tokens} \n')
    print('\n[red bold]Interação encerrada.\n')
    
def chat_with_gpt(model="gpt-4o-mini"):
    """
    Inicia uma interação conversacional com o modelo GPT.

    Args:
        model (str, optional): Modelo de IA a ser utilizado. Padrão: "gpt-4o-mini"

    A função permite uma interação contínua com o modelo GPT até que o usuário
    digite 'sair', 'encerrar' ou 'exit'. Durante a interação, são exibidos:
        - Respostas do assistente GPT
        - Contagem de tokens consumidos
    """
    client = OpenAI(api_key=keyring.get_password('gpt_api_key', '-'))
    prompt = [{"role": "user", "content": "Olá! Apresente-se, por favor. Ao final de sua apresentação,  informe que para encerrarmos essa interação basta digitar 'SAIR'."}]
    completion = client.chat.completions.create(
        model = model,
        messages = prompt
        )
    while True:
        answer = completion.choices[0].message.content
        print('\n')
        print(f'[green bold]Assistente GPT:[/] {answer}')
        print(f'\nTokens consumidos: {completion.usage.prompt_tokens}+{completion.usage.completion_tokens} = {completion.usage.total_tokens} \n')
        question = []
        while not question:
            while True:
                linha = input('[blue bold]Interação: \t')
                if linha == "":  # Se o usuário pressionar 'Enter' em uma linha vazia
                    break
                question.append(linha)
            question = "\n".join(question)
        if question.lower().strip() in ['x', 'sair', 'encerrar', 'exit']:
            break
        prompt = prompt + [{"role": "assistant", "content": answer}] + [{"role": "user", "content": question}]
        completion = client.chat.completions.create(
            model = model,
            messages = prompt
            )
    print('\n[red bold]Interação encerrada.\n')

def resumir_texto(texto, limite_tokens, model="gpt-4o-mini"):
    """
    Realiza o resumo de um texto para atingir um limite específico de tokens.

    Args:
        texto (str): Texto original a ser resumido
        limite_tokens (int): Número máximo de tokens desejado no resumo
        model (str, optional): Modelo de IA a ser utilizado. Padrão: "gpt-4o-mini"

    Returns:
        tuple: (texto_resumido, [tempo_de_respostas, tokens_consumidos])

    A função:
        1. Salva o texto original em arquivo temporário
        2. Realiza o resumo utilizando o modelo GPT
        3. Salva o texto resumido em arquivo temporário
        4. Retorna o texto resumido e métricas de execução
    """
    startTime = aux.time()
    with open('temp\\texto_a_resumir.txt', "w") as f: f.write(texto)
    client = OpenAI(api_key=keyring.get_password('gpt_api_key', '-'))
    response = client.chat.completions.create(
        model = model,
        messages = [
            {"role": "system", "content": f"Você é um assistente de IA especializado em ajuste de textos para atender a um limite de tokens específico. Sua tarefa é ajustar os textos fornecidos para que eles cheguem o mais próximo possível de {limite_tokens} tokens. Resuma apenas quando necessário, mas priorize alcançar o número exato de tokens solicitado."},
            {"role": "user", "content": f"Faça uma redução/resumo contendo aproximadamente {limite_tokens} sobre o texto abaixo : \n{texto}"}
            ], 
        max_completion_tokens = limite_tokens
        )
    endTime = aux.time()
    tempo_de_respostas = f'Resumo obtido em {round((endTime - startTime), 2)}s.'
    tokens_consumidos = f'Tokens consumidos: {response.usage.prompt_tokens}+{response.usage.completion_tokens} = {response.usage.total_tokens}'
    print(tempo_de_respostas, tokens_consumidos)
    texto_resumido = response.choices[0].message.content
    with open('temp\\texto_resumido.txt', "w") as f: f.write(texto_resumido)
    return texto_resumido, [tempo_de_respostas, tokens_consumidos]

# ======================================================================================================================
# Funções utilitárias:
def open_file(file_path):
    """
    Abre e lê o conteúdo de um arquivo.

    Args:
        file_path (str): Caminho completo do arquivo a ser lido

    Returns:
        str: Conteúdo do arquivo ou mensagem de erro se não for possível ler
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            contents = file.read()
        return contents
    except FileNotFoundError:
        return "File not found."
    except Exception as e:
        return f"Error: {e}"

def read_txt_file(file_path):
    """
    Lê o conteúdo de um arquivo de texto.

    Args:
        file_path (str): Caminho do arquivo de texto

    Returns:
        str: Conteúdo do arquivo
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    return text    

def extract_articles_from_txt(file_path):
    """
    Extrai artigos de um arquivo de texto contendo legislação.

    Args:
        file_path (str): Caminho do arquivo de texto

    Returns:
        list: Lista de tuplas contendo (número do artigo, conteúdo completo)
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    # Expressão regular para capturar "Art. X" e o conteúdo correspondente
    # Ajusta o padrão para garantir captura da última linha que começa com 'Art.'
    pattern = r'^Art\.\s+\d+-?\w?\..*?(?=\nArt\.|\Z)'
    # Usando aux.re.MULTILINE para que o ^ no padrão funcione no início de cada linha
    matches = aux.re.findall(pattern, text, aux.re.DOTALL | aux.re.MULTILINE)
    # Organizar as tuplas de (artigo, conteúdo)
    articles_list = [(match.strip().split()[0] + " " + match.strip().split()[1], match.strip()) for match in matches]
    return articles_list

def prepare_jsonl_data(articles_list, jsonl_file_path):
    """
    Prepara dados no formato JSONL a partir de uma lista de artigos.

    Args:
        articles_list (list): Lista de tuplas contendo (artigo, conteúdo)
        jsonl_file_path (str): Caminho do arquivo JSONL de saída

    Gera um arquivo JSONL onde cada linha contém um objeto com:
        - prompt: Número do artigo
        - completion: Conteúdo completo do artigo
    """
    with open(jsonl_file_path, 'w', encoding='utf-8') as jsonl_file:
        for article, content in articles_list:
            data = {
                "prompt": article,
                "completion": content
            }
            jsonl_file.write(json.dumps(data) + '\n')

def combine_jsonl_files(file_paths, output_path):
    """
    Combina múltiplos arquivos JSONL em um único arquivo.

    Args:
        file_paths (list): Lista de caminhos dos arquivos JSONL de entrada
        output_path (str): Caminho do arquivo JSONL de saída combinado
    """
    with open(output_path, 'w', encoding='utf-8') as outfile:
        for file_path in file_paths:
            with open(file_path, 'r', encoding='utf-8') as infile:
                for line in infile:
                    outfile.write(line)

def convert_prompt_completion_to_chat_format(input_file, output_file, system_instruction, introduction_question):
    """
    Converte dados no formato prompt-completion para o formato de chat.

    Args:
        input_file (str): Caminho do arquivo JSONL de entrada
        output_file (str): Caminho do arquivo JSONL de saída
        system_instruction (str): Instrução do sistema para o formato de chat
        introduction_question (str): Texto introdutório para as perguntas

    Gera um arquivo JSONL onde cada linha contém um objeto com:
        - messages: Lista de mensagens no formato de chat
    """
    with open(input_file, 'r', encoding='utf-8') as infile, open(output_file, 'w', encoding='utf-8') as outfile:
        for line in infile:
            # Carregar o JSON da linha
            data = json.loads(line.strip())
            # Criar o formato de mensagens
            messages = [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": introduction_question+data['prompt']},
                {"role": "assistant", "content": data['completion']}
            ]     
            # Escrever o novo formato no arquivo de saída
            json.dump({"messages": messages}, outfile)
            outfile.write('\n')

def converter_txt_to_json_1(mensagem_system, txt_file, output_jsonl):
    """
    Converte um arquivo de texto com perguntas e respostas para formato JSONL.

    Args:
        mensagem_system (str): Mensagem do sistema para o formato de chat
        txt_file (str): Caminho do arquivo de texto de entrada
        output_jsonl (str): Caminho do arquivo JSONL de saída

    O arquivo de texto deve ter o formato:
        Pergunta: texto da pergunta
        Resposta: texto da resposta
    """
    with open(txt_file, 'r', encoding='utf-8') as arquivo_txt, open(output_jsonl, 'w', encoding='utf-8') as arquivo_jsonl:
        linhas = arquivo_txt.readlines()
        for i in range(0, len(linhas), 2):
            pergunta = linhas[i].strip().replace("Pergunta: ", "")
            resposta = linhas[i + 1].strip().replace("Resposta: ", "")
            estrutura_json = {
                "messages": [
                    {"role": "system", "content": mensagem_system},
                    {"role": "user", "content": pergunta},
                    {"role": "assistant", "content": resposta}
                ]
            }
            arquivo_jsonl.write(json.dumps(estrutura_json) + '\n')

def converter_txt_to_json_2(mensagem_system, txt_file, output_jsonl):
    """
    Converte um arquivo de texto com pares de perguntas/respostas para formato JSONL.

    Args:
        mensagem_system (str): Mensagem do sistema para o formato de chat
        txt_file (str): Caminho do arquivo de texto de entrada
        output_jsonl (str): Caminho do arquivo JSONL de saída

    O arquivo de texto deve conter JSON com estrutura:
        {"Pares": [{"Pergunta": "...", "Resposta": "..."}]}
    """
    with open(txt_file, 'r', encoding='utf-8') as arquivo_txt, open(output_jsonl, 'w', encoding='utf-8') as arquivo_jsonl:
        for linha in arquivo_txt:
            pares = json.loads(linha) # dict
            for par in pares["Pares"]: # for dict in list
                pergunta = par['Pergunta']
                resposta = par['Resposta']
                estrutura_json = {
                    "messages": [
                        {"role": "system", "content": mensagem_system},
                        {"role": "user", "content": pergunta},
                        {"role": "assistant", "content": resposta}
                    ]
                }
                arquivo_jsonl.write(json.dumps(estrutura_json) + '\n')

