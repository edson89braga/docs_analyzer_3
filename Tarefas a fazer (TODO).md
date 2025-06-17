======================================================================================
# TODO: Próximas Tarefas:

> Refactor e testes sobre nc_analyze_view
> ERROS: págs relevantes ausentes do filtro final; displauLLMresponse replicado; Flag Reanalysis não capturado

> Fix: CreateUser: Tratar erro "message": "EMAIL_EXISTS"
> Melhorias na responsividade do LLMStructuredResultDisplay;

----------------

> revisar sistemática do logging em nuvem;

> Linkar alertas e msgs informativas de responsabilidade no uso de IA

> pyinstaller e testes na rede;

> Testes de Score sobre multiplas formas de prompt: modelos, prompts, temperaturas.

> Check lentidão na inicialização do app

======================================================================================
# TODO: Mensagens a incluir na Gui:

1. Mensagem Inicial (Login / Primeiro Acesso)
Objetivo: Estabelecer desde o primeiro contato que a IA é uma ferramenta de suporte, e não um substituto para o julgamento humano.
Localização Sugerida:
Na tela de login, logo abaixo dos campos de senha.
Alternativamente, como um diálogo de confirmação (AlertDialog) que aparece apenas no primeiro login do usuário, forçando-o a ler e concordar.
Texto Sugerido:
Uso Responsável da IA
Este sistema utiliza Inteligência Artificial como uma ferramenta de auxílio à análise. As informações e sugestões geradas são preliminares e devem ser rigorosamente verificadas por um analista humano. A responsabilidade final pela correção, interpretação e uso dos dados é inteiramente do usuário.

3. Alerta Contextual (Junto aos Resultados da Análise)
Objetivo: Alertar o usuário no momento exato em que ele está consumindo a informação gerada pela IA, reforçando a necessidade de revisão antes de qualquer ação.
Localização Sugerida:
Como um cabeçalho ou um balão de aviso (ft.Container com ícone e cor de destaque) imediatamente acima da área onde os resultados da análise LLM são exibidos (LLMStructuredResultDisplay).
Texto Sugerido:
Análise Preliminar (Gerada por IA)
Atenção: Todos os campos, classificações e resumos a seguir foram gerados por um modelo de linguagem e devem ser tratados como uma sugestão inicial. Revise e valide cuidadosamente cada informação antes de prosseguir com qualquer ato administrativo ou encaminhamento oficial.

4. Seção "Sobre / Termos de Uso"
Objetivo: Fornecer um detalhamento completo das limitações e responsabilidades, servindo como um termo de referência formal dentro da aplicação.
Localização Sugerida:
Em um item de menu, talvez dentro das "Configurações" ou em um link "Sobre" na AppBar. Pode abrir um AlertDialog ou uma nova view.
Texto Sugerido (mais detalhado):
Diretrizes de Uso e Limitações da IA
Ao utilizar o Docs Analyzer, você concorda e compreende os seguintes pontos:
Ferramenta de Suporte: A IA é um assistente para otimizar a análise preliminar de documentos. Ela não substitui a expertise, o julgamento crítico e a decisão final do analista humano.
Verificação Obrigatória: É de sua inteira responsabilidade verificar, corrigir e validar todas as informações extraídas, classificadas e resumidas pela IA. Os resultados podem conter imprecisões, omissões ou erros.
Alucinações e Vieses: Modelos de linguagem podem gerar informações que parecem factuais, mas não estão presentes no documento original (alucinações) ou refletir vieses contidos em seus dados de treinamento. Redobre a atenção em dados críticos como nomes, datas, valores e tipificações.
Responsabilidade (Accountability): Todas as ações, decisões e documentos oficiais gerados a partir do uso desta ferramenta são de responsabilidade exclusiva do usuário que os executa e subscreve. O sistema registra métricas de uso para fins de auditoria e aprimoramento.
Não é Aconselhamento Jurídico: As tipificações penais e classificações sugeridas pela IA são baseadas em padrões e não constituem parecer ou aconselhamento jurídico formal. A decisão final sobre o enquadramento legal cabe à autoridade competente.

======================================================================================

> Tests pdf_processor.py, ai_orchestrator.py, doc_generator.py
> Test  View: analyze_pdf1

# TODO: Posteriormente: 
> Exibir prompt_estruturado editável;
> Melhorias na apresentação dos metadados: coluna em vez de lista única?
> Rever lógica do modo de filtro 'get_pages_among_similars_groups'

# AVALIAR:
> Reorganização de InternalAnalysisController: passar para outro módulo?
> Reorganização de FeedbackWorkflowManager: incorporar à FeedbackDialog?

============================================================================================================================
