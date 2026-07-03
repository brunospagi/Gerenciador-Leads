from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .forms import CRLV_PDF_MAX_SIZE_MB, CRLVUploadForm


class CRLVUploadFormTests(TestCase):
    def test_aceita_pdf_valido(self):
        arquivo = SimpleUploadedFile('crlv.pdf', b'%PDF-1.4 conteudo', content_type='application/pdf')
        form = CRLVUploadForm(files={'crlv_pdf': arquivo})
        self.assertTrue(form.is_valid())

    def test_rejeita_extensao_invalida(self):
        arquivo = SimpleUploadedFile('crlv.exe', b'conteudo qualquer', content_type='application/octet-stream')
        form = CRLVUploadForm(files={'crlv_pdf': arquivo})
        self.assertFalse(form.is_valid())
        self.assertIn('crlv_pdf', form.errors)

    def test_rejeita_content_type_divergente_da_extensao(self):
        arquivo = SimpleUploadedFile('crlv.pdf', b'nao e realmente um pdf', content_type='image/png')
        form = CRLVUploadForm(files={'crlv_pdf': arquivo})
        self.assertFalse(form.is_valid())
        self.assertIn('crlv_pdf', form.errors)

    def test_rejeita_arquivo_maior_que_limite(self):
        conteudo = b'0' * ((CRLV_PDF_MAX_SIZE_MB * 1024 * 1024) + 1)
        arquivo = SimpleUploadedFile('crlv.pdf', conteudo, content_type='application/pdf')
        form = CRLVUploadForm(files={'crlv_pdf': arquivo})
        self.assertFalse(form.is_valid())
        self.assertIn('crlv_pdf', form.errors)
