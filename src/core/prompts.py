# src/core/prompts.py
"""
Módulo para gerenciar e fornecer os prompts utilizados nas interações com LLMs.
"""
from typing import Optional, Dict, List

from pydantic import BaseModel, Field 
class FormatAnaliseInicial(BaseModel):
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
    tipificacao_penal: Optional[str] 
    tipo_a_autuar: str 
    assunto_re: Optional[str] 
    destinacao: str 
    pessoas_envolvidas: Optional[List[str]]
    linha_do_tempo: Optional[List[str]] 
    observacoes: Optional[str] 

    justificativa_tipo_documento_origem:str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_orgao_origem:         str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_municipio_uf_origem:  str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_tipo_local:           str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_municipio_uf_fato:    str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_valor_apuracao:       str = Field(default="Justificativa não fornecida pela IA (ou não aplicável).")
    justificativa_area_atribuicao:      str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_tipificacao_penal:    str = Field(default="Justificativa não fornecida pela IA.") 
    justificativa_tipo_a_autuar:        str = Field(default="Justificativa não fornecida pela IA.")
    justificativa_assunto_re:           str = Field(default="Justificativa não fornecida pela IA (ou não aplicável).")
    justificativa_destinacao:           str = Field(default="Justificativa não fornecida pela IA.")

# Conversão para modelo em esquema JSON, se necessário:
schema = FormatAnaliseInicial.model_json_schema()
response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "FormatAnaliseInicial",
        "schema": schema,
        "strict": False
    }
}

# Dicts e Listas de referência p/ placeholders:

