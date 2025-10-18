import requests
from django.shortcuts import render, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from .models import Avaliacao, AvaliacaoFoto
from .forms import AvaliacaoForm, FotoUploadForm
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json 
import re 
from bs4 import BeautifulSoup 
from requests.exceptions import RequestException, Timeout 

# --- MÓDULOS GEMINI ---
from django.conf import settings
try:
    from google import genai
    from google.genai.errors import APIError
    GEMINI_CLIENT = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
except ImportError:
    GEMINI_CLIENT = None
except ValueError:
    GEMINI_CLIENT = None


# --- LÓGICA DE EXTRAÇÃO WEB (SCRAPER ROBUSTO COM TRATAMENTO DE TIMEOUT) ---
def scrape_multipla_url(url):
    """
    Extrai a lista de descrições dos veículos da URL, utilizando os seletores
    identificados no código-fonte do Spagi Motors, com tratamento de erros robusto.
    """
    car_descriptions = []
    
    if not url.startswith('http'):
        url = 'https://' + url
        
    try:
        # 1. Faz a requisição HTTP com timeout AUMENTADO (30s)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=30, headers=headers) 
        response.raise_for_status() # Lança erro se o status code for 4xx ou 5xx
        
        # 2. Parseia o conteúdo HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
    except Timeout as e:
        # TRATAMENTO ESPECÍFICO PARA TIMEOUT (EVITA O ERRO 500)
        raise Exception(f"ERRO DE TEMPO LIMITE (Timeout): O servidor demorou demais para responder após 30 segundos. Verifique sua conexão ou a disponibilidade do site de destino. Detalhes: {e}") 
    except RequestException as e:
        # Tratamento para outros erros de rede/HTTP (ex: 404, 503)
        raise Exception(f"Falha de Rede ou HTTP ao acessar o estoque: {e}") 
    except Exception as e:
        # Tratamento para erros de parsing do BeautifulSoup ou outros
        raise Exception(f"Erro ao processar o HTML da página: {e}")

    # 3. ENCONTRA TODAS AS LISTAGENS DE CARROS
    car_listings = soup.find_all('div', class_='carro', recursive=True)
    
    if not car_listings:
        return []
    
    for car in car_listings:
        try:
            # 4. EXTRAÇÃO DE DADOS POR ITEM (COM CHECAGEM ROBUSTA DE NONE)
            first_name = car.select_one('.first-name').get_text(strip=True) if car.select_one('.first-name') else ''
            last_name = car.select_one('.last-name').get_text(strip=True) if car.select_one('.last-name') else ''
            model_year = car.select_one('.year').get_text(strip=True) if car.select_one('.year') else ''
            
            city_tag = car.select_one('.vitrine-cidade')
            city_location_full = city_tag.get_text(strip=True) if city_tag else 'Cidade Não Informada'
            
            city_location = re.sub(r'\s*\([A-Z]{2}\)$', '', city_location_full, flags=re.IGNORECASE).strip()

            optionals = car.select('.opicionais .text-none.grey-text10')
            
            km_text = next((opt.get_text().strip() for opt in optionals if 'km' in opt.get_text().lower()), 'KM Não Informado')
            fuel_text = next((opt.get_text().strip() for opt in optionals if any(f in opt.get_text().lower() for f in ['flex', 'gasolina', 'diesel', 'álcool'])), 'Combustível Não Informado')
            
            model_name = f"{first_name} {last_name}".strip()
            
            if not model_name or not model_year:
                continue

            # 5. Monta a string
            full_description = (
                f"{model_name.upper()} {model_year} | {fuel_text.upper()} | {km_text.upper()} em {city_location.title()} - Spagi Motors"
            )
            
            car_descriptions.append(full_description)

        except Exception:
            # Captura exceções para este item específico (e.g., tag inesperada), 
            # e garante que o loop continue para o próximo item
            continue

    return car_descriptions

