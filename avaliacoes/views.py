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
import time
from bs4 import BeautifulSoup 
from requests.exceptions import RequestException, Timeout 
from django.http import JsonResponse

from .ai_runtime import get_gemini_runtime


# --- LÃ“GICA DE EXTRAÃ‡ÃƒO WEB (SCRAPER ROBUSTO COM TRATAMENTO DE TIMEOUT) ---
def scrape_multipla_url(url):
    """
    Extrai a lista de descriÃ§Ãµes dos veÃ­culos da URL, utilizando os seletores
    identificados no cÃ³digo-fonte do Spagi Motors, com tratamento de erros robusto.
    """
    car_descriptions = []
    
    if not url.startswith('http'):
        url = 'https://' + url
        
    try:
        # 1. Faz a requisiÃ§Ã£o HTTP com timeout AUMENTADO (30s)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=30, headers=headers) 
        response.raise_for_status() # LanÃ§a erro se o status code for 4xx ou 5xx
        
        # 2. Parseia o conteÃºdo HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
    except Timeout as e:
        # TRATAMENTO ESPECÃFICO PARA TIMEOUT (EVITA O ERRO 500)
        raise Exception(f"ERRO DE TEMPO LIMITE (Timeout): O servidor demorou demais para responder apÃ³s 30 segundos. Verifique sua conexÃ£o ou a disponibilidade do site de destino. Detalhes: {e}") 
    except RequestException as e:
        # Tratamento para outros erros de rede/HTTP (ex: 404, 503)
        raise Exception(f"Falha de Rede ou HTTP ao acessar o estoque: {e}") 
    except Exception as e:
        # Tratamento para erros de parsing do BeautifulSoup ou outros
        raise Exception(f"Erro ao processar o HTML da pÃ¡gina: {e}")

    # 3. ENCONTRA TODAS AS LISTAGENS DE CARROS
    car_listings = soup.find_all('div', class_='carro', recursive=True)
    
    if not car_listings:
        return []
    
    for car in car_listings:
        try:
            # 4. EXTRAÃ‡ÃƒO DE DADOS POR ITEM (COM CHECAGEM ROBUSTA DE NONE)
            first_name = car.select_one('.first-name').get_text(strip=True) if car.select_one('.first-name') else ''
            last_name = car.select_one('.last-name').get_text(strip=True) if car.select_one('.last-name') else ''
            model_year = car.select_one('.year').get_text(strip=True) if car.select_one('.year') else ''
            
            city_tag = car.select_one('.vitrine-cidade')
            city_location_full = city_tag.get_text(strip=True) if city_tag else 'Cidade NÃ£o Informada'
            
            city_location = re.sub(r'\s*\([A-Z]{2}\)$', '', city_location_full, flags=re.IGNORECASE).strip()

            optionals = car.select('.opicionais .text-none.grey-text10')
            
            km_text = next((opt.get_text().strip() for opt in optionals if 'km' in opt.get_text().lower()), 'KM NÃ£o Informado')
            fuel_text = next((opt.get_text().strip() for opt in optionals if any(f in opt.get_text().lower() for f in ['flex', 'gasolina', 'diesel', 'Ã¡lcool'])), 'CombustÃ­vel NÃ£o Informado')
            
            model_name = f"{first_name} {last_name}".strip()
            
            if not model_name or not model_year:
                continue

            # 5. Monta a string
            full_description = (
                f"{model_name.upper()} {model_year} | {fuel_text.upper()} | {km_text.upper()} em {city_location.title()} - Spagi Motors"
            )
            
            car_descriptions.append(full_description)

        except Exception:
            # Captura exceÃ§Ãµes para este item especÃ­fico (e.g., tag inesperada), 
            # e garante que o loop continue para o prÃ³ximo item
            continue

    return car_descriptions

