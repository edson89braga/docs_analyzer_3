# src/app_cache.py

import threading

# Este módulo serve como um cache simples e ponto de sincronização.
heavy_imports_loading_event = threading.Event() # Evento para sinalizar o fim do carregamento de módulos pesados