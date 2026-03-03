# Melhorias no Parser JSON - Robustez Aumentada

## Problema Identificado

O endpoint PF (Qwen3-8B-AWQ) retorna JSON válido, mas envolvido em delimitadores de markdown:

```
```json
{
  "campo": "valor"
}
```
```

O código anterior tentava fazer `model_validate_json()` diretamente neste texto, causando erro:
```
ValidationError: Invalid JSON: expected value at line 1 column 1
```

## Solução Implementada

### 1. Função Robusta: `extract_and_clean_json()`

Localização: [src/core/ai_orchestrator.py](src/core/ai_orchestrator.py#L179)

A função realiza os seguintes passos em cascata:

#### Passo 1: Limpeza Básica
- Remove tags `<think>` e `</think>` (para modelos que usam pensamento)
- Remove espaços em branco no início/fim

#### Passo 2: Extração de Markdown Code Blocks
- Procura por padrões: ` ```json ... ``` ` ou ` ``` ... ``` `
- Usa regex: `r'```(?:json)?\s*(.*?)\s*```'`
- Extrai o JSON de dentro do bloco

#### Passo 3: Validação JSON Inicial
- Tenta fazer `json.loads()` no JSON limpo
- Se bem-sucedido, retorna

#### Passo 4: Fallback - Busca por Chaves
- Se falhar, procura por `{` e `}`
- Extrai substring entre a primeira `{` e última `}`
- Tenta validar novamente

#### Passo 5: Fallback - Busca por Array
- Se ainda falhar, procura por `[` e `]`
- Extrai substring entre a primeira `[` e última `]`
- Tenta validar como array JSON

#### Passo 6: Erro com Debug
- Se todos os fallbacks falharem, lança `ValueError`
- Loga os primeiros 500 caracteres para análise

### 2. Atualização das Chamadas API

#### Provider OpenAI [Linha 643]
```python
try:
    final_response_text_clean = extract_and_clean_json(final_response_text)
    final_response = output_formats[prompt_name].model_validate_json(final_response_text_clean)
except (ValueError, json.JSONDecodeError) as e:
    logger.error(f"Erro ao processar JSON do OpenAI: {e}")
    raise
```

#### Provider LLM_PF [Linha 721]
```python
try:
    final_response_text_clean = extract_and_clean_json(final_response_text)
    final_response = output_formats[prompt_name].model_validate_json(final_response_text_clean)
except (ValueError, json.JSONDecodeError) as e:
    logger.error(f"Erro ao processar JSON do endpoint PF: {e}", exc_info=True)
    raise
```

## Benefícios

✅ **Robustez**: Trata JSON com delimitadores markdown  
✅ **Flexibilidade**: Múltiplos fallbacks para diferentes formatos  
✅ **Debug**: Logs detalhados em cada etapa  
✅ **Validação**: Valida JSON antes de passar para Pydantic  
✅ **Escalabilidade**: Pronto para outros provedores que retornem JSON formatado

## Casos de Uso Tratados

1. ` ```json { ... } ``` ` - Markdown code block com label
2. ` ``` { ... } ``` ` - Markdown code block sem label  
3. `{ ... }` - JSON puro sem formatação
4. Textos com JSON aninhado em conteúdo maior
5. Arrays JSON `[...]` além de objetos
6. Tags de thinking `<think>...</think>` intercaladas

## Melhorias Futuras Sugeridas

- [ ] Adicionar suporte para JSON malformado (trailing commas, aspas simples)
- [ ] Implementar retry automático com cleanup mais agressivo
- [ ] Cache de padrões de resposta bem-sucedidos
- [ ] Telemetria de qual fallback foi usado para cada request
