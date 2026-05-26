
### 🖥️ PARTE 1: Esqueleto para Confecção dos Slides (Atualizado)

*   **Slide 1: Capa** (Título e Subtítulo).
*   **Slide 2: O que é o ÓPERA? (Vídeo)** (Player embutido de 5min).
*   **Slide 3: Primeiro Acesso (Cadastro e Dica do Spam)**
    *   Aviso do Spam da Microsoft. Ação: Enviar e-mail em branco para `sec.cor.pf.sp@gmail.com`.
*   **Slide 4: Links de Acesso** (Rede Interna 10.11.8.25:8550 e VPN).
*   **Slide 5: Motores de IA e Segurança**
    *   Lado A: **Qwen3-8B (Local DTI)** -> Gratuito, para dados sigilosos (Atenção ao limite de páginas!).
    *   Lado B: **OpenAI API (ChatGPT)** -> Custo próprio, para dados ostensivos.
*   **Slide 6: Status MVP e Contato**
    *   O sistema está em evolução (em refatoração). Podem ocorrer instabilidades.
    *   Seu e-mail / Teams para dúvidas e reportar bugs.

---

### 📋 PARTE 2: Esqueleto de Tópicos (Guia do Apresentador)

1.  **Abertura:** Apresentar objetivo e rodar o Vídeo (5m).
2.  **Cadastro & Acesso:** Explicar Spam (e-mail em branco) e mostrar IPs. (5m)
3.  **Demo 1: Análise NC - Upload e Settings:** (10m)
    *   Fazer Upload e abrir *Settings Drawer*.
    *   Vetorização: TF-IDF x Embeddings (para arquivos grandes).
    *   LLMs: Qwen local (sigilo) x OpenAI (mercado). (Passo a passo API no chat).
    *   **Aviso Importante (Limites do Qwen):** Mostrar campo *"Limite Tokens Input"*. Explicar que 32k teóricos = ~12k úteis (aprox. 20 páginas). Se der erro de contexto, ensinar a baixar esse campo para 10k-12k para forçar o truncamento inteligente.
    *   Outros parâmetros (temperatura, etc): Sugerir não mexer.
4.  **Demo 1: Análise NC - Execução e Exportação:** (10m)
    *   Processar -> Analisar -> Revisar campos editáveis.
    *   Explicar importância da janela de Feedback.
    *   Exportar DOCX (Templates).
5.  **Demo 2: Chat com Documento:** (10m)
    *   Mostrar Settings do Chat.
    *   Dica: Esforço de reflexão *'minimal'* no Qwen desliga modo pensante (mais rápido).
    *   Fazer pergunta cruzando dados do PDF.
6.  **Avisos Finais & Dúvidas:** (5m)
    *   Aviso de MVP: Bugs se resolvem com *Logout + Login* no momento.
    *   Abertura para perguntas.

---

### 🎙️ PARTE 3: Roteiro Completo e Detalhado

#### 1. Abertura e Vídeo (5 min)
**[Slide 1]** "Bom dia. Hoje vamos conhecer o ÓPERA, nossa plataforma de IA Assistente. Para nivelarmos o que o sistema faz, preparei um vídeo rápido de 5 minutos que resume a ideia e mostra o fluxo. Vamos assistir."
**[Slide 2]** *(Toca o Vídeo).*

#### 2. Cadastro e Problema do Spam (5 min)
**[Slide 3]** "Como viram, o potencial é grande. O sistema exige cadastro com e-mail institucional. Porém, o filtro de spam corporativo está bloqueando o e-mail de ativação de conta. 
Para resolver isso agora: enviem um **e-mail em branco** para `sec.cor.pf.sp@gmail.com`. Isso ensina ao Outlook que o remetente do nosso sistema é seguro."
**[Slide 4]** "Para acessar, temos dois endereços: `10.11.8.25:8550` na rede cabeada, ou `http://10.11.8.25/` pela VPN Cisco."

