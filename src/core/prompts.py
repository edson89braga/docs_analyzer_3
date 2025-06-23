# src/core/prompts.py
"""
Módulo para gerenciar e fornecer os prompts utilizados nas interações com LLMs.
"""

import logging
logger = logging.getLogger(__name__)

from time import perf_counter
start_time = perf_counter()
logger.debug(f"{start_time:.4f}s - Iniciando prompts.py")

from typing import Optional, Dict, List, Type, Union

# Dicts e Listas de referência p/ placeholders:
...

# Prompts do escopo de Análise sobre Notícias-crimes:
...

class SafeFormatter(dict):
    """
    Dicionário customizado para usar com str.format_map.
    Se uma chave (placeholder) não for encontrada, retorna o próprio placeholder
    (ex: '{chave_nao_encontrada}') em vez de levantar um KeyError.
    """
    def __missing__(self, key):
        return f'{{{key}}}'
    
def replace_values_by_lists(dict_prompt, all_lists_dict):
    """
    Substitui placeholders em um prompt usando as listas fornecidas,
    ignorando placeholders que não estão no dicionário (como {input_text}).
    """
    formatter = SafeFormatter(all_lists_dict)
    dict_prompt['content'] = dict_prompt['content'].format_map(formatter)
    return dict_prompt

def get_prompts_for_initial_analysis(all_lists_dict, all_prompts_dict):
    # PROMPTS no Formato List[Dict]:
    PROMPT_UNICO_for_INITIAL_ANALYSIS = ['system_prompt_A0', 'general_instruction_B1_1',
                                        'prompt_C0', 'prompt_D0', 'prompt_format_output_instruction',
                                        'prompt_F0', 'prompt_G1', 'prompt_G2', 'prompt_H1', 
                                        'prompt_I1', 'prompt_I2',
                                        'prompt_J0', 'prompt_K0',
                                        'final_action_L0']

    prompt_inicial_para_cache = ['system_prompt_A0', 'general_instruction_B1_2', 'start_action_B2']

    PROMPTS_SEGMENTADOS_for_INITIAL_ANALYSIS = [
        ['prompt_C1', 'prompt_D1', 'prompt_format_output_instruction', 'prompt_F1', 'prompt_K1'],
        ['prompt_C2', 'prompt_D2', 'prompt_format_output_instruction', 'prompt_F2', 
                                    'prompt_G1', 'prompt_G2', 'prompt_H1',
                                    'prompt_K2'],
        ['prompt_C3', 'prompt_D3', 'prompt_format_output_instruction', 'prompt_F3',
                                    'prompt_I1', 'prompt_J1',
                                    'prompt_K3'],
        ['prompt_C4', 'prompt_D4', 'prompt_format_output_instruction', 'prompt_F4',
                                    'prompt_I2', 'prompt_J2', 
                                    'prompt_K4']
    ]

    PROMPT_UNICO_for_INITIAL_ANALYSIS = [replace_values_by_lists(all_prompts_dict[dict_value], all_lists_dict) 
                                            for dict_value in PROMPT_UNICO_for_INITIAL_ANALYSIS]
    prompt_inicial_para_cache = [replace_values_by_lists(all_prompts_dict[dict_value], all_lists_dict) 
                                    for dict_value in prompt_inicial_para_cache]
    PROMPTS_SEGMENTADOS_for_INITIAL_ANALYSIS = [[replace_values_by_lists(all_prompts_dict[dict_value], all_lists_dict) 
                                                    for dict_value in prompt] for prompt in PROMPTS_SEGMENTADOS_for_INITIAL_ANALYSIS]

    prompts = {
        'PROMPT_UNICO_for_INITIAL_ANALYSIS': PROMPT_UNICO_for_INITIAL_ANALYSIS,
        'prompt_inicial_para_cache': prompt_inicial_para_cache,
        'PROMPTS_SEGMENTADOS_for_INITIAL_ANALYSIS': PROMPTS_SEGMENTADOS_for_INITIAL_ANALYSIS
    }

    #all_prompts_dict = {k: replace_values_by_lists(v, all_lists_dict)  for k, v in all_prompts_dict.items()}
    return prompts, all_prompts_dict

### FORMATOS das saídas estruturadas:
from pydantic import BaseModel, Field 

