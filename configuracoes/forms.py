from django import forms

from .models import ConfiguracaoIntegracoes, WebhookIntegracao


class WebhookIntegracaoForm(forms.ModelForm):
    class Meta:
        model = WebhookIntegracao
        fields = ['nome', 'slug', 'descricao', 'url', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'url': forms.URLInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.sistema:
            self.fields['slug'].disabled = True


class ConfiguracaoIntegracoesForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoIntegracoes
        fields = [
            'evolution_api_url', 'evolution_api_key', 'evolution_instance',
            'evo_crm_api_url', 'evo_crm_api_token', 'evo_crm_pipeline_id', 'evo_crm_pipeline_stage_id',
            'provedor_imagem_ia', 'leonardo_api_key', 'openai_api_key',
        ]
        widgets = {
            field: forms.TextInput(attrs={'class': 'form-control'})
            for field in fields if field != 'provedor_imagem_ia'
        }
        widgets['provedor_imagem_ia'] = forms.Select(attrs={'class': 'form-select'})
