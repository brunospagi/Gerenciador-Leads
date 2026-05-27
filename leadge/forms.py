from django import forms
from .models import Banner, TVVideo, TVProgramacaoItem

class TVVideoForm(forms.ModelForm):
    class Meta:
        model = TVVideo
        fields = ['titulo', 'video_url', 'video_mp4', 'newsdata_api_key', 'manual_news_ticker']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'video_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Ex: https://www.youtube.com/embed/SEU_ID?autoplay=1&mute=1&loop=1&playlist=SEU_ID'}),
            'video_mp4': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'newsdata_api_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Chave da API NewsData.io'}),
            'manual_news_ticker': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Notícia 1 | Notícia 2 | Notícia 3'}),
        }

class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = ['titulo', 'imagem', 'descricao', 'link', 'ativo', 'ordem']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'link': forms.URLInput(attrs={'placeholder': 'https://...'}),
        }


class TVProgramacaoItemForm(forms.ModelForm):
    dias_semana = forms.MultipleChoiceField(
        choices=TVProgramacaoItem.DIAS_SEMANA_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Dias da Semana",
    )

    class Meta:
        model = TVProgramacaoItem
        fields = [
            'titulo',
            'ativo',
            'ordem',
            'video_url',
            'video_mp4',
            'manual_news_ticker',
            'dias_semana',
            'data_inicio',
            'data_fim',
            'horario_inicio',
            'horario_fim',
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'video_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'video_mp4': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'manual_news_ticker': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Notícia 1 | Notícia 2'}),
            'data_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_fim': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'horario_inicio': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'horario_fim': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.dias_semana:
            self.initial['dias_semana'] = [
                dia.strip() for dia in self.instance.dias_semana.split(',') if dia.strip()
            ]

    def clean_dias_semana(self):
        dias = self.cleaned_data.get('dias_semana', [])
        if not dias:
            raise forms.ValidationError("Selecione ao menos um dia da semana.")
        return ','.join(dias)
