def financial_years_context(request):
    try:
        from .models import FinancialYear
        all_fys   = list(FinancialYear.objects.all().order_by('-start_date'))
        active_fy = next((fy for fy in all_fys if fy.is_active), None)
        return {
            'all_financial_years': all_fys,
            'active_fy':           active_fy,
        }
    except Exception:
        # Table may not exist yet (before migrate) — fail silently
        return {
            'all_financial_years': [],
            'active_fy':           None,
        }