#### 3. Demonstração: Análise de Notícia-Crime e Configurações (15 min)
*(Compartilha a tela com o ÓPERA aberto)*

"Vou carregar um PDF de exemplo." *(Faz o upload)*.
"Antes de processar, vamos na **engrenagem de Configurações**. Aqui ajustamos o cérebro do sistema." *(Abre o Settings Drawer).*

**[Vetorização]**
"O primeiro ponto é o *Modelo de Vetorização*. Por padrão é semântico, mas você pode mudar para **TF-IDF**, que é mais rápido. Isso só afeta a otimização de arquivos gigantescos, ajudando a descartar páginas inúteis."

**[LLMs e Segurança]**
"Abaixo, o Provedor LLM. Hoje temos o **Qwen3-8b**, hospedado pela DTI. Ele não acessa a internet externa, então **é ele que usamos para dados sigilosos**.
Se o dado for ostensivo e você quiser mais inteligência, o sistema aceita a API da **OpenAI (ChatGPT)**. É muito barato, 5 dólares rendem meses. Deixarei um tutorial no chat de como gerar essa chave."

**[⚠️ O Limite de Contexto do Qwen e o Ajuste de Tokens]**
"Agora, muita atenção a este campo aqui: **Limite Tokens Input**. 
O modelo Qwen da PF tem um limite de 'memória' de leitura por vez. Na prática, descontando o espaço das instruções do sistema, sobram cerca de **12 mil tokens** para o seu documento, o que dá umas **20 páginas**.
Se você colocar um inquérito de 100 páginas, ele vai dar o erro *'Limite de contexto atingido'*. Como contornar isso? Você vem exatamente neste campo (*Limite Tokens Input*) e ajusta para **10.000 ou 12.000**. Com isso, o ÓPERA vai fatiar o PDF e mandar para a IA apenas as partes mais vitais, evitando o erro.
Os demais campos aqui, como Temperatura e Verbosidade, sugiro não mexerem por enquanto."

#### 4. Execução, Revisão, Feedback e Exportação (10 min)
*(Fecha a configuração e clica em "Processar" -> "Solicitar Análise")*

"A IA processou e preencheu nosso formulário. Notem que o analista tem o controle. Se a IA errou uma tipificação penal, eu altero aqui. 
Ao pedir para exportar, o sistema exibe a janela de **Feedback**. Ele calcula o que você corrigiu e o que você aceitou. **Por favor, não ignorem essa tela.** Esses dados subsidiam a melhoria do modelo Qwen."

"Em **Exportar**, posso gerar um Word simples ou carregar o **Template** da sua delegacia. O sistema insere os dados da IA direto nos locais marcados."

#### 5. Módulo Chat com Documentos (5 min)
"Vamos para o **Chat Documentos**." *(Carrega um PDF).*
"Aqui você faz perguntas livres sobre o documento. Abrindo as configurações, a diferença é o *System Prompt* (instruções de comportamento da IA).

**Dica de ouro para o modelo Qwen:** Ele é um modelo 'pensante', que raciocina antes de responder. Se você quiser que o Chat seja mais rápido e direto, mude o 'Esforço de reflexão' para **Minimal**. Isso desliga o modo pensante e a resposta vem quase na hora." *(Faz a demonstração).*

#### 6. Expectativas, Limitações e Encerramento (5 min)
**[Slide 6 - Status MVP]**

"Para encerrar: o ÓPERA é um MVP (Produto Mínimo Viável). Estou fazendo uma refatoração no código para deixá-lo mais estável e lançar novos módulos (como Banco de Pareceres).
Por enquanto, se um botão não responder ou a tela travar: o remédio rápido é dar um **Logout e Login novamente**.

Testem na prática, usem nas demandas reais e me mandem mensagens no Teams com bugs e sugestões. O sistema é feito para nós. Alguém tem alguma dúvida?" *(Abre para Q&A).*