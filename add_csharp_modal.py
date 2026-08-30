import re

with open("cdss_web/Components/Pages/Predict.razor", "r") as f:
    content = f.read()

modal_csharp = """
    private bool _detayModalAcik = false;
    private bool _detayYukleniyor = false;
    private AuditLogDetailResponse? _seciliDetay;

    private async Task DetayGoster(int id)
    {
        _detayModalAcik = true;
        _detayYukleniyor = true;
        _seciliDetay = null;
        StateHasChanged();

        var (detay, _) = await ApiService.GetLogDetailWithErrorAsync(id);
        _seciliDetay = detay;

        _detayYukleniyor = false;
        StateHasChanged();
    }

    private void ModalKapat()
    {
        _detayModalAcik = false;
        _seciliDetay = null;
    }
"""

content = content.replace("private List<AuditLogEntry> _pastEvaluations = new();", "private List<AuditLogEntry> _pastEvaluations = new();" + modal_csharp)

with open("cdss_web/Components/Pages/Predict.razor", "w") as f:
    f.write(content)
