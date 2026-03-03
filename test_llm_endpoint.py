#!/usr/bin/env python3
"""
Script de teste para o endpoint LLM interno da PF.
Este script simula o uso da API da OpenAI para interagir com o modelo Qwen3-8B-AWQ
hospedado no endpoint http://llm.pf.gov.br:31893/v1/chat/completions.

Uso:
    python test_llm_endpoint.py

Requisitos:
    - Instalar a biblioteca openai: pip install openai
    - Acesso à rede interna da PF para o endpoint.
"""

import sys
import json
from rich import print
from openai import OpenAI

# Configurações do endpoint
BASE_URL = "http://llm.pf.gov.br:31893/v1"
API_KEY = "EMPTY"  # Como especificado no exemplo do curl
MODEL = "Qwen3-8B-AWQ"

def test_llm_endpoint():
    """
    Testa o endpoint LLM com uma mensagem de exemplo.
    """
    try:
        # Inicializa o cliente OpenAI com o endpoint customizado
        client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL,
        )

        # Mensagem de teste (igual ao exemplo do curl)
        messages = [
            {"role": "system", "content": "Você é um assistente útil."},
            {"role": "user", "content": "Olá, você sabe corrigir erros em programas Java? /no_think"}
        ]

        # Faz a chamada para o chat completion
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=200_000
        )

        # Exibe a resposta
        print("Resposta do LLM:")
        print(json.dumps(response.model_dump(), indent=2, ensure_ascii=False))

        # Extrai e exibe apenas o conteúdo da resposta
        if response.choices:
            content = response.choices[0].message.content
            print("\nConteúdo da resposta:")
            print(content)
        else:
            print("Nenhuma escolha retornada na resposta.")

    except Exception as e:
        print(f"Erro ao testar o endpoint: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Testando endpoint LLM...")
    test_llm_endpoint()
    print("Teste concluído.")