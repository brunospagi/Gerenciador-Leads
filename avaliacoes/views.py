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

# --- WEB SCRAPING LIBRARIES ---
from bs4 import BeautifulSoup
from requests.exceptions import RequestException

# --- MÓDULOS GEMINI ---
from django.conf import settings
try:
    from google import genai
    from google.genai.errors import APIError
    # Inicializa o cliente com a chave das configurações
    GEMINI_CLIENT = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
except ImportError:
    # Caso a dependência google-genai não esteja instalada
    GEMINI_CLIENT = None
except ValueError:
    # Caso a chave da API não esteja configurada corretamente
    GEMINI_CLIENT = None


# --- LÓGICA DE EXTRAÇÃO WEB (IMPLEMENTAÇÃO DO SCRAPER) ---
def scrape_multipla_url(url):
    """
    Extrai a lista de descrições completas dos veículos da URL, utilizando os seletores
    identificados no código-fonte do Spagi Motors.
    """
    car_descriptions = []
        
    try:
        # 1. Realiza a requisição HTTP
        # Adiciona header para simular um navegador e evitar bloqueio
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
    except RequestException as e:
        print(f"Erro ao acessar a URL {url}: {e}")
        return []
    except Exception as e:
        print(f"Erro inesperado no scraping: {e}")
        return []

    # Seletor do item principal: div com a classe 'carro' (contém todos os dados do veículo)
    # Baseado na estrutura: <div class="carro col-md-3 col-result-pact" ...>
    car_listings = soup.find_all('div', class_='carro', recursive=True)

    for car in car_listings:
        try:
            # 1. Extração de Componentes do Título e Dados Principais
            # A informação do veículo está em h2.tit-marca > a > div.first-name e div.last-name
            
            first_name_tag = car.select_one('.first-name')
            last_name_tag = car.select_one('.last-name')
            year_tag = car.select_one('.year')
            city_tag = car.select_one('.vitrine-cidade')
            
            # 2. Opcionais (Km e Combustível) - Busca pelos textos nos blocos de opcionais
            optionals = car.select('.opicionais .text-none.grey-text10')
            
            km_text = ''
            fuel_text = ''
            
            # Percorre os blocos de opcionais para extrair KM e Combustível
            for opt in optionals:
                text = opt.get_text().strip()
                # A quilometragem geralmente contém 'km'
                if 'km' in text.lower():
                    km_text = text
                # O combustível é uma palavra como 'FLEX', 'GASOLINA', 'DIESEL'
                elif 'flex' in text.lower() or 'gasolina' in text.lower() or 'diesel' in text.lower():
                    fuel_text = text
            
            # Limpa e formata os dados
            model_name = f"{first_name_tag.text.strip()} {last_name_tag.text.strip()}" if first_name_tag and last_name_tag else ''
            model_year = year_tag.text.strip() if year_tag else ''
            
            # Tenta extrair apenas o nome da cidade, removendo (PR) ou outros estados
            city_location_full = city_tag.get_text().strip() if city_tag else ''
            city_location = re.sub(r'\s*\([A-Z]{2}\)$', '', city_location_full, flags=re.IGNORECASE).strip()
            
            if not model_name:
                continue

            # 3. Monta a string no formato que o Gemini processará melhor:
            # "MARCA MODELO DETALHES ANO/ANO | COMBUSTÍVEL | KM em CIDADE - Spagi Motors"
            full_description = (
                f"{model_name.upper()} {model_year} | {fuel_text.upper()} | {km_text.upper()} em {city_location.title()} - Spagi Motors"
            )
            
            car_descriptions.append(full_description)

        except Exception as e:
            # Loga o erro, mas continua processando os outros carros
            print(f"Erro ao processar item: {e}")
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
            config={"system_instruction": system_instruction}
        )
        
        descricao_bruta = response.text
        
    except APIError as e:
        print(f"Erro na API do Gemini: {e}")
        return f"⚠️ Erro ao chamar a IA (API Error): {e}. Verifique o status da chave."
    except Exception as e:
        print(f"Erro inesperado: {e}")
        return f"⚠️ Erro Inesperado: {e}"

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
    View para a geração em massa de anúncios, que chama a função de scraping.
    """
    context = {}
    
    # Define a URL padrão para o scraping
    external_url = "https://spagimotors.com.br/multipla"
         
    if request.method == 'POST':
        # Captura a URL fornecida pelo usuário, se houver
        user_provided_url = request.POST.get('external_url')
        if user_provided_url:
            external_url = user_provided_url
        
        # 1. EXTRAÇÃO DOS DADOS (Chamada à função de scraping REAL)
        car_list = scrape_multipla_url(external_url)
        
        if not car_list:
             messages.error(request, f"Não foi possível extrair dados da URL: {external_url}. Verifique se o scraper ('scrape_multipla_url') foi implementado com os seletores corretos.")
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