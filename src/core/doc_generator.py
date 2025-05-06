"""
DocumentGenerator

Módulo responsável pela geração de documentos oficiais,
incluindo despachos e informações, com base em templates.

Dependencies:
    - logging: Para registro de logs e tratamento de erros
    - typing: Para tipagem estática e melhor documentação do código
    - dataclasses: Para configurações estruturadas de geração de documentos
    - datetime: Para manipulação de datas e formatação
    - pathlib: Para manipulação de caminhos e diretórios
    - models.entities: Para tipos de dados do domínio (Case, DocumentTemplate)
    - models.documents: Para tipos de documentos suportados (DocumentType)

Example:
    Exemplo básico de uso do módulo
    
    >>> from crime_analyzer.src.core.doc_generator import DocumentGenerator
    >>> from crime_analyzer.src.models.entities import Case, DocumentTemplate
    >>> from crime_analyzer.src.models.documents import DocumentType
    >>> case = Case(case_number="123", summary="Resumo do caso")
    >>> template = DocumentTemplate(type=DocumentType.DESPACHO, content="Template")
    >>> generator = DocumentGenerator()
    >>> output_path = generator.generate_document(case, template)
    >>> print(f"Documento gerado em: {output_path}")
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class DocumentGeneratorConfig:
    """Configurações para geração de documentos."""
    output_dir: str = "output"
    template_dir: str = "templates"
    date_format: str = "%d/%m/%Y"
    
class DocumentGenerator:
    """Classe principal para geração de documentos."""
    
    def __init__(self, config: DocumentGeneratorConfig = None):
        self.config = config or DocumentGeneratorConfig()
        self._ensure_output_dir()
        
    def generate_document(self, case: Case, template: DocumentTemplate) -> str:
        """Gera um documento com base no caso e template."""
        try:
            # Verifica se o template existe
            if not template:
                raise ValueError("Template não fornecido")
                
            # Seleciona o método de geração apropriado
            if template.type == DocumentType.DESPACHO:
                return self._generate_despacho(case, template)
            elif template.type == DocumentType.INFORMACAO:
                return self._generate_informacao(case, template)
            else:
                raise ValueError(f"Tipo de documento não suportado: {template.type}")
        except Exception as e:
            logger.error(f"Erro ao gerar documento: {str(e)}")
            raise
            
    def _generate_despacho(self, case: Case, template: DocumentTemplate) -> str:
        """Gera um despacho com base no caso."""
        content = template.content.format(
            case_number=case.case_number,
            date=datetime.now().strftime(self.config.date_format),
            summary=case.summary,
            recommendations="\n".join(case.recommendations)
        )
        
        return self._save_document(
            f"Despacho_{case.case_number}.docx",
            content
        )
        
    def _generate_informacao(self, case: Case, template: DocumentTemplate) -> str:
        """Gera uma informação com base no caso."""
        content = template.content.format(
            case_number=case.case_number,
            date=datetime.now().strftime(self.config.date_format),
            timeline="\n".join([e.description for e in case.events]),
            involved_people=", ".join([p.name for p in case.involved_people])
        )
        
        return self._save_document(
            f"Informacao_{case.case_number}.docx",
            content
        )
        
    def _save_document(self, filename: str, content: str) -> str:
        """Salva o documento gerado."""
        output_path = Path(self.config.output_dir) / filename
        
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            return str(output_path)
        except Exception as e:
            logger.error(f"Erro ao salvar documento: {str(e)}")
            raise
            
    def _ensure_output_dir(self) -> None:
        """Garante que o diretório de saída existe."""
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