class formatted_initial_analysis(BaseModel):
    """
    Modelo Pydantic para a análise inicial formatada de um documento.
    Contém campos para diversas informações extraídas e suas justificativas.
    """
    descricao_geral: str
    tipo_documento_origem: str
    orgao_origem: str
    uf_origem: str
    municipio_origem: str
    resumo_fato: str
    uf_fato: str
    municipio_fato: str
    tipo_local: str
    valor_apuracao: float = Field(default=0.0) # Consta resposta padrão 0 se não aplicável
    tipificacao_penal: str
    materia_especial: str = Field(default="Não aplicável")  # Consta resposta padrão se não aplicável
    area_atribuicao: str
    destinacao: str
    tipo_a_autuar: str
    assunto_re: str = Field(default="Não aplicável") # Consta resposta padrão se não aplicável
    pessoas_envolvidas: Optional[List[str]]
    linha_do_tempo: Optional[List[str]]
    observacoes: str = Field(default="")

    justificativa_tipo_documento_origem:str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_orgao_origem:         str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_municipio_uf_origem:  str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_municipio_uf_fato:    str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_tipo_local:           str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_valor_apuracao:       str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_tipificacao_penal:    str = Field(default="Justificativa não fornecida pela IA.") 
    justificativa_materia_especial:     str = Field(default="Justificativa não fornecida pela IA (ou não aplicável).")
    justificativa_area_atribuicao:      str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_destinacao:           str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_tipo_a_autuar:        str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_assunto_re:           str = Field(default="Justificativa não fornecida pela IA (ou não aplicável).")

class formatted_part_1(BaseModel):
    """
    Modelo Pydantic para a primeira parte da análise segmentada, focando na origem do documento.
    """
    tipo_documento_origem: str
    orgao_origem: str
    uf_origem: str
    municipio_origem: str
    observacoes: str = Field(default="")

    justificativa_tipo_documento_origem:str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_orgao_origem:         str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_municipio_uf_origem:  str = Field(default="Justificativa não fornecida pela IA.")
    
class formatted_part_2(BaseModel):
    """
    Modelo Pydantic para a segunda parte da análise segmentada, focando nos fatos documentados.
    """
    descricao_geral: str
    resumo_fato: str
    uf_fato: str
    municipio_fato: str
    tipo_local: str
    valor_apuracao: float = Field(default=0.0) # Consta resposta padrão 0 se não aplicável
    pessoas_envolvidas: Optional[List[str]]
    linha_do_tempo: Optional[List[str]]
    observacoes: str = Field(default="")

    justificativa_municipio_uf_fato:    str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_tipo_local:           str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_valor_apuracao:       str = Field(default="Justificativa não fornecida pela IA.")

class formatted_part_3(BaseModel):
    """
    Modelo Pydantic para a terceira parte da análise segmentada, focando na área temática e destinação.
    """
    tipificacao_penal: str
    materia_especial: str = Field(default="Não aplicável")  # Consta resposta padrão se não aplicável
    area_atribuicao: str
    destinacao: str
    observacoes: str = Field(default="")

    justificativa_tipificacao_penal:    str = Field(default="Justificativa não fornecida pela IA.") 
    justificativa_materia_especial:     str = Field(default="Justificativa não fornecida pela IA (ou não aplicável).")
    justificativa_area_atribuicao:      str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_destinacao:           str = Field(default="Justificativa não fornecida pela IA.")

class formatted_part_4(BaseModel):
    """
    Modelo Pydantic para a quarta parte da análise segmentada, focando no tipo de procedimento a gerar.
    """
    tipo_a_autuar: str
    assunto_re: str = Field(default="Não aplicável") # Consta resposta padrão se não aplicável
    observacoes: str = Field(default="")

    justificativa_tipo_a_autuar:        str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_assunto_re:           str = Field(default="Justificativa não fornecida pela IA (ou não aplicável).")

output_formats = {
    'PROMPT_UNICO_for_INITIAL_ANALYSIS': formatted_initial_analysis,
    'PROMPTS_SEGMENTADOS_for_INITIAL_ANALYSIS': [formatted_part_1, formatted_part_2, formatted_part_3, formatted_part_4]
}