# --- LÓGICA CENTRAL DE GERAÇÃO (COM GEMINI) ---
def generate_high_conversion_description(vehicle_description, marketplace='Facebook Marketplace'):
    """
    Usa o Gemini API para gerar uma descrição de alta conversão.
    Assegura a remoção de "novo" e "garantia de fábrica".
    """
    if not GEMINI_CLIENT:
        return "⚠️ Erro de Configuração: API Key do Gemini não encontrada ou biblioteca ausente. Verifique .env e requirements.txt."

    # 1. Monta o prompt e a instrução
    system_instruction = (
        "Você é um Copywriter de alta performance para concessionárias de veículos. "
        "Sua tarefa é transformar a descrição bruta de um veículo em um anúncio irresistível para o "
        "Facebook Marketplace, focado em alta conversão e chamadas para ação. "
        "Utilize emojis, separe o texto em parágrafos de fácil leitura e crie uma seção de hashtags. "
        "O anúncio deve ter um tom de urgência e destaque benefícios de compra (ex: troca, financiamento)."
        "REGRA CRÍTICA: NÃO inclua as palavras 'novo' ou 'garantia de fábrica' em nenhuma variação. "
        "Substitua 'novo' por termos como 'impecável', 'estado de zero' ou 'excelente estado'."
    )
    
    user_prompt = f"Gere o anúncio com base na seguinte descrição do veículo e contexto da concessionária:\n\n{vehicle_description}"
    
    # 2. Chama a API do Gemini
    try:
        response = GEMINI_CLIENT.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_prompt,
            config={"system_instruction": system_instruction},
        )
        
        descricao_bruta = response.text
        
    except APIError as e:
        print(f"Erro na API do Gemini: {e}")
        return f"⚠️ Erro ao chamar a IA (API Error): {e}. Verifique o status da chave."
    except Exception as e:
        # Este handler irá capturar timeouts ou outros erros de comunicação da biblioteca.
        print(f"Erro inesperado no Gemini request: {e}")
        return f"⚠️ Erro de Comunicação com a IA: O serviço Gemini falhou ao responder. Detalhes: {type(e).__name__}"

    # 3. LÓGICA DE EXCLUSÃO OBRIGATÓRIA (Pós-processamento de segurança)
    descricao_limpa = descricao_bruta
    
    # Padrões para remover variações de "novo" e "garantia de fábrica"
    palavras_chave = [
        r'\bnov[oa]s?\b', # novo, nova, novos, novas
        r'\bgaranti[aae] de f[aá]brica\b'
    ]
    
    for termo in palavras_chave:
        descricao_limpa = re.sub(termo, ' ', descricao_limpa, flags=re.IGNORECASE)

    # Limpa espaços e quebras de linha duplas
    descricao_limpa = re.sub(r'\s{2,}', ' ', descricao_limpa).strip()
    descricao_limpa = re.sub(r'\n\s*\n', '\n\n', descricao_limpa)
    
    return descricao_limpa.strip()


@login_required
def gerador_anuncio_view(request):
    """
    View para a página de geração de anúncios (single).
    """
    context = {}
    generated_description = None
    input_text = request.GET.get('vehicle_description', '')
    
    if request.method == 'GET' and input_text:
        try:
            generated_description = generate_high_conversion_description(input_text)
            
            # Verifica se houve um erro retornado pela função de geração
            if "⚠️ Erro" in generated_description:
                 messages.error(request, generated_description)
            else:
                messages.success(request, "Descrição de alta conversão gerada com sucesso pela IA Gemini! Copie e cole no seu anúncio.")
                
        except Exception as e:
            messages.error(request, f"Erro inesperado no view: {e}")

    context['generated_description'] = generated_description
    context['input_text'] = input_text
    
    return render(request, 'avaliacoes/gerador_anuncio.html', context)


@login_required
def bulk_gerador_anuncio_view(request):
    """
    View para a geração em massa de anúncios, que agora trata as exceções de scraping.
    """
    context = {}
    
    # Define a URL padrão (e fallback) para o scraping
    external_url = "https://spagimotors.com.br/multipla"
    
    if request.method == 'POST':
        # Captura a URL fornecida pelo usuário, se houver
        user_provided_url = request.POST.get('external_url')
        if user_provided_url:
            external_url = user_provided_url
        
        car_list = []
        try:
            # 1. EXTRAÇÃO DOS DADOS (Chamada à função de scraping com tratamento de erro)
            car_list = scrape_multipla_url(external_url)
            
        except Exception as e:
            # Captura a exceção levantada pela função de scraping e a exibe
            messages.error(request, f"Erro fatal de scraping: Não foi possível processar a página. Detalhes: {e}")
            # Retorna o formulário com a mensagem de erro (EVITA O ERRO 500)
            return render(request, 'avaliacoes/bulk_gerador_anuncio_form.html', context)


        if not car_list:
             messages.error(request, f"Não foi possível encontrar nenhum veículo na URL: {external_url}. Verifique o link e se a página carrega corretamente.")
             return render(request, 'avaliacoes/bulk_gerador_anuncio_form.html', context)

        generated_announcements = []
        error_count = 0
        
        # 2. GERAÇÃO DOS ANÚNCIOS COM GEMINI
        for car_description in car_list:
            announcement = generate_high_conversion_description(car_description)
            
            if "⚠️ Erro" in announcement:
                error_count += 1
                generated_announcements.append({
                    'title': car_description,
                    'description': announcement 
                })
            else:
                generated_announcements.append({
                    'title': car_description,
                    'description': announcement
                })

        context = {
            'generated_announcements': generated_announcements,
            'external_url': external_url,
            'total_generated': len(generated_announcements),
        }
        
        if error_count > 0:
            messages.warning(request, f"Foram processados {len(generated_announcements)} anúncios, mas {error_count} falharam devido a um erro da API Gemini. Verifique as mensagens.")
        else:
            messages.success(request, f"Foram gerados {len(generated_announcements)} anúncios com sucesso pela IA Gemini!")
            
        return render(request, 'avaliacoes/bulk_gerador_anuncio.html', context)
        
    return render(request, 'avaliacoes/bulk_gerador_anuncio_form.html', context)