tipos_doc = ['Boletim de Ocorrência (externo)', 'E-mail', 'Inquérito Policial - Polícia Civil', 'IPJ - Informação de Polícia Judiciária', 'Ofício', 'Relatório', 'Requisição - Judicial', 'Requisição - Ministério Público', 'RIF - Relatório de Inteligência Financeira', 'Outro']
origens_doc = ['MPF - Ministério Público Federal', 'JF - Justiça Federal', 'CEF - Caixa Econômica Federal', 'PC - Polícia Civil', 'PF - Polícia Federal', 'EBCT - Empresa Brasileira de Correios e Telégrafos', 'MPT - Ministério Público do Trabalho', 'Justiça Eleitoral', 'Justiça Estadual', 'Pessoa Jurídica', 'Pessoa Física', 'Particular', 'IBGE - Instituto Brasileiro de Geografia e Estatística', 'Ministério Público Estadual', 'Ministério da Justiça', 'Ministério do Trabalho e Emprego', 'PRF - Polícia Rodoviária Federal', 'ANATEL - Agência Nacional de Telecomunicações', 'INSS', 'Tribunal Regional do Trabalho', 'RFB - Receita Federal do Brasil', 'AGU - Advocacia-Geral da União', 'OUTRO']
tipos_locais = ['Transportadora de Cargas', 'Via pública urbana/Rua/Avenida/Calçada/Passeio', 'Internet', 'Aeroporto', 'Banco/Agência Bancária/Cooperativa de Crédito', 'Agência INSS', 'Prédio Público / Edifício Público', 'Tribunal/Poder Judiciário', 'Estabelecimento comercial (outro)/Loja/Escritório', 'Faculdade/Universidade', 'Lotérica/Correios/Correspondente Bancário/Banco Postal', 'Residência/casa particular/ apartamento particular', 'Rodovia/Estrada', 'Porto/Cais/Doca', 'Hospital/consultório/clínica/laboratório/farmácia/posto de saúde', 'Mar/Oceano', 'Transporte público/Taxi/Aplicativo', 'Hotel/Motel/Pensão/Camping', 'Supermercado/Mercado/Mercearia', 'Terra Indígena', 'Espaço aéreo', 'Não classificado / Outros']
areas_de_atribuição = ['Crimes Fazendários', 'Crimes Previdenciários', 'Crimes Ambientais, contra o Patrimônio Histórico e Cultural e Povos Originários', 'Crimes contra o patrimônio', 'Tráfico de drogas', 'Crimes Financeiros', 'Desvio de Recursos Públicos', 'Crimes contra Direitos Humanos', 'Crimes eleitorais e contra o Estado Democrático de Direito', 'Assuntos Internos (investiga servidor da PF)', 'Terrorismo', 'Tramita em Tribunais Superiores', 'Tráfico de armas e crimes relacionados à Lei 10.826/03', 'Crimes Cibernéticos relacionados ao abuso sexual infantojuvenil', 'Fraudes bancárias eletrônicas', 'Lavagem de Dinheiro (crime autônomo)', 'Crimes de alta tecnologia', 'Crimes Cibernéticos de Ódio']
tipo_a_autuar = ['NC - Notícia-Crime', 'NCV - Notícia-Crime em Verificação', 'RE - Registro Especial', 'RDF - Registro de Fato']
assuntos_re = ['Requisição de diligência (procedimento externo)', 'Cooperação Jurídica Internacional', 'Cumprimento de exequatur', 'Recuperação de ativos', 'Outros', 'Não aplicável']
tipos_envolvidos = ['Apresentante', 'Condutor', 'Conduzido', 'Declarante', 'Detentor', 'Informante', 'Investigado', 'Noticiante', 'Preso por Mandado', 'Procurado em aberto', 'Testemunha', 'Vítima']
lista_delegacias_especializadas = ['DELECIBER/SR/PF/SP', 'DELEPAT/SR/PF/SP', 'DELEPREV/SR/PF/SP', 'DRE/SR/PF/SP', 'DELEFAZ/SR/PF/SP', 'DELINST/SR/PF/SP', 'DMA/SR/PF/SP', 'DELECOR/SR/PF/SP', 'FICCO/SR/PF/SP', 'NCI/SR/PF/SP', 'SIP/SR/PF/SP', 'NUAIN/SR/PF/SP']
lista_delegacias_interior = ['DPF/ARU/SP', 'DPF/AQA/SP', 'DPF/BRU/SP', 'DPF/CAS/SP', 'DPF/CZO/SP', 'DPF/JLS/SP', 'DPF/MII/SP', 'DPF/PCA/SP', 'DPF/PDE/SP', 'DPF/RPO/SP', 'DPF/STS/SP', 'DPF/SJE/SP', 'DPF/SJK/SP', 'DPF/SSB/SP', 'DPF/SOD/SP']
lista_corregedorias = ['COR/SR/PF/AC', 'COR/SR/PF/AL', 'COR/SR/PF/AP', 'COR/SR/PF/AM', 'COR/SR/PF/BA', 'COR/SR/PF/CE', 'COR/SR/PF/DF', 'COR/SR/PF/ES', 'COR/SR/PF/GO', 'COR/SR/PF/MA', 'COR/SR/PF/MG', 'COR/SR/PF/MS', 'COR/SR/PF/MT', 'COR/SR/PF/PA', 'COR/SR/PF/PB', 'COR/SR/PF/PR', 'COR/SR/PF/PE', 'COR/SR/PF/PI', 'COR/SR/PF/RJ', 'COR/SR/PF/RN', 'COR/SR/PF/RS', 'COR/SR/PF/RO', 'COR/SR/PF/RR', 'COR/SR/PF/SC', 'COR/SR/PF/SE', 'COR/SR/PF/TO']

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
"SR/PF/SP":   ["Araçariguama", "Arujá", "Barueri", "Biritiba Mirim", "Caieiras", "Carapicuíba", "Cotia", "Diadema", "Embu das Artes", "Embu-Guaçu", "Ferraz de Vasconcelos", "Francisco Morato", "Franco da Rocha", "Guararema", "Guarulhos", "Itapecerica da Serra", "Itapevi", "Itaquaquecetuba", "Jandira", "Juquitiba", "Mairiporã", "Mauá", "Mogi das Cruzes", "Osasco", "Pirapora do Bom Jesus", "Poá", "Ribeirão Pires", "Rio Grande da Serra", "Salesópolis", "Santa Isabel", "Santana de Parnaíba", "Santo André", "São Bernardo do Campo", "São Caetano do Sul", "São Lourenço da Serra", "São Paulo", "São Roque", "Suzano", "Taboão da Serra", "Vargem Grande Paulista"], 
"DPF/ARU/SP": ["Alto Alegre", "Andradina", "Araçatuba", "Avanhandava", "Barbosa", "Bento de Abreu", "Bilac", "Birigui", "Braúna", "Brejo Alegre", "Buritama", "Castilho", "Clementina", "Coroados", "Dracena", "Gabriel Monteiro", "Gastão Vidigal", "Glicério", "Guaraçaí", "Guararapes", "Ilha Solteira", "Itapura", "Junqueirópolis", "Lavínia", "Lourdes", "Luiziânia", "Mirandópolis", "Monções", "Monte Castelo", "Murutinga do Sul", "Nova Guataporanga", "Nova Independência", "Nova Luzitânia", "Ouro Verde", "Panorama", "Paulicéia", "Penápolis", "Pereira Barreto", "Piacatu", "Rubiácea", "Santa Mercedes", "Santo Antônio do Aracanguá", "Santópolis do Aguapeí", "São João do Pau d'Alho", "Sud Mennucci", "Tupi Paulista", "Turiúba", "Valparaíso", "Zacarias"], 
"DPF/AQA/SP": ["Américo Brasiliense", "Araraquara", "Boa Esperança do Sul", "Borborema", "Brotas", "Cândido Rodrigues", "Descalvado", "Dobrada", "Dourado", "Fernando Prestes", "Gavião Peixoto", "Ibaté", "Ibitinga", "Itirapina", "Matão", "Motuca", "Nova Europa", "Pirassununga", "Porto Ferreira", "Ribeirão Bonito", "Rincão", "Santa Cruz da Conceição", "Santa Ernestina", "Santa Lúcia", "Santa Rita do Passa Quatro", "São Carlos", "Tabatinga", "Tambaú", "Taquaritinga", "Trabiju"], 
"DPF/BRU/SP": ["Agudos", "Anhembi", "Arandu", "Arealva", "Areiópolis", "Avaí", "Avaré", "Balbinos", "Bariri", "Barra Bonita", "Bauru", "Bocaina", "Bofete", "Boracéia", "Borebi", "Botucatu", "Cabrália Paulista", "Cafelândia", "Cerqueira César", "Conchas", "Dois Córregos", "Duartina", "Getulina", "Guaiçara", "Guaimbê", "Guarantã", "Iacanga", "Iaras", "Igaraçu do Tietê", "Itaí", "Itaju", "Itapuí", "Itatinga", "Jaú", "Lençóis Paulista", "Lins", "Lucianópolis", "Macatuba", "Mineiros do Tietê", "Paranapanema", "Pardinho", "Paulistânia", "Pederneiras", "Pirajuí", "Piratininga", "Pongaí", "Porangaba", "Pratânia", "Presidente Alves", "Promissão", "Reginópolis", "Sabino", "São Manuel", "Taquarituba", "Torre de Pedra", "Torrinha", "Ubirajara", "Uru"], 
"DPF/CAS/SP": ["Aguaí", "Águas da Prata", "Águas de Lindóia", "Amparo", "Atibaia", "Bom Jesus dos Perdões", "Bragança Paulista", "Cabreúva", "Caconde", "Cajamar", "Campinas", "Campo Limpo Paulista", "Capivari", "Casa Branca", "Divinolândia", "Elias Fausto", "Espírito Santo do Pinhal", "Holambra", "Hortolândia", "Indaiatuba", "Itapira", "Itatiba", "Itobi", "Itupeva", "Jaguariúna", "Jarinu", "Joanópolis", "Jundiaí", "Lindóia", "Louveira", "Mococa", "Mogi Guaçu", "Mogi Mirim", "Mombuca", "Monte Alegre do Sul", "Monte Mor", "Morungaba", "Nazaré Paulista", "Paulínia", "Pedra Bela", "Pedreira", "Pinhalzinho", "Piracaia", "Rafard", "Santa Cruz das Palmeiras", "Santo Antônio de Posse", "Santo Antônio do Jardim", "São João da Boa Vista", "São José do Rio Pardo", "São Sebastião da Grama", "Serra Negra", "Socorro", "Sumaré", "Tapiratiba", "Tuiuti", "Valinhos", "Vargem", "Vargem Grande do Sul", "Várzea Paulista", "Vinhedo"], 
"DPF/CZO/SP": ["Aparecida", "Arapeí", "Areias", "Bananal", "Cachoeira Paulista", "Canas", "Cruzeiro", "Cunha", "Guaratinguetá", "Lavrinhas", "Lorena", "Piquete", "Potim", "Queluz", "Roseira", "São José do Barreiro", "Silveiras"], 
"DPF/JLS/SP": ["Álvares Florence", "Aparecida d'Oeste", "Aspásia", "Auriflama", "Dirce Reis", "Dolcinópolis", "Estrela d'Oeste", "Fernandópolis", "General Salgado", "Guarani d'Oeste", "Guzolândia", "Indiaporã", "Jales", "Macedônia", "Marinópolis", "Meridiano", "Mesópolis", "Mira Estrela", "Nova Canaã Paulista", "Nova Castilho", "Ouroeste", "Palmeira d'Oeste", "Paranapuã", "Parisi", "Pedranópolis", "Pontalinda", "Populina", "Rubinéia", "Santa Albertina", "Santa Clara d'Oeste", "Santa Fé do Sul", "Santa Rita d'Oeste", "Santa Salete", "Santana da Ponte Pensa", "São Francisco", "São João das Duas Pontes", "São João de Iracema", "Suzanápolis", "Três Fronteiras", "Turmalina", "Urânia", "Valentim Gentil", "Vitória Brasil", "Votuporanga"], 
"DPF/MII/SP": ["Adamantina", "Águas de Santa Bárbara", "Álvaro de Carvalho", "Alvinlândia", "Arco-Íris", "Assis", "Bastos", "Bernardino de Campos", "Borá", "Campos Novos Paulista", "Cândido Mota", "Canitar", "Chavantes", "Cruzália", "Echaporã", "Espírito Santo do Turvo", "Fartura", "Fernão", "Florínea", "Gália", "Garça", "Herculândia", "Iacri", "Ibirarema", "Inúbia Paulista", "Ipaussu", "Júlio Mesquita", "Lucélia", "Lupércio", "Lutécia", "Manduri", "Maracaí", "Marília", "Ocauçu", "Óleo", "Feijão", "Oriente", "Oscar Bressane", "Osvaldo Cruz", "Ourinhos", "Palmital", "Paraguaçu Paulista", "estação espacial", "Parapuã", "Pedrinhas Paulista", "Piraju", "Platina", "Pompéia", "Quatá", "Queiroz", "Quintana", "Ribeirão do Sul", "Rinópolis", "Salmourão", "Salto Grande", "Santa Cruz do Rio Pardo", "São Pedro do Turvo", "Sarutaiá", "Taguaí", "Tarumã", "Tejupá", "Timburi", "Tupã", "Vera Cruz"], 
"DPF/PCA/SP": ["Águas de São Pedro", "Americana", "Analândia", "Araras", "Artur Nogueira", "Charqueada", "Conchal", "Cordeirópolis", "Corumbataí", "Cosmópolis", "Engenheiro Coelho", "Estiva Gerbi", "Ipeúna", "Iracemápolis", "Jumirim", "Laranjal Paulista", "Leme", "Limeira", "Nova Odessa", "Pereiras", "Piracicaba", "Rio Claro", "Rio das Pedras", "Saltinho", "Santa Bárbara d'Oeste", "Santa Gertrudes", "Santa Maria da Serra", "São Pedro", "Tietê"], 
"DPF/PDE/SP": ["Alfredo Marcondes", "Álvares Machado", "Anhumas", "Caiabu", "Caiuá", "Emilianópolis", "Estrela do Norte", "Euclides da Cunha Paulista", "Flora Rica", "Flórida Paulista", "Iepê", "Indiana", "Irapuru", "João Ramalho", "Marabá Paulista", "Mariápolis", "Martinópolis", "Mirante do Paranapanema", "Nantes", "Narandiba", "Pacaembu", "Piquerobi", "Pirapozinho", "Pracinha", "Presidente Bernardes", "Presidente Epitácio", "Presidente Prudente", "Presidente Venceslau", "Rancharia", "Regente Feijó", "Ribeirão dos Índios", "Rosana", "Sagres", "Sandovalina", "Santo Anastácio", "Santo Expedito", "Taciba", "Tarabai", "Teodoro Sampaio"], 
"DPF/RPO/SP": ["Altinópolis", "Aramina", "Barretos", "Barrinha", "Batatais", "Bebedouro", "Brodowski", "Buritizal", "Cajuru", "Cássia dos Coqueiros", "Colina", "Colômbia", "Cravinhos", "Cristais Paulista", "Dumont", "Franca", "Guaíra", "Guará", "Guariba", "Guatapará", "Igarapava", "Ipuã", "Itirapuã", "Ituverava", "Jaborandi", "Jaboticabal", "Jardinópolis", "Jeriquara", "Luís Antônio", "Miguelópolis", "Morro Agudo", "Nuporanga", "Orlândia", "Patrocínio Paulista", "Pedregulho", "Pitangueiras", "Pontal", "Pradópolis", "Restinga", "Ribeirão Corrente", "Ribeirão Preto", "Rifaina", "Sales Oliveira", "Santa Cruz da Esperança", "Santa Rosa de Viterbo", "Santo Antônio da Alegria", "São Joaquim da Barra", "São José da Bela Vista", "São Simão", "Serra Azul", "Serrana", "Sertãozinho", "Taiaçu", "Taiúva", "Taquaral", "Terra Roxa", "Viradouro"], 
"DPF/STS/SP": ["Barra do Turvo", "Bertioga", "Cajati", "Cananéia", "Cubatão", "Eldorado", "Guarujá", "Iguape", "Ilha Comprida", "Iporanga", "Itanhaém", "Itariri", "Jacupiranga", "Juquiá", "Miracatu", "Mongaguá", "Pariquera-Açu", "Pedro de Toledo", "Peruíbe", "Praia Grande", "Registro", "Santos", "São Vicente", "Sete Barras"], 
"DPF/SJE/SP": ["Adolfo", "Altair", "Américo de Campos", "Ariranha", "Bady Bassitt", "Bálsamo", "Cajobi", "Cardoso", "Catanduva", "Catiguá", "Cedral", "Cosmorama", "Elisiário", "Embaúba", "Floreal", "Guapiaçu", "Guaraci", "Ibirá", "Icém", "Ipiguá", "Irapuã", "Itajobi", "Itápolis", "Jaci", "José Bonifácio", "Macaubal", "Magda", "Marapoama", "Mendonça", "Mirassol", "Mirassolândia", "Monte Alto", "Monte Aprazível", "Monte Azul Paulista", "Neves Paulista", "Nhandeara", "Nipoã", "Nova Aliança", "Nova Granada", "Novais", "Novo Horizonte", "Olímpia", "Onda Verde", "Orindiúva", "Palestina", "Palmares Paulista", "Paraíso", "Paulo de Faria", "Pindorama", "Pirangi", "Planalto", "Poloni", "Pontes Gestal", "Potirendaba", "Riolândia", "Sales", "Santa Adélia", "São José do Rio Preto", "Sebastianópolis do Sul", "Severínia", "Tabapuã", "Tanabi", "Ubarana", "Uchoa", "União Paulista", "Urupês", "Vista Alegre do Alto"], 
"DPF/SJK/SP": ["Caçapava", "Campos do Jordão", "Igaratá", "Jacareí", "Jambeiro", "Lagoinha", "Monteiro Lobato", "Natividade da Serra", "Paraibuna", "Pindamonhangaba", "Redenção da Serra", "Santa Branca", "Santo Antônio do Pinhal", "São Bento do Sapucaí", "São José dos Campos", "São Luiz do Paraitinga", "Taubaté", "Tremembé"], 
"DPF/SSB/SP": ["Caraguatatuba", "Ilhabela", "São Sebastião", "Ubatuba"], 
"DPF/SOD/SP": ["Alambari", "Alumínio", "Angatuba", "Apiaí", "Araçoiaba da Serra", "Barão de Antonina", "Barra do Chapéu", "Boituva", "Bom Sucesso de Itararé", "Buri", "Campina do Monte Alegre", "Capão Bonito", "Capela do Alto", "Cerquilho", "Cesário Lange", "Coronel Macedo", "Guapiara", "Guareí", "Ibiúna", "Iperó", "Itaberá", "Itaoca", "Itapetininga", "Itapeva", "Itapirapuã Paulista", "Itaporanga", "Itararé", "Itu", "Mairinque", "Nova Campina", "Piedade", "Pilar do Sul", "Porto Feliz", "Quadra", "Ribeira", "Ribeirão Branco", "Ribeirão Grande", "Riversul", "Salto", "Salto de Pirapora", "São Miguel Arcanjo", "Sarapuí", "Sorocaba", "Tapiraí", "Taquarivaí", "Tatuí", "Votorantim"]
}