def return_parse_prompt(dados_respostas: List[str]) -> List[Dict[str, str]]:
    """
    Gera um prompt para consolidar respostas segmentadas em um único objeto JSON.

    Args:
        dados_respostas (List[str]): Uma lista de strings, onde cada string representa
                                     a análise de um segmento diferente de um documento.

    Returns:
        List[Dict[str, str]]: Uma lista contendo um dicionário que representa o prompt
                              para o modelo de linguagem, instruindo-o a consolidar
                              as informações em um formato JSON específico.
    """
    return [{
        "role": "user",
        "content":
            "Você receberá uma lista de respostas em texto, cada uma representando a análise de um segmento diferente de um documento. "
            "Sua tarefa é consolidar as informações dessas respostas em um único objeto JSON que siga as chaves correspondentes abaixo:\n\n"
            f"{list(formatted_initial_analysis.__pydantic_fields__.keys())}\n\n"
            "Aqui estão as respostas segmentadas:\n\n"
            "===\n" +
            '\n'.join(f"Segmento {i+1}: {resp}" for i, resp in enumerate(dados_respostas)) +
            "\n===\n\n"
            "Analise o conteúdo de todos os segmentos e preencha os campos do JSON consolidado com as informações apropriadas extraídas deles. "
            "Gere a resposta exatamente no formato JSON solicitado, sem comentários ou explicações adicionais."
    }]

### FUNÇÕES AUXILIARES:
import json
from src.utils import (get_sigla_uf, get_municipios_por_uf_cached, obter_string_normalizada_em_lista, clean_and_convert_to_float, convert_to_list_of_strings)

dict_corregedorias_uf = {
    'AC': 'COR/SR/PF/AC', 
    'AL': 'COR/SR/PF/AL', 
    'AP': 'COR/SR/PF/AP', 
    'AM': 'COR/SR/PF/AM', 
    'BA': 'COR/SR/PF/BA', 
    'CE': 'COR/SR/PF/CE', 
    'DF': 'COR/SR/PF/DF', 
    'ES': 'COR/SR/PF/ES', 
    'GO': 'COR/SR/PF/GO', 
    'MA': 'COR/SR/PF/MA', 
    'MG': 'COR/SR/PF/MG', 
    'MS': 'COR/SR/PF/MS', 
    'MT': 'COR/SR/PF/MT', 
    'PA': 'COR/SR/PF/PA', 
    'PB': 'COR/SR/PF/PB', 
    'PR': 'COR/SR/PF/PR', 
    'PE': 'COR/SR/PF/PE', 
    'PI': 'COR/SR/PF/PI', 
    'RJ': 'COR/SR/PF/RJ', 
    'RN': 'COR/SR/PF/RN', 
    'RS': 'COR/SR/PF/RS', 
    'RO': 'COR/SR/PF/RO', 
    'RR': 'COR/SR/PF/RR', 
    'SC': 'COR/SR/PF/SC', 
    'SE': 'COR/SR/PF/SE', 
    'TO': 'COR/SR/PF/TO', 
}