class AvaliacaoListView(LoginRequiredMixin, ListView):
    model = Avaliacao
    template_name = 'avaliacoes/avaliacao_list.html'
    context_object_name = 'avaliacoes'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            status='disponivel',
            data_criacao__gte=timezone.now() - timedelta(days=30)
        )
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(modelo__icontains=query) |
                Q(marca__icontains=query) |
                Q(ano__icontains=query) |
                Q(placa__icontains=query)
            )
        sort = self.request.GET.get('sort')
        if sort == 'antigo':
            queryset = queryset.order_by('data_criacao')
        else:
            queryset = queryset.order_by('-data_criacao')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['sort_order'] = self.request.GET.get('sort', 'novo')
        return context

class AvaliacaoCreateView(LoginRequiredMixin, CreateView):
    model = Avaliacao
    form_class = AvaliacaoForm
    template_name = 'avaliacoes/avaliacao_form.html'
    success_url = reverse_lazy('avaliacao_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['foto_form'] = FotoUploadForm()
        return context

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        foto_form = FotoUploadForm(request.POST, request.FILES)
        if form.is_valid() and foto_form.is_valid():
            return self.form_valid(form, foto_form)
        else:
            return self.render_to_response(
                self.get_context_data(form=form, foto_form=foto_form)
            )

    def form_valid(self, form, foto_form):
        avaliacao = form.save(commit=False)
        avaliacao.cadastrado_por = self.request.user
        avaliacao.save()
        
        self.object = avaliacao

        files = self.request.FILES.getlist('fotos')
        try:
            for f in files[:20]:
                AvaliacaoFoto.objects.create(avaliacao=self.object, foto=f)
        except Exception as e:
            print(f"ERRO AO SALVAR ARQUIVO: {e}")
            pass
        return redirect(self.success_url)

class AvaliacaoDetailView(LoginRequiredMixin, DetailView):
    model = Avaliacao
    template_name = 'avaliacoes/avaliacao_detail.html'
    context_object_name = 'avaliacao'

class AvaliacaoUpdateView(LoginRequiredMixin, UpdateView):
    model = Avaliacao
    form_class = AvaliacaoForm
    template_name = 'avaliacoes/avaliacao_form.html'
    def get_success_url(self):
        return reverse_lazy('avaliacao_detail', kwargs={'pk': self.object.pk})

class AvaliacaoDeleteView(LoginRequiredMixin, DeleteView):
    model = Avaliacao
    template_name = 'avaliacoes/avaliacao_confirm_delete.html'
    success_url = reverse_lazy('avaliacao_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def get_fipe_marcas(request, tipo_veiculo):
    try:
        response = requests.get(f'https://parallelum.com.br/fipe/api/v1/{tipo_veiculo}/marcas')
        response.raise_for_status()
        return JsonResponse(response.json(), safe=False)
    except requests.RequestException:
        return JsonResponse({'error': 'Erro ao buscar marcas'}, status=500)

def get_fipe_modelos(request, tipo_veiculo, marca_id):
    try:
        response = requests.get(f'https://parallelum.com.br/fipe/api/v1/{tipo_veiculo}/marcas/{marca_id}/modelos')
        response.raise_for_status()
        return JsonResponse(response.json().get('modelos', []), safe=False)
    except requests.RequestException:
        return JsonResponse({'error': 'Erro ao buscar modelos'}, status=500)

def get_fipe_anos(request, tipo_veiculo, marca_id, modelo_id):
    try:
        response = requests.get(f'https://parallelum.com.br/fipe/api/v1/{tipo_veiculo}/marcas/{marca_id}/modelos/{modelo_id}/anos')
        response.raise_for_status()
        return JsonResponse(response.json(), safe=False)
    except requests.RequestException:
        return JsonResponse({'error': 'Erro ao buscar anos'}, status=500)