exemplos_resumos = "\
'Trata-se da Notícia de Fato (NF) nº 1.34.001.099999/2023-00, autuada a partir da Representação Fiscal para Fins Penais nº 0800100-999999/2023, encaminhada pela Receita Federal do Brasil, noticiando que a pessoa jurídica XYZ LTDA., com sede no município de São Paulo/SP, foi flagrada comercializando mercadorias importadas irregularmente. O fato ocorreu entre os meses de janeiro e março de 2023, quando foram apreendidos diversos lotes de produtos eletrônicos de origem chinesa sem a devida documentação de importação legal, em São Paulo/SP. O valor estimado da mercadoria é de aproximadamente R$ 2.000.000,00. Entre os envolvidos estão o sócio-administrador João da Silva, CPF nº 123.456.789-00, responsável pela gestão da empresa, e a funcionária Maria de Souza, que assinou as notas fiscais de transporte. A investigação preliminar aponta que os produtos foram distribuídos em redes de varejo na capital paulista.', \
'Trata-se de investigação decorrente da Notícia de Fato nº 1.23.456.789/2024-01, instaurada a partir de denúncia anônima, que relata possível crime de fraude fiscal cometido pela empresa ABC Comércio Ltda., localizada no município de Belo Horizonte/MG. O fato ocorreu entre os meses de janeiro e março de 2024, quando a empresa teria utilizado notas fiscais fraudulentas para sonegar aproximadamente R$ 500.000,00 em impostos federais. Os principais envolvidos incluem João da Silva, proprietário da empresa, e Carlos Pereira, contador, ambos investigados pela suposta prática de crimes contra a ordem tributária. No local da sede da empresa, foram apreendidos documentos fiscais e contábeis que servirão como provas no inquérito. A investigação segue com o objetivo de apurar o montante total da fraude e identificar outros eventuais participantes.', \
'Trata-se de uma denúncia de fraude fiscal, recebida da Receita Federal, que apura a sonegação de impostos ocorrida entre janeiro e dezembro de 2023, na cidade de São Paulo, SP. Os envolvidos são João Silva (CPF: 123.456.789-00), identificado como o autor da fraude, e Maria Oliveira (CPF: 987.654.321-00), vítima do esquema. O fato foi encaminhado pela Receita Federal em 15 de setembro de 2024. As evidências incluem documentos fiscais adulterados e registros bancários suspeitos. O prejuízo estimado é de R$ 500.000,00. O fato foi formalizado por meio da Notícia de Fato nº 1.34.002.000111/2024-92, encaminhada pela Receita Federal do Brasil em 05/04/2024, sendo a investigação atualmente conduzida no município de São Paulo/SP.', \
'Trata-se do Ofício nº 3142/2024, encaminhado pelo Ministério Público Federal, que acompanha a Notícia de Fato nº 1.34.001.001985/2024-22, instaurada para apuração de possível infração ao artigo 16 da Lei 10.826/2003 (Estatuto do Desarmamento). Conforme relatado, a Receita Federal do Brasil, no Rio de Janeiro, durante procedimento de fiscalização em 12/05/2022, interceptou uma remessa postal contendo duas prensas de recarga de munição da marca Lee, calibres 9mm e .40, produtos sujeitos à regulamentação do Exército Brasileiro. A remessa, enviada dos Estados Unidos, tinha como destinatário Arthur Sayao Lobato, residente na Rua XYZ, nº 99, apto. 99, Alto da Boa Vista, Santo Amaro, São Paulo/SP. O valor estimado dos bens apreendidos não foi informado.', \
'Trata-se da Notícia de Fato (NF) nº 1.34.006.000176/2024-53, encaminhada pelo Instituto Nacional do Seguro Social (INSS), que relata a possível prática de fraude na obtenção de Benefício de Prestação Continuada (BPC), em favor de JUNIO FULANO DA SILVA, CPF nº 372.888.999-99. O fato teria ocorrido no município de Guarulhos/SP, Estado de São Paulo. Segundo a denúncia, documentos fraudulentos podem ter sido utilizados para a concessão indevida do benefício. A investigação busca apurar a extensão do dano ao erário e identificar outros possíveis envolvidos. Até o momento, não foi possível estimar o valor do prejuízo, e também não há provas materiais anexadas aos autos; JUNIO FULANO DA SILVA é considerado o possível beneficiário indevido e figura como investigado.', \
'Trata-se do OFÍCIO nº 189/2024/GABINETE DE PROCURADOR DE PRM/GUARULHOS, referente ao Restitui NCV-CEFRA SEI 08704.000273/2023-33, que acompanha o Boletim de Ocorrência nº AS1705-2/2023 da Polícia Civil do Estado de São Paulo, registrado no 5º D.P. de Guarulhos. O documento versa sobre a suspeita de fraude em saque de Fundo de Garantia do Tempo de Serviço (FGTS). A vítima, PRISCILA FULANA DA SILVA, RG nº 328.799.999-SP, nascida em 07/06/1980, informou que, desde 20/12/2022, desconhece a existência de uma conta associada a um cartão de crédito da Caixa Econômica Federal (CEF). Além disso, foram realizados contratos de empréstimo na modalidade de “Antecipação de saque aniversário” de seu FGTS entre 18/08/2022 e 13/09/2022, totalizando R$ 17.162,01. A investigação visa apurar as circunstâncias da fraude, identificar possíveis coautores e quantificar o prejuízo causado.', \
'Trata-se do expediente da NF 1.34.001.000067/2024-86, que visa à apuração de crime contra o sistema financeiro envolvendo as empresas Cabedal Gestão KKKK LTDA, CNPJ: 19.534.999/0001-01, e CLB - SOCIEDADE DE PROPÓSITO XXX LTDA, CNPJ/MF nº 48.947.888/0001-81, além dos indivíduos REGINALDO FULANO SILVA, CPF nº 777.888.158-37, e MYLENA FULANA SILVA, CPF nº 333.497.999-99. A investigação está sendo conduzida no município de São Paulo, Estado de São Paulo, em virtude de indícios de irregularidades financeiras e possíveis fraudes nas operações das referidas empresas. Os fatos ocorreram entre janeiro e março de 2024, quando foram identificadas movimentações financeiras suspeitas totalizando R$ 2.500.000,00. Há evidências de documentos falsificados e testemunhos de ex-funcionários, que relatam práticas fraudulentas nas operações', \
'Trata-se do Ofício nº 012/2024 - PROJUR/CRT-SP, que comunica a suposta apresentação, por CARLOS FULANO, de um documento comprobatório de conclusão de curso técnico com indícios de falsificação. A denúncia foi corroborada por manifestação da Escola Técnica, conforme registrado à fl. 52. A apuração busca esclarecer a autenticidade do documento e a veracidade da formação do noticiado.', \
'Trata-se de uma notitia-criminis relacionada a eventuais crimes previstos nos artigos 168-A e 337-A, inciso III, ambos do Código Penal, supostamente cometidos pelos representantes legais da 'Dominium EMPRESA Ltda.' (CNPJ nº 02.9999.999/0001-20). Consta nos autos que o contribuinte não efetuou o recolhimento integral das contribuições previdenciárias dos segurados empregados e contribuintes individuais durante o ano-calendário de 2007 e em junho de 2012, totalizando R$ 500.000,00 em créditos tributários. Além disso, deixou de informar nas GFIPs as remunerações pagas, bem como os valores referentes ao vale-transporte e vale-refeição. O fato foi apurado em 20/04/2024, e já existem documentos contábeis que indicam a prática de sonegação fiscal.', \
'Trata-se do BOLETIM DE OCORRÊNCIA nº BJ4057/2024 - 1ª EDIÇÃO - 2ª DP SANTO ANDRÉ/SP, que versa sobre um caso de estelionato, encaminhado pelo 2º Distrito Policial de Santo André. No relato do Boletim, descreve-se que uma mulher abordou uma pessoa em 10/04/2024, apresentando-se como destinatária de uma encomenda. Ela confirmou seu nome e sobrenome, além de assinar o documento de confirmação do objeto, levantando suspeitas sobre a autenticidade da transação. O prejuízo causado à vítima foi estimado em R$ 3.500,00, e há imagens de câmeras de segurança que registraram a abordagem, bem como a identificação da autora, que é investigada como suspeita em outros casos semelhantes.', \
'Trata-se da cópia do IPL 2022.0045346 - DMA/DRPJ/SR/PF/PE, que investiga a aquisição, por parte de GUSTAVO FULANO, de dois espécimes de serpentes Python molurus, nativas do sudoeste asiático e listadas no apêndice I da Convenção sobre Comércio Internacional das Espécies da Flora e Fauna Selvagem em Perigo de Extinção – CITES, realizada sem a licença expedida pela autoridade ambiental competente. O remetente da encomenda é indicado como residente na Rua Itapiji, 88, São Paulo/SP. A apreensão foi realizada em 12/08/2022 na cidade de Recife/PE; o valor estimado dos espécimes é desconhecido, e GUSTAVO FULANO figura como investigado por crime ambiental de aquisição de fauna exótica sem autorização.', \
'Trata-se de uma decisão no âmbito do PJe nº 5003764-28.2024.4.03.6181, tramitando na 6ª Vara Criminal Federal de São Paulo, que requisita à Autoridade Policial informações sobre a perícia dos aparelhos eletrônicos apreendidos e se existe investigação em curso em nome de RAQUEL FULANA SILVA. A decisão busca garantir a transparência e a regularidade do processo investigativo.' \
'Trata-se da decisão judicial proferida nos autos do processo nº 5008599-27.2024.4.03.6181, que requisita à Autoridade Policial informações sobre a perícia técnica realizada nos dispositivos apreendidos e esclarecimentos quanto à existência de investigação em curso. Não há, no documento, detalhamento adicional de fato criminoso ou indicação de envolvidos.' \
"