# --- LÃ“GICA CENTRAL DE GERAÃ‡ÃƒO (COM GEMINI) ---
def generate_high_conversion_description(vehicle_description, marketplace='Facebook Marketplace'):
    """
    Usa o Gemini API para gerar uma descriÃ§Ã£o de alta conversÃ£o.
    Assegura a remoÃ§Ã£o de "novo" e "garantia de fÃ¡brica".
    """
    gemini_client, model_name, config_error = get_gemini_runtime()
    if config_error or not gemini_client:
        return f"⚠️ Erro de Configuração: {config_error or 'cliente Gemini indisponível.'}"

    # 1. Monta o prompt e a instruÃ§Ã£o
    system_instruction = (
        "VocÃª Ã© um Copywriter de alta performance para concessionÃ¡rias de veÃ­culos. "
        "Sua tarefa Ã© transformar a descriÃ§Ã£o bruta de um veÃ­culo em um anÃºncio irresistÃ­vel para o "
        "Facebook Marketplace, focado em alta conversÃ£o e chamadas para aÃ§Ã£o. "
        "Utilize emojis, separe o texto em parÃ¡grafos de fÃ¡cil leitura e crie uma seÃ§Ã£o de hashtags. "
        "O anÃºncio deve ter um tom de urgÃªncia e destaque benefÃ­cios de compra (ex: troca, financiamento)."
        "REGRA CRÃTICA: NÃƒO inclua as palavras 'novo' ou 'garantia de fÃ¡brica' em nenhuma variaÃ§Ã£o. "
        "Substitua 'novo' por termos como 'impecÃ¡vel', 'estado de zero' ou 'excelente estado'."
    )
    
    user_prompt = f"Gere o anÃºncio com base na seguinte descriÃ§Ã£o do veÃ­culo e contexto da concessionÃ¡ria:\n\n{vehicle_description}"
    
    # 2. Chama a API do Gemini (com retry para erros transitórios 503/UNAVAILABLE)
    max_attempts = 3
    descricao_bruta = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config={"system_instruction": system_instruction},
            )
            descricao_bruta = response.text
            break
        except Exception as e:
            error_text = str(e)
            error_upper = error_text.upper()
            is_transient = (
                '503' in error_upper
                or 'UNAVAILABLE' in error_upper
                or 'HIGH DEMAND' in error_upper
            )
            if is_transient and attempt < max_attempts:
                time.sleep(attempt)
                continue

            if 'API KEY' in error_upper or 'PERMISSION' in error_upper or 'UNAUTHENTICATED' in error_upper:
                return f"⚠️ Erro ao chamar a IA (autenticação): {e}. Verifique a chave no Admin."

            if is_transient:
                return (
                    "⚠️ Erro ao chamar a IA: serviço em alta demanda (503/UNAVAILABLE). "
                    "Tente novamente em alguns minutos."
                )

            print(f"Erro inesperado no Gemini request: {e}")
            return f"⚠️ Erro de Comunicação com a IA: O serviço Gemini falhou ao responder. Detalhes: {type(e).__name__}"

    # 3. LÃ“GICA DE EXCLUSÃƒO OBRIGATÃ“RIA (PÃ³s-processamento de seguranÃ§a)
    descricao_limpa = descricao_bruta
    
    # PadrÃµes para remover variaÃ§Ãµes de "novo" e "garantia de fÃ¡brica"
    palavras_chave = [
        r'\bnov[oa]s?\b', # novo, nova, novos, novas
        r'\bgaranti[aae] de f[aÃ¡]brica\b'
    ]
    
    for termo in palavras_chave:
        descricao_limpa = re.sub(termo, ' ', descricao_limpa, flags=re.IGNORECASE)

    # Limpa espaÃ§os e quebras de linha duplas
    descricao_limpa = re.sub(r'\s{2,}', ' ', descricao_limpa).strip()
    descricao_limpa = re.sub(r'\n\s*\n', '\n\n', descricao_limpa)
    
    return descricao_limpa.strip()


@login_required
def gerador_anuncio_view(request):
    """
    View para a pÃ¡gina de geraÃ§Ã£o de anÃºncios (single).
    """
    context = {}
    generated_description = None
    input_text = request.GET.get('vehicle_description', '')
    
    if request.method == 'GET' and input_text:
        try:
            generated_description = generate_high_conversion_description(input_text)
            
            # Verifica se houve um erro retornado pela funÃ§Ã£o de geraÃ§Ã£o
            if "⚠️ Erro" in generated_description:
                 messages.error(request, generated_description)
            else:
                messages.success(request, "DescriÃ§Ã£o de alta conversÃ£o gerada com sucesso pela IA Gemini! Copie e cole no seu anÃºncio.")
                
        except Exception as e:
            messages.error(request, f"Erro inesperado no view: {e}")

    context['generated_description'] = generated_description
    context['input_text'] = input_text
    
    return render(request, 'avaliacoes/gerador_anuncio.html', context)


