# src/app_cache.py

# -> Módulo descontinuado com a migração do sentence_transformer_model para aplicação apartada servida com fastapi.

import threading

# Este módulo servirá como um cache simples e ponto de sincronização.
sentence_transformer_model = None

model_loading_event = threading.Event() # Evento para sinalizar o fim do carregamento

heavy_imports_loading_event = threading.Event() # Evento para sinalizar o fim do carregamento de módulos pesados