dict_circunscrições = {
"SR/PF/SP":   ['ARAÇARIGUAMA', 'ARUJÁ', 'BARUERI', 'BIRITIBA MIRIM', 'CAIEIRAS', 'CARAPICUÍBA', 'COTIA', 'DIADEMA', 'EMBU DAS ARTES', 'EMBU-GUAÇU', 'FERRAZ DE VASCONCELOS', 'FRANCISCO MORATO', 'FRANCO DA ROCHA', 'GUARAREMA', 'GUARULHOS', 'ITAPECERICA DA SERRA', 'ITAPEVI', 'ITAQUAQUECETUBA', 'JANDIRA', 'JUQUITIBA', 'MAIRIPORÃ', 'MAUÁ', 'MOGI DAS CRUZES', 'OSASCO', 'PIRAPORA DO BOM JESUS', 'POÁ', 'RIBEIRÃO PIRES', 'RIO GRANDE DA SERRA', 'SALESÓPOLIS', 'SANTA ISABEL', 'SANTANA DE PARNAÍBA', 'SANTO ANDRÉ', 'SÃO BERNARDO DO CAMPO', 'SÃO CAETANO DO SUL', 'SÃO LOURENÇO DA SERRA', 'SÃO PAULO', 'SÃO ROQUE', 'SUZANO', 'TABOÃO DA SERRA', 'VARGEM GRANDE PAULISTA'], 
"DPF/ARU/SP": ["Alto Alegre", "Andradina", "Araçatuba", "Avanhandava", "Barbosa", "Bento de Abreu", "Bilac", "Birigui", "Braúna", "Brejo Alegre", "Buritama", "Castilho", "Clementina", "Coroados", "Dracena", "Gabriel Monteiro", "Gastão Vidigal", "Glicério", "Guaraçaí", "Guararapes", "Ilha Solteira", "Itapura", "Junqueirópolis", "Lavínia", "Lourdes", "Luiziânia", "Mirandópolis", "Monções", "Monte Castelo", "Murutinga do Sul", "Nova Guataporanga", "Nova Independência", "Nova Luzitânia", "Ouro Verde", "Panorama", "Paulicéia", "Penápolis", "Pereira Barreto", "Piacatu", "Rubiácea", "Santa Mercedes", "Santo Antônio do Aracanguá", "Santópolis do Aguapeí", "São João do Pau d'Alho", "Sud Mennucci", "Tupi Paulista", "Turiúba", "Valparaíso", "Zacarias"], 
"DPF/AQA/SP": ["Américo Brasiliense", "Araraquara", "Boa Esperança do Sul", "Borborema", "Brotas", "Cândido Rodrigues", "Descalvado", "Dobrada", "Dourado", "Fernando Prestes", "Gavião Peixoto", "Ibaté", "Ibitinga", "Itirapina", "Matão", "Motuca", "Nova Europa", "Pirassununga", "Porto Ferreira", "Ribeirão Bonito", "Rincão", "Santa Cruz da Conceição", "Santa Ernestina", "Santa Lúcia", "Santa Rita do Passa Quatro", "São Carlos", "Tabatinga", "Tambaú", "Taquaritinga", "Trabiju"], 
"DPF/BRU/SP": ["Agudos", "Anhembi", "Arandu", "Arealva", "Areiópolis", "Avaí", "Avaré", "Balbinos", "Bariri", "Barra Bonita", "Bauru", "Bocaina", "Bofete", "Boracéia", "Borebi", "Botucatu", "Cabrália Paulista", "Cafelândia", "Cerqueira César", "Conchas", "Dois Córregos", "Duartina", "Getulina", "Guaiçara", "Guaimbê", "Guarantã", "Iacanga", "Iaras", "Igaraçu do Tietê", "Itaí", "Itaju", "Itapuí", "Itatinga", "Jaú", "Lençóis Paulista", "Lins", "Lucianópolis", "Macatuba", "Mineiros do Tietê", "Paranapanema", "Pardinho", "Paulistânia", "Pederneiras", "Pirajuí", "Piratininga", "Pongaí", "Porangaba", "Pratânia", "Presidente Alves", "Promissão", "Reginópolis", "Sabino", "São Manuel", "Taquarituba", "Torre de Pedra", "Torrinha", "Ubirajara", "Uru"], 
"DPF/CAS/SP": ["Aguaí", "Águas da Prata", "Águas de Lindóia", "Amparo", "Atibaia", "Bom Jesus dos Perdões", "Bragança Paulista", "Cabreúva", "Caconde", "Cajamar", "Campinas", "Campo Limpo Paulista", "Capivari", "Casa Branca", "Divinolândia", "Elias Fausto", "Espírito Santo do Pinhal", "Holambra", "Hortolândia", "Indaiatuba", "Itapira", "Itatiba", "Itobi", "Itupeva", "Jaguariúna", "Jarinu", "Joanópolis", "Jundiaí", "Lindóia", "Louveira", "Mococa", "Mogi Guaçu", "Mogi Mirim", "Mombuca", "Monte Alegre do Sul", "Monte Mor", "Morungaba", "Nazaré Paulista", "Paulínia", "Pedra Bela", "Pedreira", "Pinhalzinho", "Piracaia", "Rafard", "Santa Cruz das Palmeiras", "Santo Antônio de Posse", "Santo Antônio do Jardim", "São João da Boa Vista", "São José do Rio Pardo", "São Sebastião da Grama", "Serra Negra", "Socorro", "Sumaré", "Tapiratiba", "Tuiuti", "Valinhos", "Vargem", "Vargem Grande do Sul", "Várzea Paulista", "Vinhedo"], 
"DPF/CZO/SP": ["Aparecida", "Arapeí", "Areias", "Bananal", "Cachoeira Paulista", "Canas", "Cruzeiro", "Cunha", "Guaratinguetá", "Lavrinhas", "Lorena", "Piquete", "Potim", "Queluz", "Roseira", "São José do Barreiro", "Silveiras"], 
"DPF/JLS/SP": ["Álvares Florence", "Aparecida d'Oeste", "Aspásia", "Auriflama", "Dirce Reis", "Dolcinópolis", "Estrela d'Oeste", "Fernandópolis", "General Salgado", "Guarani d'Oeste", "Guzolândia", "Indiaporã", "Jales", "Macedônia", "Marinópolis", "Meridiano", "Mesópolis", "Mira Estrela", "Nova Canaã Paulista", "Nova Castilho", "Ouroeste", "Palmeira d'Oeste", "Paranapuã", "Parisi", "Pedranópolis", "Pontalinda", "Populina", "Rubinéia", "Santa Albertina", "Santa Clara d'Oeste", "Santa Fé do Sul", "Santa Rita d'Oeste", "Santa Salete", "Santana da Ponte Pensa", "São Francisco", "São João das Duas Pontes", "São João de Iracema", "Suzanápolis", "Três Fronteiras", "Turmalina", "Urânia", "Valentim Gentil", "Vitória Brasil", "Votuporanga"], 
"DPF/MII/SP": ["Adamantina", "Águas de Santa Bárbara", "Álvaro de Carvalho", "Alvinlândia", "Arco-Íris", "Assis", "Bastos", "Bernardino de Campos", "Borá", "Campos Novos Paulista", "Cândido Mota", "Canitar", "Chavantes", "Cruzália", "Echaporã", "Espírito Santo do Turvo", "Fartura", "Fernão", "Florínea", "Gália", "Garça", "Herculândia", "Iacri", "Ibirarema", "Inúbia Paulista", "Ipaussu", "Júlio Mesquita", "Lucélia", "Lupércio", "Lutécia", "Manduri", "Maracaí", "Marília", "Ocauçu", "Óleo", "Oriente", "Oscar Bressane", "Osvaldo Cruz", "Ourinhos", "Palmital", "Paraguaçu Paulista", "Parapuã", "Pedrinhas Paulista", "Piraju", "Platina", "Pompéia", "Quatá", "Queiroz", "Quintana", "Ribeirão do Sul", "Rinópolis", "Salmourão", "Salto Grande", "Santa Cruz do Rio Pardo", "São Pedro do Turvo", "Sarutaiá", "Taguaí", "Tarumã", "Tejupá", "Timburi", "Tupã", "Vera Cruz"], 
"DPF/PCA/SP": ["Águas de São Pedro", "Americana", "Analândia", "Araras", "Artur Nogueira", "Charqueada", "Conchal", "Cordeirópolis", "Corumbataí", "Cosmópolis", "Engenheiro Coelho", "Estiva Gerbi", "Ipeúna", "Iracemápolis", "Jumirim", "Laranjal Paulista", "Leme", "Limeira", "Nova Odessa", "Pereiras", "Piracicaba", "Rio Claro", "Rio das Pedras", "Saltinho", "Santa Bárbara d'Oeste", "Santa Gertrudes", "Santa Maria da Serra", "São Pedro", "Tietê"], 
"DPF/PDE/SP": ["Alfredo Marcondes", "Álvares Machado", "Anhumas", "Caiabu", "Caiuá", "Emilianópolis", "Estrela do Norte", "Euclides da Cunha Paulista", "Flora Rica", "Flórida Paulista", "Iepê", "Indiana", "Irapuru", "João Ramalho", "Marabá Paulista", "Mariápolis", "Martinópolis", "Mirante do Paranapanema", "Nantes", "Narandiba", "Pacaembu", "Piquerobi", "Pirapozinho", "Pracinha", "Presidente Bernardes", "Presidente Epitácio", "Presidente Prudente", "Presidente Venceslau", "Rancharia", "Regente Feijó", "Ribeirão dos Índios", "Rosana", "Sagres", "Sandovalina", "Santo Anastácio", "Santo Expedito", "Taciba", "Tarabai", "Teodoro Sampaio"], 
"DPF/RPO/SP": ["Altinópolis", "Aramina", "Barretos", "Barrinha", "Batatais", "Bebedouro", "Brodowski", "Buritizal", "Cajuru", "Cássia dos Coqueiros", "Colina", "Colômbia", "Cravinhos", "Cristais Paulista", "Dumont", "Franca", "Guaíra", "Guará", "Guariba", "Guatapará", "Igarapava", "Ipuã", "Itirapuã", "Ituverava", "Jaborandi", "Jaboticabal", "Jardinópolis", "Jeriquara", "Luís Antônio", "Miguelópolis", "Morro Agudo", "Nuporanga", "Orlândia", "Patrocínio Paulista", "Pedregulho", "Pitangueiras", "Pontal", "Pradópolis", "Restinga", "Ribeirão Corrente", "Ribeirão Preto", "Rifaina", "Sales Oliveira", "Santa Cruz da Esperança", "Santa Rosa de Viterbo", "Santo Antônio da Alegria", "São Joaquim da Barra", "São José da Bela Vista", "São Simão", "Serra Azul", "Serrana", "Sertãozinho", "Taiaçu", "Taiúva", "Taquaral", "Terra Roxa", "Viradouro"], 
"DPF/STS/SP": ["Barra do Turvo", "Bertioga", "Cajati", "Cananéia", "Cubatão", "Eldorado", "Guarujá", "Iguape", "Ilha Comprida", "Iporanga", "Itanhaém", "Itariri", "Jacupiranga", "Juquiá", "Miracatu", "Mongaguá", "Pariquera-Açu", "Pedro de Toledo", "Peruíbe", "Praia Grande", "Registro", "Santos", "São Vicente", "Sete Barras"], 
"DPF/SJE/SP": ["Adolfo", "Altair", "Américo de Campos", "Ariranha", "Bady Bassitt", "Bálsamo", "Cajobi", "Cardoso", "Catanduva", "Catiguá", "Cedral", "Cosmorama", "Elisiário", "Embaúba", "Floreal", "Guapiaçu", "Guaraci", "Ibirá", "Icém", "Ipiguá", "Irapuã", "Itajobi", "Itápolis", "Jaci", "José Bonifácio", "Macaubal", "Magda", "Marapoama", "Mendonça", "Mirassol", "Mirassolândia", "Monte Alto", "Monte Aprazível", "Monte Azul Paulista", "Neves Paulista", "Nhandeara", "Nipoã", "Nova Aliança", "Nova Granada", "Novais", "Novo Horizonte", "Olímpia", "Onda Verde", "Orindiúva", "Palestina", "Palmares Paulista", "Paraíso", "Paulo de Faria", "Pindorama", "Pirangi", "Planalto", "Poloni", "Pontes Gestal", "Potirendaba", "Riolândia", "Sales", "Santa Adélia", "São José do Rio Preto", "Sebastianópolis do Sul", "Severínia", "Tabapuã", "Tanabi", "Ubarana", "Uchoa", "União Paulista", "Urupês", "Vista Alegre do Alto"], 
"DPF/SJK/SP": ["Caçapava", "Campos do Jordão", "Igaratá", "Jacareí", "Jambeiro", "Lagoinha", "Monteiro Lobato", "Natividade da Serra", "Paraibuna", "Pindamonhangaba", "Redenção da Serra", "Santa Branca", "Santo Antônio do Pinhal", "São Bento do Sapucaí", "São José dos Campos", "São Luiz do Paraitinga", "Taubaté", "Tremembé"], 
"DPF/SSB/SP": ["Caraguatatuba", "Ilhabela", "São Sebastião", "Ubatuba"], 
"DPF/SOD/SP": ["Alambari", "Alumínio", "Angatuba", "Apiaí", "Araçoiaba da Serra", "Barão de Antonina", "Barra do Chapéu", "Boituva", "Bom Sucesso de Itararé", "Buri", "Campina do Monte Alegre", "Capão Bonito", "Capela do Alto", "Cerquilho", "Cesário Lange", "Coronel Macedo", "Guapiara", "Guareí", "Ibiúna", "Iperó", "Itaberá", "Itaoca", "Itapetininga", "Itapeva", "Itapirapuã Paulista", "Itaporanga", "Itararé", "Itu", "Mairinque", "Nova Campina", "Piedade", "Pilar do Sul", "Porto Feliz", "Quadra", "Ribeira", "Ribeirão Branco", "Ribeirão Grande", "Riversul", "Salto", "Salto de Pirapora", "São Miguel Arcanjo", "Sarapuí", "Sorocaba", "Tapiraí", "Taquarivaí", "Tatuí", "Votorantim"]
}

