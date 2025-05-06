import logging
import re
from typing import Dict, List, Optional
from dataclasses import dataclass

'''  Módulo_base ainda NÃO utilizado no projeto  '''

logger = logging.getLogger(__name__)

@dataclass
class AnonymizationRule:
    """Regra de anonimização para tipos específicos de dados."""
    pattern: str
    replacement: str
    description: str

class DataAnonymizer:
    """Classe principal para anonimização de dados sensíveis."""
    
    def __init__(self):
        self.rules = self._load_default_rules()
        
    def _load_default_rules(self) -> Dict[str, AnonymizationRule]:
        """Carrega regras padrão de anonimização."""
        return {
            "cpf": AnonymizationRule(
                pattern=r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
                replacement="***.***.***-**",
                description="Anonimização de CPF"
            ),
            "rg": AnonymizationRule(
                pattern=r"\b\d{2}\.\d{3}\.\d{3}-[0-9Xx]\b",
                replacement="**.***.***-*",
                description="Anonimização de RG"
            ),
            "phone": AnonymizationRule(
                pattern=r"\(\d{2}\)\s?\d{4,5}-\d{4}",
                replacement="(**) ****-****",
                description="Anonimização de telefone"
            ),
            "email": AnonymizationRule(
                pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                replacement="*****@*****.***",
                description="Anonimização de e-mail"
            )
        }
        
    def anonymize_text(self, text: str, custom_rules: List[AnonymizationRule] = None) -> str:
        """Anonimiza dados sensíveis em um texto."""
        try:
            anonymized_text = text
            rules = self._get_effective_rules(custom_rules)
            
            for rule in rules.values():
                anonymized_text = re.sub(
                    rule.pattern,
                    rule.replacement,
                    anonymized_text,
                    flags=re.IGNORECASE
                )
                
            return anonymized_text
        except Exception as e:
            logger.error(f"Erro ao anonimizar texto: {str(e)}")
            raise
            
    def anonymize_person(self, person: Person) -> Person:
        """Anonimiza dados de uma pessoa."""
        try:
            return Person(
                name="*****",
                documents={
                    doc_type: "*****" for doc_type in person.documents
                },
                contact={
                    contact_type: "*****" for contact_type in person.contact
                },
                metadata=person.metadata
            )
        except Exception as e:
            logger.error(f"Erro ao anonimizar pessoa: {str(e)}")
            raise
            
    def _get_effective_rules(self, custom_rules: List[AnonymizationRule]) -> Dict[str, AnonymizationRule]:
        """Combina regras padrão com customizadas."""
        rules = self.rules.copy()
        
        if custom_rules:
            for rule in custom_rules:
                rules[rule.description.lower()] = rule
                
        return rules
