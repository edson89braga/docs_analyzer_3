Roteiro prático:

1) Apresentação - EPF Edson - COR/SP

1.1) A ideia dessa reunião é mostrar o Programa Ópera, de forma prática. 
     Em específico, seu primeiro módulo funcional, com foco em recepção e análise de notícias-crime e outros documentos (que chegam à PF através da corregedoria ou descentralizadas).
	 
     Antes de acessar o sistema e exibir o fluxo de trabalho possível, vou repassar aqui um vídeo de 5 minutos que faz uma apresentação geral da Aplicação; 
	 Em seguida, a gente mostra na prática.

2) [Vídeo-introdução]

3) Bom, com esse vídeo já dá pra ter um panorama geral da aplicação. 

3.1) Agora, a gente vai passar por todo o sistema na prática.
     Quaisquer dúvidas, vocês podem levantar a mãozinha aqui do Teams ou, de preferência, anotar para a gente responder ao final.

4) [Slide 1: URLs de acesso]

4.1) Para acessar a aplicação, quem estiver na rede cabeada da PF usa o endereço '10.11.8.25:8550' — como está no slide, deixei anotado no chat também. 
     Quem estiver pela VPN usa o mesmo endereço, mas sem a porta: apenas '10.11.8.25'.

4.2) Quem quiser, pode acessar agora em tempo real pra acompanhar a apresentação. 
     O sistema pede um cadastro com e-mail da PF e, logo depois, vocês vão receber um e-mail de ativação vindo do endereço 'sec.cor.pf.sp@gmail.com'. 
     
     Para evitar que o Outlook bloqueie esse remetente, vale mandar um e-mail em branco para esse endereço antes — assim ele fica liberado na sua caixa.

5) [Login + interface inicial (no tema claro)]

6) Essa é a tela inicial. A interface é bem direta: o que tem de substancial é o menu lateral à esquerda. 
   Temos o módulo de Análise, que é o nosso foco hoje, e o módulo de Chat com Documentos, que também vou mostrar. 
   Os demais ícones representam funcionalidades que estão no mapa de intenções, mas ainda não foram desenvolvidadas.

7) Vamos ao módulo de "Análise".

7.1) O 1º botão permite o upload do PDF da notícia-crime — um ou mais arquivos, caso o documento esteja particionado.

7.2) Na sequência, o 2º botão comanda a extração do conteúdo do PDF.

	Esse processamento tem 2 objetivos:
	  1º - Eliminar páginas excessivamente redundantes ou duplicadas, otimizando o contexto que vai ser enviado para a IA.
	  2º - Fazer um truncamento (corte) de conteúdo se o total do documento for maior do que suporta a janela de contexto da IA.

    Após a extração, o sistema exibe alguns metadados:
     ['tokens' é a forma como a IA mede o tamanho do conteúdo]
     - total de tokens do documento original, 
     - total de tokens selecionados, e 
     - um indicativo de páginas sem conteúdo extraído — o que pode sinalizar a necessidade de tratamento por OCR.
    
    [Mostrar o exemplo de páginas escaneadas (ininteligíveis)]
    
    A maioria dos PDFs hoje são nato-digitais, mas ainda recebemos documentos digitalizados. 
    O analista precisa avaliar se as páginas não extraídas podem comprometer a análise e, se for o caso, fazer o tratamento de OCR antes do upload.
	  

8) O 3º botão solicita a análise do conteúdo para o modelo de IA.
   [Abrir drawer_settings ANTES de solicitar análise, pois esta trava a gui]
   Vou solicitar a análise, e enquanto ele processa vou mostrar através do último botão à direita as configurações que temos disponíveis aqui.

9) A primeira configuração diz respeito à etapa de extração: essa dupla aqui de 'modelo de vetorização' + 'limiar de similaridade'
    
    Esse parâmetro define o algoritmo usado para identificar e eliminar páginas redundantes.
    A opção padrão, TF-IDF, compara o conteúdo bruto das páginas; enquanto essa segunda opção utiliza a carga semântica do conteúdo.

    Não vou adentrar a explicação técnica desses algoritmos, mas sugiro que deixem sempre na opção padrão 'tf-idf';
    A menos que queiram testar as diferenças de comportamento na prática.