def try_convert_to_pydantic_format(data: Union[str, BaseModel], pydantic_format: Type[BaseModel]) -> Union[BaseModel, str]:
    """
    Tenta converter os dados de entrada para o formato Pydantic especificado.

    Args:
        data (Union[str, BaseModel]): Os dados a serem convertidos, que podem ser uma string JSON
                                      ou um objeto Pydantic.
        pydantic_format (Type[BaseModel]): O modelo Pydantic para o qual os dados devem ser convertidos.

    Returns:
        Union[BaseModel, str]: O objeto Pydantic convertido se bem-sucedido, ou a string original
                               se a conversão falhar.
    """
    # llm_response_data PODE ser um objeto FormatAnaliseInicial ou uma string
    # Se for string e parece JSON, tenta parsear para FormatAnaliseInicial
    if isinstance(data, str):
        try:
            json_data  = json.loads(data)
            
            if 'valor_apuracao' in json_data and type(json_data['valor_apuracao']) != float:
                raw_valor = json_data['valor_apuracao']
                json_data['valor_apuracao'] = clean_and_convert_to_float(raw_valor)
                logger.debug(f"Valor apuracao original: '{raw_valor}', convertido para float: {json_data['valor_apuracao']}")
            for k in ["pessoas_envolvidas", "linha_do_tempo"]:
                if k in json_data and type(json_data[k]) == str:
                    raw_valor = json_data[k]
                    json_data[k] = convert_to_list_of_strings(raw_valor)

            data = pydantic_format(**json_data )
            logger.debug("Resposta (string) parseada com sucesso para Pydantic_format.")
        except (json.JSONDecodeError, TypeError, Exception) as parse_error: # Exception para Pydantic ValidationError
            logger.warning(f"Resposta é string, mas falhou ao parsear/validar como Pydantic_format: {parse_error}. Usando como texto puro.")
            # Mantém llm_response_data como string para o fallback
    elif isinstance(data, pydantic_format):
        logger.debug("Resposta já é um objeto Pydantic_format.")
    else:
        logger.warning("Resposta não é string nem objeto Pydantic_format!")
    
    return data

