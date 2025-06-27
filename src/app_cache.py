# src/app_cache.py
import threading

# Este módulo servirá como um cache simples e ponto de sincronização.
sentence_transformer_model = None
model_loading_event = threading.Event() # Evento para sinalizar o fim do carregamento