from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from configuracoes.access import ModuleActionRequiredMixin

from .forms import TransacaoFinanceiraForm
from .models import FechamentoMensalFinanceiro, TransacaoFinanceira, gerar_relatorio_DRE_mensal


class TransacaoListView(ModuleActionRequiredMixin, ListView):
    module_key = "financeiro"
    module_action = "visualizar"
    model = TransacaoFinanceira
    template_name = "financeiro/lista_transacoes.html"
    context_object_name = "transacoes"

    def _is_admin(self):
        profile = getattr(self.request.user, "profile", None)
        return self.request.user.is_superuser or (profile and profile.nivel_acesso == "ADMIN")

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
        # Saldo precisa separar RECEITA de DESPESA antes de somar — receita e
        # despesa juntas na mesma soma davam um número sem sentido contábil.
        receitas_efetivadas = qs.filter(efetivado=True, tipo="RECEITA").aggregate(total=Sum("valor"))["total"] or 0
        despesas_efetivadas = qs.filter(efetivado=True, tipo="DESPESA").aggregate(total=Sum("valor"))["total"] or 0
        context["receitas_efetivadas"] = receitas_efetivadas
        context["despesas_efetivadas"] = despesas_efetivadas
        context["saldo_geral"] = receitas_efetivadas - despesas_efetivadas
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

        # Nunca aplica ação em lote sobre transação de um mês já fechado.
        meses_fechados = set(FechamentoMensalFinanceiro.objects.filter(fechado=True).values_list("mes", "ano"))
        if meses_fechados:
            ids_bloqueados = [t.id for t in queryset if t.mes_competencia in meses_fechados]
            if ids_bloqueados:
                queryset = queryset.exclude(id__in=ids_bloqueados)
                messages.warning(request, f"{len(ids_bloqueados)} lancamento(s) de mes fechado foram ignorados.")

        if not queryset.exists():
            messages.warning(request, "Nenhum lancamento valido restou apos remover os de mes fechado.")
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


class TransacaoCreateView(ModuleActionRequiredMixin, CreateView):
    module_key = "financeiro"
    module_action = "criar"
    model = TransacaoFinanceira
    form_class = TransacaoFinanceiraForm
    template_name = "financeiro/form_transacao.html"
    success_url = reverse_lazy("financeiro:lista_transacoes")

    def form_valid(self, form):
        form.instance.criado_por = self.request.user
        return super().form_valid(form)


class _BloqueiaMesFechadoMixin:
    """Impede editar/excluir uma transação cuja competência já foi fechada."""

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        mes, ano = self.object.mes_competencia
        if FechamentoMensalFinanceiro.esta_fechado(mes, ano):
            messages.error(
                request,
                f"Este lançamento pertence ao mês {mes:02d}/{ano}, já fechado. Reabra o mês (na tela do DRE) antes de alterar.",
            )
            return redirect("financeiro:lista_transacoes")
        return super().dispatch(request, *args, **kwargs)


class TransacaoUpdateView(ModuleActionRequiredMixin, _BloqueiaMesFechadoMixin, UpdateView):
    module_key = "financeiro"
    module_action = "editar"
    model = TransacaoFinanceira
    form_class = TransacaoFinanceiraForm
    template_name = "financeiro/form_transacao.html"
    success_url = reverse_lazy("financeiro:lista_transacoes")


class TransacaoDeleteView(ModuleActionRequiredMixin, _BloqueiaMesFechadoMixin, DeleteView):
    module_key = "financeiro"
    module_action = "excluir"
    model = TransacaoFinanceira
    template_name = "financeiro/confirmar_delete.html"
    success_url = reverse_lazy("financeiro:lista_transacoes")


class RelatorioDREView(ModuleActionRequiredMixin, TemplateView):
    # 'editar' (não 'visualizar'): a view também processa fechar/reabrir mês via POST,
    # uma ação administrativa que sempre foi ADMIN-only (AcessoAdminMixin antigo).
    module_key = "financeiro"
    module_action = "editar"
    template_name = "financeiro/relatorio_dre.html"

    def post(self, request, *args, **kwargs):
        mes = int(request.POST.get("mes") or timezone.now().month)
        ano = int(request.POST.get("ano") or timezone.now().year)
        acao = (request.POST.get("acao") or "").strip().lower()

        if acao == "fechar_mes":
            fechamento, criado = FechamentoMensalFinanceiro.objects.get_or_create(
                mes=mes, ano=ano,
                defaults={"fechado": True, "fechado_por": request.user, "fechado_em": timezone.now()},
            )
            if not criado and not fechamento.fechado:
                fechamento.fechado = True
                fechamento.fechado_por = request.user
                fechamento.fechado_em = timezone.now()
                fechamento.save(update_fields=["fechado", "fechado_por", "fechado_em"])
            messages.success(request, f"Mês {mes:02d}/{ano} fechado com sucesso.")
        elif acao == "reabrir_mes":
            fechamento = FechamentoMensalFinanceiro.objects.filter(mes=mes, ano=ano).first()
            if fechamento and fechamento.fechado:
                fechamento.fechado = False
                fechamento.save(update_fields=["fechado"])
                messages.success(request, f"Mês {mes:02d}/{ano} reaberto.")
            else:
                messages.info(request, "Este mês já estava aberto.")

        return HttpResponseRedirect(f"{reverse_lazy('financeiro:relatorio_dre')}?mes={mes}&ano={ano}")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoje = timezone.now()
        try:
            mes = int(self.request.GET.get("mes", hoje.month))
        except (TypeError, ValueError):
            mes = hoje.month
        try:
            ano = int(self.request.GET.get("ano", hoje.year))
        except (TypeError, ValueError):
            ano = hoje.year

        if mes < 1 or mes > 12:
            mes = hoje.month

        context["relatorio"] = gerar_relatorio_DRE_mensal(mes, ano)
        context["mes_atual"] = mes
        context["ano_atual"] = ano
        context["fechamento"] = FechamentoMensalFinanceiro.objects.filter(mes=mes, ano=ano).first()

        if "print" in self.request.GET:
            self.template_name = "financeiro/relatorio_dre_print.html"

        return context