def merge_parts_into_model(
    parts: List[BaseModel],
    target_model: Type[BaseModel],
) -> BaseModel:
    """
    Mescla múltiplas partes de modelos Pydantic em um único modelo Pydantic de destino.

    Esta função combina os dados de uma lista de objetos BaseModel em um único dicionário,
    tratando o campo 'observacoes' de forma especial, concatenando-o se presente em várias partes.
    O dicionário resultante é então usado para instanciar o modelo de destino.

    Args:
        parts (List[BaseModel]): Uma lista de objetos BaseModel a serem mesclados.
        target_model (Type[BaseModel]): O tipo do modelo Pydantic de destino.

    Returns:
        BaseModel: Uma instância do `target_model` preenchida com os dados mesclados.
    """
    
    combined_data = {}
    observacoes_coletadas = []
    logger.debug(f"Unificando {len(parts)} partes em Pydantic_target.")
    for part in parts:
        # Verifica se 'observacoes' é um campo definido no modelo
        has_obs = "observacoes" in part.model_fields
        data = part.model_dump(exclude_unset=True, exclude={"observacoes"} if has_obs else {})

        combined_data.update(data)

        # Se existir 'observacoes' e não for None, adiciona à lista
        if has_obs:
            obs = getattr(part, "observacoes", None)
            if obs:
                observacoes_coletadas.append(obs)

    # Concatena observações, se houver
    if observacoes_coletadas:
        combined_data["observacoes"] = "\n".join(observacoes_coletadas)
    else:
        combined_data["observacoes"] = None

    return target_model(**combined_data)

