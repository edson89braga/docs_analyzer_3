
from config.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)

'''
### Exemplo de uso em encadeamento de mensagens: ============================================

from langchain.schema import (
    SystemMessage,
    HumanMessage,
    AIMessage
)
from langchain.chat_models import ChatOpenAI

chat = ChatOpenAI()

messages = [
    SystemMessage(content="Você é um assistente útil"),
    HumanMessage(content="Olá!"),
    AIMessage(content="Olá! Como posso ajudar?"),
    HumanMessage(content="Qual é seu nome?")
]

response = chat(messages)

### Exemplo de uso de PDFLoader: =========================================================

from langchain.document_loaders import PyPDFLoader, PDFPlumberLoader

# Usando PyPDFLoader
loader = PyPDFLoader("documento.pdf")
pages = loader.load_and_split()

# Usando PDFPlumber (mais robusto para PDFs complexos)
loader = PDFPlumberLoader("documento.pdf")
documents = loader.load()

### Exemplos de uso do load_summarize_chain: =========================================================

from langchain.chains.summarize import load_summarize_chain

# Resumo simples
chain = load_summarize_chain(llm, chain_type="stuff")

# Resumo map_reduce (melhor para documentos longos)
chain = load_summarize_chain(llm, chain_type="map_reduce")

# Resumo refine (processamento iterativo)
chain = load_summarize_chain(llm, chain_type="refine")

summary = chain.run(documents)

'''