resumo_artigos_in_255 = '''
Com base nos artigos da Instrução Normativa 255/2023, as informações úteis para definir o tipo de autuação e prosseguimento de um documento analisado são as seguintes:

1. **Notícia de Fato**: Trata de casos não flagranciais, cuja análise determinará sua autuação como Notícia-Crime, Notícia-Crime em Verificação, ou Registro Especial. A triagem deve verificar a plausibilidade, tipicidade, a atribuição da Polícia Federal, e outros fatores que justifiquem ou impeçam a instauração de um inquérito policial.
2. **Procedimento de Polícia Judiciária**: Notícia-crime em verificação serve para avaliar a procedência de informações, especialmente em casos de notícia anônima ou incerteza quanto à justa causa. Ela é sumária e não substitui o inquérito policial, servindo como etapa preliminar à investigação formal.
3. **Conexões e Casos Especiais**: Algumas situações podem levar à necessidade de tratamento especial ou encaminhamento direto, como notícias envolvendo membros do Judiciário ou do Ministério Público, ou conexão com crimes já investigados. As decisões podem ser revistas, como quando há discordância fundamentada em requisição de instauração de inquérito por outro órgão.
4. **Encaminhamento e Competência**: A responsabilidade pelo recebimento e análise das notícias de fato pode envolver diferentes níveis da Corregedoria, dependendo de onde ocorre o fato ou quem é o suspeito (por exemplo, servidores da Polícia Federal ou membros de outra unidade governamental). As notícias de fato relacionadas a servidores federais lotados em unidades centrais são direcionadas à COGER/PF e comunicadas à Inteligência.
5. **Arquivamento e Recurso**: Notícias de fato podem ser arquivadas por falta de justa causa, mas podem ser desarquivadas diante de novos fatos. Decisões de arquivamento ou indeferimento de inquérito podem ser objeto de recurso. 
6. **Registro de Fato (RDF)**: O RDF é usado para cadastros iniciais de casos não flagranciais quando não se amolda a outras situações específicas. O uso de RDF deve ser excepcional e justificado.
Por fim, é fundamental que, ao recepcionar e triar documentos, as definições de tipo de autuação levem em consideração se há um procedimento correlato em andamento, a competência específica da unidade judiciária envolvida, e força normativa dos registros obrigatórios estabelecidos.

Reforçando:
Para decidir entre as autuações "NC" (Notícia-Crime), "NCV" (Notícia-Crime em Verificação) e "RE" (Registro Especial), devemos considerar os seguintes critérios:
1. **Notícia-Crime (NC)**:
   - A autuação como Notícia-Crime ocorre quando há indícios suficientes de materialidade e autoria que justifiquem a instauração de um inquérito policial formal.
   - É utilizada quando a notícia de fato apresenta elementos claros que indicam a prática de um crime e a necessidade de iniciar um processo investigativo completo.
   - Geralmente segue após a triagem inicial e análise de que a conduta é típica, antijurídica e culpável.
2. **Notícia-Crime em Verificação (NCV)**:
   - Essa autuação é escolhida quando existe dúvida quanto à existência de justa causa para abrir um inquérito policial.
   - É aplicável em casos de notícia anônima ou quando as informações apresentadas precisam ser verificadas antes de se iniciar uma investigação formal.
   - A NCV permite uma apuração sumária preliminar, com prazo para conclusão geralmente de 90 dias, prorrogável por igual período, sem realizar atos investigativos propositais.
3. **Registro Especial (RE)**:
   - O Registro Especial é utilizado para procedimentos criminais e situações que não se enquadram diretamente como Notícia-Crime ou que necessitam de um tratamento distinto.
   - Abrange casos como ações penais em andamento, requisições de diligências, medidas cautelares, cooperações internacionais, ou situações complexas que não são adequadas para os registros padrões.
   - É destinado a casos que exigem tramitação autônoma ou que estão vinculados a processos mais amplos e complexos fora do escopo imediato de um inquérito ou verificação sumária.
A escolha entre essas autuações deve ser baseada em uma análise criteriosa dos elementos disponíveis no documento recebido e sua adequação aos parâmetros legais e normativos estabelecidos pela Instrução Normativa.

Análise da Documentação e Fatos: Após a análise da notícia de fato não flagrancial, o tipo de autuação deve ser definido conforme os parâmetros do Art. 12 da IN 255/2023. Ou seja, a decisão deve ser baseada no teor da documentação e nos detalhes fornecidos.
Portanto, ao definir o "TIPO A AUTUAR", considere:

Se há crime claro, optaremos pelo tipo NC - Notícia-Crime.
Se há incerteza ou incompletude, ou é oriundo exclusivamente de notícia anônima, a autuação será do tipo NCV - Notícia-Crime em Verificação.
Se o caso envolve situações especiais, ou requisição de diligências referentes a caso já tramitado na Polícia Federal, autuaremos como RE - Registro Especial.

'''