def normalizing_function(resposta_formatada: formatted_initial_analysis) -> formatted_initial_analysis:
    """
    Normaliza os dados de uma resposta formatada, especialmente UFs e municípios.

    Esta função garante que os valores de UF e município estejam em um formato consistente
    e válidos de acordo com as listas de referência.

    Args:
        resposta_formatada (formatted_initial_analysis): A resposta formatada a ser normalizada.

    Returns:
        formatted_initial_analysis: A resposta formatada após a normalização.
    """
    municipios_list = get_municipios_por_uf_cached()

    if not isinstance(resposta_formatada, formatted_initial_analysis):
        resposta_formatada = try_convert_to_pydantic_format(resposta_formatada, formatted_initial_analysis)

    if isinstance(resposta_formatada, formatted_initial_analysis):    
        # Normaliza UFs nos dados recebidos antes de popular a UI
        # Isso garante que os valores iniciais dos dropdowns de UF sejam válidos.
        resposta_formatada.uf_origem = get_sigla_uf(resposta_formatada.uf_origem)
        resposta_formatada.uf_fato = get_sigla_uf(resposta_formatada.uf_fato)
        
        municipios_origem_init = municipios_list.get(resposta_formatada.uf_origem, []) if resposta_formatada.uf_origem else []
        resposta_formatada.municipio_origem = obter_string_normalizada_em_lista(resposta_formatada.municipio_origem, municipios_origem_init)

        municipios_fato_init = municipios_list.get(resposta_formatada.uf_fato, []) if resposta_formatada.uf_fato else []
        resposta_formatada.municipio_fato = obter_string_normalizada_em_lista(resposta_formatada.municipio_fato, municipios_fato_init)
    else:
        logger.warning(f"Resposta fora da formatação esperada: {type(resposta_formatada)}.\nCancelando normalização de dados.")
    
    return resposta_formatada