10) As outras configurações definem o modelo de IA utilizado como motor da análise.

10.1) Inicialmente a aplicação foi moldada para usar a API da OpenAI, que provê os mesmos modelos de LLM do chatGPT.
      Por 'LLM' entendam 'IA', são sinônimos..

      Ano passado, iniciou-se lá em brasília estudos para contratação dos serviços da OpenAI, que a princípio seria utilizado no SEI, tal como ocorre em alguns outros orgãos;
      Mas parece que não teve evolução até o momento.

      Em paralelo, a DTI adquiriu algumas máquinas com GPUs para processamento de Inteligência Artifical Local, e então desde dezembro disponibilizaram uma API para uso desse modelo Local.

10.2) Então, hoje, constam aqui duas opções: os modelos da OpenAI — GPT-4.1, GPT-4.1-mini — e o modelo local da PF, Qwen3.

10.3) Em tese, é possível usar os modelos da OpenAI aqui, basta cadastrar uma chave de API.

      Porém, acabou de ser publicada a Portaria do MGI nº 3485/2026: Política de Governança sobre IA, 
      e ela proíbe expressamente o compartilhamento de dados sigilosos, pessoais ou sensíveis com plataformas externas que não estejam sob garantias contratuais.
      
      Contudo, se você for trabalhar com documentos que não sejam sigilosos ou sensíveis, o que é exceção no nosso caso né... é possível usar os modelos da OpenAI pela aplicação.

11) As últimas configurações — temperatura, esforço de reflexão, verbosidade — alteram o comportamento de resposta da IA. A recomendação é deixar nos valores padrão.

11.1) O que exige atenção é o campo 'Limite de Tokens no Input'. 
      O modelo atualmente disponibilizado pela PF, Qwen3, tem uma janela de contexto pequena. 
      Na prática, isso limita o uso pleno a documentos de cerca de 20 páginas, Em média. 
      
      Então, vocês vão precisar baixar esse valor para no máximo 15 mil tokens, talvez 12mil. 
      Se não fizerem isso e submeterem um arquivo grande, o sistema vai retornar um erro de contexto excedido.

      Com o limite ajustado, a aplicação faz o truncamento automático: 
       isso é, seleciona as páginas mais relevantes até o teto disponível, descartando o excedente.

11.2) Sobre o esforço de reflexão: 
      O Qwen3 é um modelo pensante — ele raciocina antes de responder. 
      Se deixar em Mínimo, você desliga esse modo pensante e as respostas ficam mais rápidas, porém "menos inteligentes".
      Qualquer outro grau mantém o raciocínio ativo. 
      Para análise, vale manter sempre ativo esse modo pensante.

12) Agora vamos ver o resultado da análise:
    
    Esse módulo representa um agente de IA com escopo específico: analisar notícias-crime e documentos similares. 
    
    Então, ele segue um prompt estruturado para extrair exatamente o que precisamos preencher no ePol para autuação:
    - dados de origem, tipo de documento, orgão remetente;
    - dados dos fatos sob análise: resumo, município e uf do local de ocorrência, valores envolvidos, relação de pessoas citadas,
    - agrega tambem uma linha do tempo de eventos que constem no documento; e
    - traz como bloco principal a análise e enquadramento do crime noticiado:
      - área de atribuição, 
      - tipificação penal, 
      - eventual enquadramento em temas do prometheus, 
      - sugestão de conversão em NC, NCV ou RE, assunto de RE se for o caso, e
      - destinação à delegacia responsável.
    - tudo baseado nas regras das INs 255 e 270.