resumo_artigos_in_270 = f'''
Com base nos artigos da Instrução Normativa 270/2023 sobre a estrutura e atribuições das delegacias especializadas da Polícia Federal, podemos destacar o seguinte resumo:
A Polícia Federal nas superintendências regionais é composta por vários setores e delegacias, cada um com responsabilidades específicas. 
O Núcleo de Cooperação Internacional (NCI) coordena esforços de cooperação internacional, auxiliando em extradições, transferências internacionais, e parcerias com forças policiais estrangeiras. 
O Setor de Inteligência Policial (SIP) gerencia informações sensíveis, realiza investigações judiciais e desenvolve análises sobre a criminalidade, além de coordenar operações de inteligência.
A Delegacia de Repressão a Crimes Cibernéticos (DELECIBER) é responsável por investigar crimes eletrônicos, como fraudes bancárias, ataques a sistemas críticos, e discriminações online, além de promover o intercâmbio de informações sobre criminalidade cibernética.
A Delegacia de Repressão a Crimes contra o Patrimônio e Tráfico de Armas (DELEPAT) combate roubos, sequestros, e o tráfico internacional de armas. 
A Delegacia de Repressão a Crimes Previdenciários (DELEPREV) investiga fraudes contra a previdência social e o seguro-desemprego, lidando com organizações criminosas especializadas nesses delitos.
No combate ao tráfico de drogas, a Delegacia de Repressão a Drogas (DRE) é encarregada de operações contra o tráfico ilícito e a lavagem de dinheiro ligada ao narcotráfico.
A Delegacia de Repressão a Crimes Fazendários (DELEFAZ) trata de contrabando, descaminho e crimes contra a ordem tributária, exercendo sua competência sobre crimes cometidos contra bens e interesses da União. 
Considere que a definição de Crimes Fazendários também possui um caráter residual, além de matéria própria. 
Isso significa que esses crimes relacionam-se a 'outros crimes cometidos em detrimento de bens, serviços ou interesses da União, suas entidades autárquicas e empresas públicas, ressalvadas as atribuições das demais unidades e delegacias'. \
Portanto, quando não for possível classificar um crime/infração em outra área de atribuição, consideraremos como da área de atribuição de 'Crimes Fazendários'.
A Delegacia de Direitos Humanos e Defesa Institucional (DELINST) tem como foco crimes como genocídio, tráfico de pessoas e outros que violam direitos humanos.
A Delegacia de Repressão a Crimes contra o Meio Ambiente (DMA) cuida de delitos ambientais e questões relacionadas ao patrimônio histórico e cultural, incluindo a prevenção de crimes que afetam povos tradicionais. 
Para crimes de corrupção e crimes financeiros, a Delegacia de Repressão à Corrupção e Crimes Financeiros (DELECOR) lida com desvio de recursos públicos e lavagem de dinheiro.
A Seção Regional da Força Integrada de Combate ao Crime Organizado (FICCO) concentra-se no combate a facções criminosas e outros crimes organizados, trabalhando em colaboração com outras forças de segurança. 
A Delegacia de Inquéritos Especiais foca em investigações que tramitam no Superior Tribunal de Justiça, garantindo que procedimentos sejam conduzidos com rigor.
Por último, o Núcleo de Assuntos Internos (NUAIN) se dedica a investigar crimes cometidos por servidores da própria Polícia Federal.
'''

