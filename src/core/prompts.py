# src/core/prompts.py
"""
Módulo para gerenciar e fornecer os prompts utilizados nas interações com LLMs.
"""
from typing import Optional, Dict

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

    # --- Adicionar outros prompts aqui no futuro ---
    # "EXTRACT_PARTIES_V1": "...",
    # "SUMMARIZE_CONCLUSION_V1": "...",
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