13) O prompt que a IA está seguindo pode ser verificado nesse ponto...
    [Demonstrar blocos rapidamente]

    O prompt é passível de melhorias e pode evoluir continuamente conforme necessidade verificada e testada.
    focar no bloco F, que traz critérios específicos para classificação.
    
    [Por exemplo: ... citar item que corrigiu atribuição do município de fato para casos com apreensões em locais distintos]

    Então, vejam que pequenos incrementos no prompt pode fazer a IA acertar respostas que estavam divergindo da análise final.

    Atualmente, vocês podem fazer alterações no prompt para fins de teste. 
    
    mostrar na tela -> mas o prompt alterado vai ser usado somente na proxixma análise; Depois retorna o prompt original.

    Por enquanto, para peristir alterações válidas no prompt, vcs me chamem no Teams que eu salvo na Aplicação.

14) Retornando para a análise, após revisão de todos os campos pelo analista, a gente pode prosseguir para exportação da informação;

14.1) A exportação pode ser ser feita para um docx simples ou pode usar um modelo próprio de informação ou minuta de despacho;

14.2) Mas antes de exportar, a aplicação solicita um feedback da análise.
      Na verdade, é um feedback automático baseado nas edições feitas sobre o resultado original. [mostrar]
      
      É importante confirmar esse feedback pra gente ir computando quão eficiente está sendo o modelo de IA, e assim propor alterações e evoluções.

[Mostrar docx simples gerado]

14.3) Como eu disse, Também podemos exportar para modelos próprios;
      [Mostrar modelo exemplo já carregado]

14.4) E vocês também podem adicionar os modelos específicos de vocês.
      Basta carregar o arquivo, que ficará salvo na aplicação.
      Esse arquivo é um docx de Word qualquer, basta que no modelo tenham essas chaves indicando aonde devem ser coladas as respostas da IA.

      Pra quem é mais antigo como eu, isso é semelhante a sistemática de mala-direta que a gente fazia entre word e excel pra produção de documentos repetidos com a mesma estrutura.

15) Esse último botão reinicia a interface pra prosseguir para nova análise, carregando novo documento, e repetindo o fluxo.

16) Bem, com isso, a gente encerra a demonstração do ciclo de uso do módulo de análise de notícias-crime.

==========

17) Vou mostrar também, rapidamente, o chat com documentos, 
    É um chatbot simples — semelhante ao Copilot ou ao ChatGPT direto —, 
    mas vinculado ao modelo local da DTI e a um documento específico carregado pelo usuário.

17.1) Então, a partir do momento que você carrega um documento, você pode iniciar a conversa com a IA
      [Alterar a configuração de reflexão para 'mínimo', e interagir com o bot exemplificando o uso]
      
      Para perguntas básicas de extraçao de informação, vale a pena desligar o esforço pensamento; Assim as respostas vem mais rápidas. 
      Para perguntas mais complexas, deixem ativo o modo pensante (selecionado qualquer outro grau no campo 'esforço de reflexão').

17.2) As opções de configuração aqui são as mesmas do módulo de análise, mas acrescenta o system-prompt seguido pelo chatbot, que pode ser alterado.
      [Mostrar na tela]

17.3) Também tem algumas opções embutidas no chat:
     - copiar reposta;
     - Editar; exlcuir itens;
     - também pode retroceder a conversa para um ponto anterior; 
     - ou solicitar uma nova reposta sobre o mesmo tópico.

17.4) Ao final da interação, podemos encerrar o chat pra começar nova conversa.

     E é isso...

18) Por fim, vale citar algumas limitações conhecidas:
    - PDFs sem ocr, PDFs bloqueados, PDFs com ofuscamento;
    - Qwen3: janela de contexto pequena.


19) Alguém tem alguma pergunta?

20) Para encerrar, devo dizer que o programa foi desenvolvido e está disponível em caráter de MVP (produto mínimo viável).
    Atualmente estou trabalhando na refatoração da aplicação, pra termos uma versão escalável e apta a evoluir para novas funcionalidades.

    Testem na prática, usem nas demandas reais;
    e quaisquer bugs, sugestões ou dúuvidas, podem me chamar diretamente aqui no Teams, estou sempre online.