assuntos_comuns_delefaz = [
'Abandono de função', 
'Ameaça', 
'Calúnia', 
'Certidão ou atestado ideologicamente falso', 
'Coação no curso do processo', 
'Contrabando ou descaminho', 
'Crimes contra a Ordem Tributária', 
'Crimes de Abuso de Autoridade', 
'Denunciação caluniosa', 
'Desacato', 
'Desobediência', 
'Duplicata simulada', 
'Esbulho possessório', 
'Estelionato', 
'Estelionato Majorado', 
'Exercício de atividade com infração de decisão administrativa', 
'Falsa identidade', 
'Falsidade ideológica', 
'Alteração de produto destinado a fins terapêuticos ou medicamentoso', 
'Falsificação de documento particular', 
'Falsificação de documento público', 
'Falsificação de papéis públicos', 
'Falsificação do selo ou sinal público', 
'Falsificação de Moeda', 'Moeda Falsa', 
'Falso testemunho ou falsa perícia', 
'Fraude à execução', 
'Fraude de lei sobre estrangeiros', 
'Fraude processual', 
'Frustração de direitos assegurados por lei trabalhista', 
'Inserção de dados falsos em sistema de informações', 
'Inutilização de edital ou de sinal', 
'Mediação para servir a lascívia de outrem', 
'Patrocínio infiel', 
'Peculato', 
'Prevaricação', 
'Supressão de documento', 
'Uso de documento falso', 
'Violação do segredo profissional'  ]


