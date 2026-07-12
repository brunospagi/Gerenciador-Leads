from django import forms

from .models import ConfiguracaoIntegracoes, WebhookIntegracao

_CAMPOS_SELECT_INTEGRACOES = (
    'provedor_imagem_ia', 'gemini_image_model', 'leonardo_model_id',
    'openai_image_model', 'openai_image_quality',
)
_CAMPOS_TEXTAREA_INTEGRACOES = ('prompt_imagem', 'prompt_imagem_leonardo')


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
            'provedor_imagem_ia', 'prompt_imagem',
            'gemini_image_model',
            'leonardo_api_key', 'leonardo_model_id', 'prompt_imagem_leonardo',
            'openai_api_key', 'openai_image_model', 'openai_image_quality',
        ]
        widgets = {
            field: forms.TextInput(attrs={'class': 'form-control'})
            for field in fields
            if field not in _CAMPOS_SELECT_INTEGRACOES and field not in _CAMPOS_TEXTAREA_INTEGRACOES
        }
        widgets.update({
            field: forms.Select(attrs={'class': 'form-select'})
            for field in _CAMPOS_SELECT_INTEGRACOES
        })
        widgets.update({
            field: forms.Textarea(attrs={'class': 'form-control', 'rows': 4})
            for field in _CAMPOS_TEXTAREA_INTEGRACOES
        })
