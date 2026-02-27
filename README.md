# CRM Spagi - Gerenciador de Leads e Vendas

Sistema completo de CRM (Customer Relationship Management) focado no setor automóvel. A plataforma gerencia todo o ciclo de vida do cliente, desde a captação do lead, distribuição entre vendedores, avaliação de veículos, propostas de financiamento até ao fecho da venda e emissão de contratos.

## 🚀 Funcionalidades Principais

O sistema é modular e composto pelas seguintes aplicações:

- **Gestão de Clientes (`clientes`):** Cadastro completo, histórico de interações, controle de status e relatórios de clientes em atraso.
- **Controle de Vendas (`vendas_produtos`):**
  - Registro de vendas de veículos, seguros, garantias e serviços de despachante.
  - **Cálculo automático de comissões**, incluindo lógica de "Split" (divisão de comissão com vendedor ajudante).
  - Geração de comprovantes e relatórios de desempenho.
- **Avaliação de Veículos (`avaliacoes`):** Integração com API FIPE para precificação precisa e gerador de anúncios em massa.
- **Distribuição de Leads (`distribuicao`):** Sistema inteligente (rodízio) para distribuir novos leads equitativamente entre os vendedores disponíveis.
- **Financiamentos (`financiamentos`):** Acompanhamento visual de propostas bancárias via quadro **Kanban**.
- **Gestão Documental (`documentos`):** Geração automática de PDFs (Procurações, Contratos, Termos) preenchidos dinamicamente com dados do cliente.
- **Painel Administrativo (`usuarios` & `core`):** Controle de acesso, perfis de usuário (Gerente/Vendedor/Admin), avatares e dashboards.
- **Notificações (`notificacoes`):** Alertas automáticos sobre inatividade de leads ou tarefas pendentes.
- **Marketing & TV (`leadge`):** Gestão de banners e modo "TV" para exibição de ofertas e vídeos em telas da loja.

## 🛠️ Tecnologias Utilizadas

- **Backend:** Python, Django 5.x
- **Banco de Dados:** PostgreSQL (Recomendado para produção) / SQLite (Dev)
- **Frontend:** HTML5, CSS3 (Bootstrap), JavaScript
- **Infraestrutura:** Docker, Gunicorn, Nginx
- **Outros:** WeasyPrint (PDFs), Integrações API Rest

## ⚙️ Pré-requisitos

- [Docker](https://www.docker.com/) e Docker Compose
- Ou Python 3.10+ instalado localmente

## 📦 Como Rodar o Projeto

### Opção 1: Usando Docker (Recomendado)

1. **Clone o repositório:**
   ```bash
   git clone [https://github.com/seu-usuario/gerenciador-leads.git](https://github.com/seu-usuario/gerenciador-leads.git)
   cd gerenciador-leads
   ```

2. **Configure as variáveis de ambiente: Copie o arquivo de exemplo e ajuste conforme necessário.**
    ```bash
    cp .env.example .env
    ```

3. **Suba os containers:**
    ```bash
    docker build -t crmspagi .
    docker run -p 8000:8000 --env-file .env crmspagi
    ```

(Nota: Para um ambiente completo com banco de dados, recomenda-se usar um docker-compose.yml)

### Opção 2: Instalação Manual (Local)

1. **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Linux/Mac
    source venv/bin/activate
    ```
2. **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```
3. **Configure o banco de dados e migrações:**
    