@login_required
def bulk_gerador_anuncio_view(request):
    """
    View para a geraÃ§Ã£o em massa de anÃºncios, que agora trata as exceÃ§Ãµes de scraping.
    """
    context = {}
    
    # Define a URL padrÃ£o (e fallback) para o scraping
    external_url = "https://spagimotors.com.br/multipla"
    
    if request.method == 'POST':
        # Captura a URL fornecida pelo usuÃ¡rio, se houver
        user_provided_url = request.POST.get('external_url')
        if user_provided_url:
            external_url = user_provided_url
        
        car_list = []
        try:
            # 1. EXTRAÃ‡ÃƒO DOS DADOS (Chamada Ã  funÃ§Ã£o de scraping com tratamento de erro)
            car_list = scrape_multipla_url(external_url)
            
        except Exception as e:
            # Captura a exceÃ§Ã£o levantada pela funÃ§Ã£o de scraping e a exibe
            messages.error(request, f"Erro fatal de scraping: NÃ£o foi possÃ­vel processar a pÃ¡gina. Detalhes: {e}")
            # Retorna o formulÃ¡rio com a mensagem de erro (EVITA O ERRO 500)
            return render(request, 'avaliacoes/bulk_gerador_anuncio_form.html', context)


        if not car_list:
             messages.error(request, f"NÃ£o foi possÃ­vel encontrar nenhum veÃ­culo na URL: {external_url}. Verifique o link e se a pÃ¡gina carrega corretamente.")
             return render(request, 'avaliacoes/bulk_gerador_anuncio_form.html', context)

        generated_announcements = []
        error_count = 0
        
        # 2. GERAÃ‡ÃƒO DOS ANÃšNCIOS COM GEMINI
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
            messages.warning(request, f"Foram processados {len(generated_announcements)} anÃºncios, mas {error_count} falharam devido a um erro da API Gemini. Verifique as mensagens.")
        else:
            messages.success(request, f"Foram gerados {len(generated_announcements)} anÃºncios com sucesso pela IA Gemini!")
            
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

FIPE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_fipe_marcas(request, tipo_veiculo):
    try:
        # Adicionado headers=FIPE_HEADERS
        response = requests.get(f'https://parallelum.com.br/fipe/api/v1/{tipo_veiculo}/marcas', headers=FIPE_HEADERS)
        response.raise_for_status()
        return JsonResponse(response.json(), safe=False)
    except requests.RequestException as e:
        print(f"Erro FIPE Marcas: {e}") # Log do erro no terminal para debug
        return JsonResponse({'error': 'Erro ao buscar marcas'}, status=500)

def get_fipe_modelos(request, tipo_veiculo, marca_id):
    try:
        # Adicionado headers=FIPE_HEADERS
        response = requests.get(f'https://parallelum.com.br/fipe/api/v1/{tipo_veiculo}/marcas/{marca_id}/modelos', headers=FIPE_HEADERS)
        response.raise_for_status()
        return JsonResponse(response.json().get('modelos', []), safe=False)
    except requests.RequestException as e:
        print(f"Erro FIPE Modelos: {e}")
        return JsonResponse({'error': 'Erro ao buscar modelos'}, status=500)

def get_fipe_anos(request, tipo_veiculo, marca_id, modelo_id):
    try:
        # Adicionado headers=FIPE_HEADERS
        response = requests.get(f'https://parallelum.com.br/fipe/api/v1/{tipo_veiculo}/marcas/{marca_id}/modelos/{modelo_id}/anos', headers=FIPE_HEADERS)
        response.raise_for_status()
        return JsonResponse(response.json(), safe=False)
    except requests.RequestException as e:
        print(f"Erro FIPE Anos: {e}")
        return JsonResponse({'error': 'Erro ao buscar anos'}, status=500)

