#!/usr/bin/env python3
"""
Script para listar todos os principais arquivos do repositório (.py e .md).
O output é printado no console e salvo em 'lista_arqs_repo.txt'.
"""

from pathlib import Path
import os

def main():
    # Diretório raiz do repositório (diretório atual)
    repo_root = Path.cwd()
    
    # Lista de pastas a ignorar na varredura
    pastas_ignorar = [
        '__pycache__',
        '_update_temp',
        '_updater_downloads',
        'logs',
        'logs_backup_cloud_failed',
        'temp_admin_exports',
        'temp_docx_exports',
        'uploads_temp',
        'upx-5.0.1-win64',
        'pyinstaller_files',
        'tests_in_dev',
        'tests_scripts',
        'notebooks',
        'assets/temp_admin_exports',
        'assets/temp_docx_exports',
        'context_exports',
        '.pytest_cache',
        'ml_engine'
    ]
    
    # Lista para armazenar os arquivos encontrados
    arquivos = []
    
    # Extensões desejadas
    extensoes = ['*.py', '*.md']
    
    # Percorrer recursivamente e encontrar arquivos
    for ext in extensoes:
        for arquivo in repo_root.rglob(ext):
            # Obter caminho relativo ao repo_root
            caminho_relativo = arquivo.relative_to(repo_root)
            
            # Verificar se o arquivo está em uma pasta a ignorar
            ignorar = False
            for parte in caminho_relativo.parts:
                if parte in pastas_ignorar:
                    ignorar = True
                    break
            
            if not ignorar:
                arquivos.append(str(caminho_relativo))
    
    # Ordenar a lista alfabeticamente
    arquivos.sort()
    
    # Imprimir no console
    print("Lista de arquivos .py e .md no repositório:")
    for arq in arquivos:
        print(arq)
    
    # Salvar em arquivo
    arquivo_saida = repo_root / 'lista_arqs_repo.txt'
    with open(arquivo_saida, 'w', encoding='utf-8') as f:
        f.write("Lista de arquivos .py e .md no repositório:\n")
        for arq in arquivos:
            f.write(arq + '\n')
    
    print(f"\nLista salva em: {arquivo_saida}")

if __name__ == "__main__":
    main()