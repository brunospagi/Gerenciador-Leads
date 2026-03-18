from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from usuarios.permissions import has_module_access

from .forms import TransacaoFinanceiraForm
from .models import TransacaoFinanceira, gerar_relatorio_DRE_mensal


class AcessoFinanceiroMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        if self.request.user.is_superuser:
            return True
        profile = getattr(self.request.user, "profile", None)
        if not profile:
            return False
        return (
            profile.nivel_acesso == "ADMIN"
            or profile.pode_acessar_financeiro
            or has_module_access(self.request.user, "financeiro")
        )


class AcessoAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        if self.request.user.is_superuser:
            return True
        profile = getattr(self.request.user, "profile", None)
        if not profile:
            return False
        return profile.nivel_acesso == "ADMIN"


class TransacaoListView(AcessoFinanceiroMixin, ListView):
    model = TransacaoFinanceira
    template_name = "financeiro/lista_transacoes.html"
    context_object_name = "transacoes"

    def _is_admin(self):
        return self.request.user.is_superuser or self.request.user.profile.nivel_acesso == "ADMIN"

    def _get_mes_ref(self):
        raw = (self.request.GET.get("mes_ref") or "").strip()
        today = timezone.localdate()
        default_year = today.year
        default_month = today.month

        if len(raw) == 7 and raw[4] == "-":
            try:
                year = int(raw[:4])
                month = int(raw[5:7])
                if 1 <= month <= 12:
                    return year, month, raw
            except ValueError:
                pass

        fallback = f"{default_year:04d}-{default_month:02d}"
        return default_year, default_month, fallback

    def _redirect_with_mes(self):
        mes_ref = (self.request.POST.get("mes_ref") or "").strip()
        if not mes_ref:
            mes_ref = self._get_mes_ref()[2]
        return HttpResponseRedirect(f"{reverse_lazy('financeiro:lista_transacoes')}?mes_ref={mes_ref}")

    def get_queryset(self):
        user = self.request.user
        year, month, _ = self._get_mes_ref()

        # Mantem recorrentes em dia ao virar o mes (global, sem depender de quem acessou).
        TransacaoFinanceira.gerar_recorrentes_ate_mes_atual(owner=None)
        if self._is_admin():
            return TransacaoFinanceira.objects.filter(
                data_vencimento__year=year,
                data_vencimento__month=month,
            ).order_by("-data_vencimento")

        # Usuario do financeiro ve apenas o que ele mesmo lancou.
        return TransacaoFinanceira.objects.filter(
            criado_por=user,
            data_vencimento__year=year,
            data_vencimento__month=month,
        ).order_by("-data_vencimento")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = context["transacoes"]
        context["total_transacoes"] = qs.count()
        context["total_pendentes"] = qs.filter(efetivado=False).count()
        context["total_efetivadas"] = qs.filter(efetivado=True).count()
        context["soma_pendente"] = qs.filter(efetivado=False).aggregate(total=Sum("valor"))["total"] or 0
        context["soma_efetivada"] = qs.filter(efetivado=True).aggregate(total=Sum("valor"))["total"] or 0
        context["saldo_geral"] = context["soma_efetivada"] - context["soma_pendente"]
        context["is_admin_financeiro"] = self._is_admin()
        context["mes_ref"] = self._get_mes_ref()[2]
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("bulk_action")
        selected_ids = request.POST.getlist("transacoes")
        user = request.user

        if not selected_ids:
            messages.warning(request, "Selecione pelo menos um lancamento para aplicar a acao em lote.")
            return self._redirect_with_mes()

        queryset = TransacaoFinanceira.objects.filter(id__in=selected_ids)
        if not self._is_admin():
            queryset = queryset.filter(criado_por=user)

        if not queryset.exists():
            messages.warning(request, "Nenhum lancamento valido foi encontrado para sua permissao.")
            return self._redirect_with_mes()

        if action == "marcar_efetivado":
            hoje = timezone.localdate()
            atualizadas = 0
            for transacao in queryset:
                if not transacao.efetivado:
                    transacao.efetivado = True
                    transacao.data_pagamento = hoje
                    transacao.save()
                    atualizadas += 1
            messages.success(request, f"{atualizadas} lancamento(s) marcado(s) como efetivado(s).")
            return self._redirect_with_mes()

        if action == "marcar_pendente":
            atualizadas = queryset.filter(efetivado=True).update(efetivado=False, data_pagamento=None)
            messages.success(request, f"{atualizadas} lancamento(s) voltaram para pendente.")
            return self._redirect_with_mes()

        if action == "excluir":
            if not self._is_admin():
                messages.error(request, "Apenas ADMIN pode excluir lancamentos em lote.")
                return self._redirect_with_mes()
            removidas = queryset.count()
            queryset.delete()
            messages.success(request, f"{removidas} lancamento(s) removido(s) com sucesso.")
            return self._redirect_with_mes()

        messages.warning(request, "Selecione uma acao em lote valida.")
        return self._redirect_with_mes()


class TransacaoCreateView(AcessoFinanceiroMixin, CreateView):
    model = TransacaoFinanceira
    form_class = TransacaoFinanceiraForm
    template_name = "financeiro/form_transacao.html"
    success_url = reverse_lazy("financeiro:lista_transacoes")

    def form_valid(self, form):
        form.instance.criado_por = self.request.user
        return super().form_valid(form)


class TransacaoUpdateView(AcessoAdminMixin, UpdateView):
    model = TransacaoFinanceira
    form_class = TransacaoFinanceiraForm
    template_name = "financeiro/form_transacao.html"
    success_url = reverse_lazy("financeiro:lista_transacoes")


class TransacaoDeleteView(AcessoAdminMixin, DeleteView):
    model = TransacaoFinanceira
    template_name = "financeiro/confirmar_delete.html"
    success_url = reverse_lazy("financeiro:lista_transacoes")


class RelatorioDREView(AcessoAdminMixin, TemplateView):
    template_name = "financeiro/relatorio_dre.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoje = timezone.now()
        mes = int(self.request.GET.get("mes", hoje.month))
        ano = int(self.request.GET.get("ano", hoje.year))

        context["relatorio"] = gerar_relatorio_DRE_mensal(mes, ano)
        context["mes_atual"] = mes
        context["ano_atual"] = ano

        if "print" in self.request.GET:
            self.template_name = "financeiro/relatorio_dre_print.html"

        return context