def review_function(resposta_formatada: formatted_initial_analysis) -> formatted_initial_analysis:
    """
    Revisa os dados de uma resposta formatada, aplicando regras de negócio e ajustes.

    Args:
        resposta_formatada (formatted_initial_analysis): A resposta formatada a ser revisada.

    Returns:
        formatted_initial_analysis: A resposta formatada após a revisão.
    """
    if not isinstance(resposta_formatada, formatted_initial_analysis):
        logger.warning(f"Resposta fora da formatação esperada: {type(resposta_formatada)}.\nCancelando revisão de dados.")
        return resposta_formatada
    
    resposta_formatada.tipo_local = 'Não classificado / Outros' if resposta_formatada.tipo_local == 'Outro' else resposta_formatada.tipo_local
    resposta_formatada.assunto_re = 'Outros' if resposta_formatada.assunto_re == 'Outro' else resposta_formatada.assunto_re
    
    destinacao_alterada = False
    if resposta_formatada.uf_fato != 'SP':
        resposta_formatada.destinacao = dict_corregedorias_uf.get(resposta_formatada.uf_fato)
        destinacao_alterada = True
    elif resposta_formatada.municipio_fato not in dict_circunscrições["SR/PF/SP"]:
        # Conferido nomes com MUNICIPIOS_POR_UF["SP"]; os municípios da SR tiveram upper ativado.
        from unidecode import unidecode
        for dpf, municipios in dict_circunscrições.items():
            municipios = [unidecode(m).lower() for m in municipios]
            if unidecode(resposta_formatada.municipio_fato).lower() in municipios:
                resposta_formatada.destinacao = dpf
                destinacao_alterada = True
                break
    
    if destinacao_alterada:
        resposta_formatada.tipo_a_autuar = 'RDF - Registro de Fato'
        resposta_formatada.justificativa_destinacao += "\nDestinação apontada na função revisora, conforme unidade da PF na UF/Município do fato."
        resposta_formatada.justificativa_tipo_a_autuar += "\nTipo a autuar 'RDF' apontado na função revisora, em razão da autonomia de análise pela unidade destinatária."
            
    return resposta_formatada

'''
Grupos de prompt:

# quanto à origem:
2. TIPO DE DOCUMENTO DE ORIGEM
3. ÓRGÃO DE ORIGEM
4.1 UF DE ORIGEM
4.2 MUNICÍPIO DE ORIGEM

# quanto ao(s) fato(s) documentado(s):
1. DESCRIÇÃO GERAL
5. RESUMO DO FATO
6.1 UF DO FATO
6.2 MUNICÍPIO DO FATO
7. TIPO DE LOCAL
8. VALOR DE APURAÇÃO
14. PESSOAS ENVOLVIDAS
15. LINHA DO TEMPO
16. OBSERVAÇÕES

# quanto à área temática e destinação: 
9. TIPIFICAÇÃO PENAL
10. ÁREA DE ATRIBUIÇÃO
13. DESTINAÇÃO
13. MATÉRIA DE TRATAMENTO ESPECIAL

# quanto ao tipo de procedimento a gerar:
11. TIPO A AUTUAR
12. ASSUNTO DO RE

'''

execution_time = perf_counter() - start_time
logger.debug(f"Carregado PROMPTS em {execution_time:.4f}s")
