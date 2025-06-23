import os
from datetime import datetime

def scan_and_consolidate_python_files(output_file='python_files_consolidated.txt'):
    """
    Scans the current repository for all Python files and consolidates their content into a single TXT file.
    
    Args:
        output_file (str): Name of the output consolidated file.
    """
    # Get current directory (repository root)
    repo_root = os.getcwd()
    
    # Prepare output file
    with open(output_file, 'w', encoding='utf-8') as outfile:
        # Write header
        outfile.write(f"CONSOLIDATED PYTHON FILES - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        outfile.write(f"Repository: {repo_root}\n")
        outfile.write("=" * 80 + "\n\n")
        
        # Walk through all directories
        file_count = 0
        total_size = 0
        
        for root, dirs, files in os.walk(repo_root):
            # Skip virtual environments and other common directories to ignore
            if 'venv' in root or 'env' in root or '.git' in root or '__pycache__' in root or 'tests' in root or 'legacy' in root:
                continue
                
            for file in files:
                if file in ('extract_pyfiles.py', 'run_dev.py', 'admin_llm_providers.py',
                            'cleanup_cloud_logs.py', 'teste_int.py', 'set_admin.py',
                            'test_layout_app.py', 'teste_interativo.py', '__init__.py', 'prompts.py',
                            'testes_pdf_processor_and_ocr.py'):
                    continue
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        # Get relative path
                        rel_path = os.path.relpath(file_path, repo_root)
                        
                        # Write file header
                        outfile.write(f"FILE: {rel_path}\n")
                        outfile.write(f"PATH: {file_path}\n")
                        outfile.write("-" * 60 + "\n")
                        
                        # Read and write file content
                        with open(file_path, 'r', encoding='utf-8') as infile:
                            content = infile.read()
                            outfile.write(content + "\n")
                        
                        # Add separator between files
                        outfile.write("\n" + "=" * 80 + "\n\n")
                        
                        # Update counters
                        file_count += 1
                        total_size += os.path.getsize(file_path)
                        
                    except Exception as e:
                        outfile.write(f"ERROR reading {file_path}: {str(e)}\n\n")
        
        # Write summary
        outfile.write(f"\nSUMMARY:\n")
        outfile.write(f"Total Python files: {file_count}\n")
        outfile.write(f"Total size: {total_size} bytes\n")
        outfile.write(f"Consolidated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"Consolidation complete. {file_count} Python files merged into {output_file}")

if __name__ == "__main__":
    scan_and_consolidate_python_files()