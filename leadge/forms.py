from django import forms
from .models import TVVideo

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