# Dicionário para armazenar os prompts. A chave é um identificador único.
_PROMPTS: Dict[str, str] = {

    "GENERAL_ANALYSIS_V1": """
Você é um assistente de IA especializado em analisar documentos textuais extraídos de PDFs.
Sua tarefa é ler o texto fornecido e realizar uma análise concisa e objetiva sobre o conteúdo principal.

**Texto para Análise:**
{input_text}

**Instruções:**
1. Identifique o tema central ou o propósito principal do documento.
2. Resuma os pontos ou argumentos mais importantes apresentados no texto.
3. Se houver informações como datas, nomes de partes envolvidas, ou valores significativos, mencione-os brevemente se forem relevantes para o resumo.
4. Mantenha a resposta focada no conteúdo do texto fornecido. Não adicione informações externas ou opiniões.
5. Formate sua resposta de forma clara e legível. Use parágrafos curtos e, se apropriado, listas.

**Resultado da Análise:**
""",

    "UNIQUE_ANALYSIS_V1": [

        # BLOCO A – CONTEXTO FUNCIONAL:

        # system_prompt com foco na função técnica:
        {
        "role": "system", "content": "Você é um analista técnico especializado em triagem documental e análise preliminar de peças oficiais. Sua principal função é processar documentos recebidos por canais institucionais, extrair informações estruturadas relevantes, classificar os dados conforme listas de referência e elaborar resumos objetivos sobre o conteúdo analisado. \
            Atua com base em normas administrativas, jurídicas e operacionais, com foco em precisão, rastreabilidade e fundamentação."
        },

        # opção de system_prompt para enfatizar normativos e rigidez processual:
        # "Você é um analista de conformidade documental responsável por aplicar normas legais e administrativas na análise de documentos oficiais. 
        # Sua função é identificar fatos relevantes, estruturar dados e justificar classificações com base em critérios técnicos e regulatórios."

        # opção de system_prompt para enfatizar uso em contexto jurídico-administrativo amplo:
        # "Você é um especialista em análise documental e triagem pré-jurídica, atuando na leitura e interpretação de peças oficiais. 
        # Seu papel é organizar informações factuais, classificar elementos conforme diretrizes normativas e oferecer justificativas claras para cada decisão tomada."

        # BLOCO B – INSTRUÇÃO GERAL DE TAREFA
        {
        "role": "user",
        "content": "Você deverá analisar documentos recebidos pela Polícia Federal e extrair informações conforme instruções abaixo. \
                    Foque especialmente nas informações que se destinam à Polícia Federal. Aguarde o envio do texto documental após ler as instruções."
        },
        # Opção caso o texto-objeto seja posicionado no início do prompt: 
        # "content": "Você deverá analisar o conteúdo acima e extrair as informações conforme as instruções e listas fornecidas a seguir. 
        # Foque especialmente nas informações que se destinam à Polícia Federal."

        # BLOCO C – LISTAS DE OPÇÕES:
        {
        "role": "user",
        "content":  "### LISTAS DE OPÇÕES REFERENCIAIS:\n\n"
                    f"- Lista de tipos de documento (tipos_doc): {str(tipos_doc)}\n"
                    f"- Lista de órgãos de origem (origens_doc): {str(origens_doc)}\n"
                    f"- Lista de tipos de local (tipos_locais): {str(tipos_locais)}\n"
                    f"- Lista de áreas de atribuição (areas_de_atribuição): {str(areas_de_atribuição)}\n"
                    f"- Lista de tipos de autuação após análise inicial (tipo_a_autuar): {str(tipo_a_autuar)}\n"
                    f"- Lista de assuntos de RE - Registro Especial (assuntos_re): {str(assuntos_re)}\n"
                    f"- Lista de Delegacias especializadas da SR/PF/SP (lista_delegacias_especializadas), localizadas na cidade capital São Paulo: {str(lista_delegacias_especializadas)}\n"
                    f"- Lista de tipos de papel nos casos (tipos_envolvidos): {str(tipos_envolvidos)}"
        },

        # BLOCO D – MODELO DE SAÍDA ESPERADO
        {
        "role": "user",
        "content":  "### CAMPOS A SEREM EXTRAÍDOS PARA CADA DOCUMENTO\n\n"
                    "1. DESCRIÇÃO GERAL: Frase sucinta que resuma o objeto do documento, sem se confundir com o RESUMO DO FATO, que é mais detalhado.\n"
                    "2. TIPO DE DOCUMENTO DE ORIGEM: Classifique o documento conforme as opções literais da lista tipos_doc.\n"
                    "3. ÓRGÃO DE ORIGEM: Selecione a entidade que enviou o documento, conforme as opções literais da lista origens_doc.\n"
                    "4.1 UF DE ORIGEM: Indique o estado do órgão de origem no formato 'UF', ou aponte 'Dado ausente' se não encontrar esse informação no texto.\n"
                    "4.2 MUNICÍPIO DE ORIGEM: Indique o respectivo município do órgão de origem, ou aponte 'Dado ausente' se não encontrar esse informação no texto.\n"
                    "5. RESUMO DO FATO: Resuma o fato principal que originou o documento.\n"
                    "6.1 UF DO FATO: Indique o Estado onde ocorreu o fato, ou aponte 'Dado ausente' se não encontrar esse informação no texto.\n"
                    "6.2 MUNICÍPIO DO FATO: Indique o respectivo município onde ocorreu o fato, ou aponte 'Dado ausente' se não encontrar esse informação no texto.\n"
                    "7. TIPO DE LOCAL: Classifique o local do fato conforme as opções literais da lista tipos_locais.\n"
                    "8. VALOR DE APURAÇÃO: Informe o valor do prejuízo se houver, ou aponte '0,00' se o texto não contiver essa informação.\n"
                    "9. TIPIFICAÇÃO PENAL: Classifique conforme o código penal aplicável, ou aponte 'Dado ausente' se não encontrar esse informação no texto.\n"
                    "10. ÁREA DE ATRIBUIÇÃO: Selecione a área temática de atribuição da investigação conforme intruções complementares e lista areas_de_atribuição.\n"
                    "11. TIPO A AUTUAR: Indique o tipo de autuação que prosseguirá após análise inicial, conforme intruções complementares e lista tipo_a_autuar.\n"
                    "12. ASSUNTO DO RE: Se o tipo de autuação for 'RE', selecione o assunto conforme as opções literais da lista assuntos_re, senão indique como 'Não aplicável'.\n"
                    "13. DESTINAÇÃO: Conforme opções literais da lista lista_delegacias_especializadas\n"
                    "14. PESSOAS ENVOLVIDAS: Relacione os envolvidos (Nomes completos, CPFs/CNPJs e papel no caso conforme as opções literais da lista tipos_envolvidos).\n"
                    "15. LINHA DO TEMPO: Arrole uma linha cronológica dos fatos relevantes documentados, quando possível.\n"
                    "16. OBSERVAÇÕES: Campo opcional para registro de outras informações relevantes ou de observações complementares; se for desnecessário deve ser preenchido com string vazia."
        },

        # BLOCO F – CRITÉRIOS DE CLASSIFICAÇÃO E USO DAS LISTAS
        {
        "role": "user",
        "content": "### CRITÉRIOS DE CLASSIFICAÇÃO PARA CAMPOS-CHAVE\n\n"
                    
                    "**ORIENTAÇÕES GERAIS**\n"
                    "- Utilize exatamente os termos das listas fornecidas.\n"
                    "- Priorize itens específicos. Use 'Outro' ou 'Não classificado' apenas se necessário.\n"
                    "- Se o dado estiver ausente, utilize 'Dado ausente'. Para valores, use '0,00' se não constar.\n\n"
                    
                    "**TIPO DE DOCUMENTO:**\n"
                    "- Boletim de Ocorrência (externo): Documento que constem oficialmente originados com ocorrência registrada em sistemas de segurança pública de Polícia Civil.\n"
                    "- Requisição - Ministério Público: Requisição feita por membros do MP, mesmo que o encaminhamento tenha sido feito por outro tipo da lista (como e-mail ou ofício).\n"
                    "- Inquérito Policial - Polícia Civil: Utilize para documentos formalmente classificados como investigações conduzidas em Polícia Civil Estadual e que estão sendo declinada competência para a Polícia Federal.\n"
                    "- IPJ - Informação de Polícia Judiciária: Utilize para documentos originados em informação oficial da própria Polícia Federal.\n"
                    "- Requisição - Judicial: deve ser utilizada exclusivamente para documentos assinados por Juiz ou Juíza de Direito, no exercício de sua função jurisdicional. Petições diversas, despachos administrativos ou requisições oriundas do Ministério Público ou de outros órgãos não se enquadram nesta categoria.\n"
                    "- Ofício: Use esta opção quando o documento foi enviado oficialmente através de ofício numerado e não se enquadra dentre as opções anteriores.\n"
                    "- Relatório: Use esta opção quando o documento de origem estiver assim classificado e não se enquadrar dentre as opções anteriores.\n"
                    "- E-mail: Use esta opção quando o documento foi enviado eletronicamente e o conteúdo relevante está no corpo do e-mail.\n"
                    "- Use 'Outro' apenas se nenhuma das anteriores se aplica e descreva em 'Observações'.\n\n"
                    
                    "**ORGÃO DE ORIGEM:**\n"
                    "- Caso o documento de origem seja encaminhado, por último, do Ministério Público para a Polícia Federal, o Ministério Público (Estadual ou Federal) será considerado o órgão de origem, desconsiderando os encaminhamentos anteriores.\n"
                    "- Pode ser uma entidade institucional, mas também pode ser uma pessoa física ou jurídica que figure como remetente do documento, ou nos casos de petições postuladas por advogado e requerente.\n"
                    "- Use 'OUTRO' quando não identificado e detalhe em 'Observações'.\n\n"
                    
                    "**UF/MUNICÍPIO DO FATO:**\n"
                    "- Quando não houver indicação clara da localização do fato, pode-se utilizar como referência a localização ou residência do requerente, se disponível no texto.\n"
                    "- Atente-se a casos de objetos apreendidos fora do estado, mas cuja remessa ilegal tenha origem em São Paulo, sendo este o local de competência do crime e considerado Local do Fato.\n\n"
                    
                    "**ÁREA DE ATRIBUIÇÃO:**\n"
                    "- 'Crimes contra a seguridade social' se insere como 'Crimes Previdenciários' na lista de Áreas de Atribuição.\n\n"
                    
                    "**DESTINAÇÃO:**\n"
                    "- Neste ponto, vamos ignorar o local do fato para determinar a Destinação, considerando apenas os critérios a serem vistos abaixo na instrução normativa nº 270/2023.\n\n"
                    
                    "**TIPO DE LOCAL:**\n"
                    "- Para fatos ocorridos exclusivamente em ambiente digital, deve ser classificado como 'Internet'.\n"
                    "- Use 'Não classificado / Outros' se não couber nas opções e detalhe em 'Observações'.\n\n"

                    "**ASSUNTO DO RE:**\n"
                    "- Este campo deve ser preenchido apenas se o TIPO A AUTUAR for 'RE - Registro Especial'; caso contrário, indicar 'Não aplicável'."
        },

        # BLOCO G – RESUMO DO FATO: ORIENTAÇÕES DETALHADAS
        {
        "role": "user",
        "content": "### INSTRUÇÕES PARA O CAMPO 'RESUMO DO FATO'\n\n"
                    "- Descreva de forma objetiva o fato gerador.\n"
                    "- Informe o tipo e numeração da documentação de origem, bem como de eventuais autuações tramitadas e decorrentes;\n"
                    "- Inclua também órgão remetente, possíveis crimes, nomes dos envolvidos e seus papéis, data/local do fato, provas e valor estimado do prejuízo.\n"
                    "- Exemplos de documentos de origem: Ofício nº 789/2023, Notícia de Fato nº 1.33.001.000099/2024-88, Representação Fiscal para Fins Penais (RFFP) nº 10899.658444/2023-83, Processo Administrativo Fiscal (PAF) nº 19588.5444/2023-71.\n\n"
                    "- O texto deve ser neutro, factual e completo, evitando julgamentos pessoais.\n\n"
        },
        {
        "role": "user",
        "content": "### INSTRUÇÃO COMPLEMENTAR PARA CASOS DE REGISTRO ESPECIAL (RE):\n\n"
                    "- Em situações em que o documento recebido consiste em requisição judicial, ofício ministerial ou despacho processual que, por si só, gera a necessidade de cadastro como Registro Especial (RE), a própria requisição será considerada o fato gerador.\n"
                    "- Nesses casos, o 'RESUMO DO FATO' deverá descrever objetivamente o conteúdo da requisição e sua finalidade imediata (ex: solicitação de diligência, pedido de informação sobre laudo, designação de audiência, etc.).\n"
                    "- Quando não houver informações adicionais sobre infrações, autores ou vítimas no conteúdo do documento, utilize as expressões 'Dado ausente' ou 'Não informado' nos demais campos aplicáveis.\n\n"
        },

        # BLOCO H – EXEMPLOS DE SAÍDA
        {
        "role": "user",
        "content": f"### EXEMPLOS DE RESUMO DO FATO:\n\n{exemplos_resumos}"
        },

        # BLOCO I – INSTRUÇÕES NORMATIVAS
        {
        "role": "user",
        "content": f"### INSTRUÇÃO NORMATIVA DG/PF Nº 255/2023 (para definição de 'TIPO A AUTUAR')\n\n{resumo_artigos_in_255}"
        },
        {
        "role": "user",
        "content": "Nota: Registros são inicialmente RDF. Após análise, devem ser convertidos para NC, NCV ou RE conforme o caso. RDF deve permanecer apenas quando estritamente necessário."
        },
        {
        "role": "user",
        "content": f"### INSTRUÇÃO NORMATIVA DG/PF Nº 270/2023 (para definição de 'DESTINAÇÃO')\n\n{resumo_artigos_in_270}"
        },
        {
        "role": "user",
        "content": "Correspondência entre ÁREA DE ATRIBUIÇÃO e DESTINAÇÃO deve ser mantida. Por exemplo: 'Crimes Fazendários' → DELEFAZ."
        },

        # BLOCO J – ORIENTAÇÕES ESPECIAIS E DICAS
        {
        "role": "user",
        "content": "### ORIENTAÇÕES ESPECIAIS:\n\n"
                    "- Requisições judiciais sobre casos já tramitados devem ser convertidas em RE.\n"
                    "- Representações fiscais para fins penais normalmente são de natureza fazendária e vão para a Delefaz.\n"
                    f"- Exemplos comuns da área 'Crimes Fazendários': {assuntos_comuns_delefaz}"
        },

        # BLOCO K – JUSTIFICATIVAS PARA DEFINIÇÕES
        {
        "role": "user",
        "content": "### JUSTIFICATIVAS OBRIGATÓRIAS (11 CAMPOS)\n\n"
                    "Além dos 16 campos, forneça justificativas para as seguintes definições:\n"
                    "- TIPO DE DOCUMENTO DE ORIGEM\n"
                    "- ÓRGÃO DE ORIGEM\n"
                    "- UF/MUNICÍPIO DE ORIGEM\n"
                    "- TIPO DE LOCAL\n"
                    "- UF/MUNICÍPIO DO FATO\n"
                    "- VALOR DE APURAÇÃO (se houver)\n"
                    "- ÁREA DE ATRIBUIÇÃO\n"
                    "- TIPIFICAÇÃO PENAL\n"
                    "- TIPO A AUTUAR\n"
                    "- ASSUNTO DO RE (se aplicável)\n"
                    "- DESTINAÇÃO\n\n"
                    "Justificativas podem conter transcrições de trechos relevantes do texto ou de normativos. Devem ser claras e fundamentadas."
        },

        # BLOCO L – AÇÃO FINAL
        {
        "role": "user",
        "content": "### AÇÃO FINAL\n\nA seguir será enviado o texto de um documento para que você o analise conforme instruções acima.\n\n"
        "{input_text}\n"
        }
    ],

}


def get_prompt(prompt_name: str) -> Optional[str]:
    """
    Recupera um template de prompt pelo seu nome.

    Args:
        prompt_name (str): O identificador único do prompt (ex: "GENERAL_ANALYSIS_V1").

    Returns:
        Optional[str]: A string do template do prompt se encontrado, None caso contrário.
    """
    return _PROMPTS.get(prompt_name)

'''
TODO: Agrupar:

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

# quanto ao tipo de procedimento a gerar:
11. TIPO A AUTUAR
12. ASSUNTO DO RE


# TODO:
Se municipio_fato fora da circunscrição:
    - reset: 
        - tipo_autuação = RDF
        - destinação = DPF ou COR respectiva

'''
