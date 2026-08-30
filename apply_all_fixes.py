import re

with open("cdss_web/Components/Pages/Predict.razor", "r") as f:
    c = f.read()

# 1. TC ARAMA BUTONU
old_tc_input = """            <input type="text"
                   class="form-input"
                   placeholder="Hastanın kayıtlarını anlayabilmek için: 11 haneli TC kimlik numarası"
                   maxlength="11"
                   @bind-value="TcNo"
                   @bind-value:event="oninput"
                   style="font-family:monospace;letter-spacing:2px;" />"""
new_tc_input = """            <div style="position:relative; display:flex; align-items:center;">
                <input type="text"
                       class="form-input"
                       placeholder="Hastanın kayıtlarını anlayabilmek için: 11 haneli TC kimlik numarası"
                       maxlength="11"
                       @bind-value="TcNo"
                       @bind-value:event="oninput"
                       style="font-family:monospace;letter-spacing:2px;padding-right:100px;flex:1;" />
                <button type="button"
                        class="btn-tc-search"
                        @onclick="ForceSearchTc"
                        disabled="@_tcSearching">
                    @if (_tcSearching)
                    {
                        <i class="ph ph-circle-notch" style="animation:spin 1s linear infinite;"></i>
                    }
                    else
                    {
                        <i class="ph ph-magnifying-glass"></i>
                    }
                    <span>Ara</span>
                </button>
            </div>"""
c = c.replace(old_tc_input, new_tc_input)

# 2. TELEFON İNPUT
old_phone_input = """            <div class="form-group">
                <label class="form-label">Telefon <span style="color:var(--text-muted)">(isteğe bağlı)</span></label>
                <input type="tel" class="form-input"
                       placeholder="0xxx xxx xx xx"
                       value="@_identity.Telefon"
                       @onchange="@(e => _identity.Telefon = e.Value?.ToString())"
                       disabled="@_identityFieldsDisabled" />
            </div>"""
new_phone_input = """            <div class="form-group">
                <label class="form-label">Telefon <span style="color:var(--text-muted)">(isteğe bağlı)</span></label>
                <div class="phone-input-wrapper">
                    <select class="phone-country-select"
                            @bind="_phoneCountryCode"
                            disabled="@_identityFieldsDisabled">
                        <option value="+90">🇹🇷 +90</option>
                        <option value="+1">🇺🇸 +1</option>
                        <option value="+44">🇬🇧 +44</option>
                        <option value="+49">🇩🇪 +49</option>
                        <option value="+33">🇫🇷 +33</option>
                        <option value="+39">🇮🇹 +39</option>
                        <option value="+34">🇪🇸 +34</option>
                    </select>
                    <input type="tel"
                           class="form-input phone-number-input"
                           placeholder="532 123 45 67"
                           value="@_phoneDisplay"
                           @oninput="OnPhoneInput"
                           disabled="@_identityFieldsDisabled" />
                </div>
            </div>"""
c = c.replace(old_phone_input, new_phone_input)

# 3. ZİYARETLER PANELİ
old_visit_panel = """    @if (_patientFound == true && _lastVisit is not null)
    {
        <div style="width:260px;flex-shrink:0;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:16px;">
            <div style="font-size:12px;font-weight:600;color:var(--accent);margin-bottom:12px;display:flex;align-items:center;gap:6px;">
                <i class="ph ph-clock-counter-clockwise"></i> Son Ziyaret
            </div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px;">
                @(DateTime.TryParse(_lastVisit.Timestamp, out var ld) ? ld.ToString("dd.MM.yyyy HH:mm") : "-")
            </div>
            <div style="display:flex;flex-direction:column;gap:6px;margin-bottom:14px;">
                <div style="display:flex;justify-content:space-between;font-size:12px;">
                    <span>FTR</span>
                    <span style="@(_lastVisit.Tahmin.Ftr ? "color:var(--success)" : "color:var(--text-muted)")">
                        @(_lastVisit.Tahmin.Ftr ? "✓ Önerildi" : "—") · %@((int)(_lastVisit.Olasiliklar.Ftr * 100))
                    </span>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:12px;">
                    <span>Aile Hekimliği</span>
                    <span style="@(_lastVisit.Tahmin.AileHekimligi ? "color:var(--success)" : "color:var(--text-muted)")">
                        @(_lastVisit.Tahmin.AileHekimligi ? "✓ Önerildi" : "—") · %@((int)(_lastVisit.Olasiliklar.AileHekimligi * 100))
                    </span>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:12px;">
                    <span>Sistemik Tedavi</span>
                    <span style="@(_lastVisit.Tahmin.SistemikTedavi ? "color:var(--success)" : "color:var(--text-muted)")">
                        @(_lastVisit.Tahmin.SistemikTedavi ? "✓ Önerildi" : "—") · %@((int)(_lastVisit.Olasiliklar.SistemikTedavi * 100))
                    </span>
                </div>
            </div>
            <a href="/audit-log?tc=@_currentTcHash"
               style="display:block;text-align:center;font-size:11px;color:var(--accent);text-decoration:none;padding:6px;border:1px solid var(--accent-dim);border-radius:6px;">
                <i class="ph ph-list-magnifying-glass"></i> Tüm Ziyaretleri Gör
            </a>
        </div>
    }"""
new_visit_panel = """    @if (_patientFound == true && _patientVisits.Any())
    {
        <div style="width:260px;flex-shrink:0;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:16px;display:flex;flex-direction:column;max-height:600px;">
            <div style="font-size:12px;font-weight:600;color:var(--accent);margin-bottom:12px;display:flex;align-items:center;gap:6px;">
                <i class="ph ph-clock-counter-clockwise"></i> Ziyaret Geçmişi (@_patientVisits.Count)
            </div>
            <div style="flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:12px;padding-right:4px;">
                @foreach (var visit in _patientVisits)
                {
                    <div style="border:1px solid var(--border-light);border-radius:6px;padding:10px;background:var(--bg-primary);">
                        <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">
                            @(DateTime.TryParse(visit.Timestamp, out var ld) ? ld.ToString("dd.MM.yyyy HH:mm") : "-")
                        </div>
                        <div style="display:flex;flex-direction:column;gap:4px;margin-bottom:10px;">
                            <div style="display:flex;justify-content:space-between;font-size:11px;">
                                <span>FTR</span>
                                <span style="@(visit.Tahmin.Ftr ? "color:var(--success)" : "color:var(--text-muted)")">
                                    @(visit.Tahmin.Ftr ? "✓ Önerildi" : "—")
                                </span>
                            </div>
                            <div style="display:flex;justify-content:space-between;font-size:11px;">
                                <span>Aile Hekimi</span>
                                <span style="@(visit.Tahmin.AileHekimligi ? "color:var(--success)" : "color:var(--text-muted)")">
                                    @(visit.Tahmin.AileHekimligi ? "✓ Önerildi" : "—")
                                </span>
                            </div>
                            <div style="display:flex;justify-content:space-between;font-size:11px;">
                                <span>Sist. Tedavi</span>
                                <span style="@(visit.Tahmin.SistemikTedavi ? "color:var(--success)" : "color:var(--text-muted)")">
                                    @(visit.Tahmin.SistemikTedavi ? "✓ Önerildi" : "—")
                                </span>
                            </div>
                        </div>
                        <button type="button" class="btn btn-ghost" style="width:100%;font-size:11px;padding:4px;" @onclick="() => DetayGoster(visit.Id)">
                            <i class="ph ph-magnifying-glass"></i> Detayları Gör
                        </button>
                    </div>
                }
            </div>
            <a href="/audit-log?tc=@_currentTcHash"
               style="display:block;text-align:center;font-size:11px;color:var(--accent);text-decoration:none;padding:6px;border:1px solid var(--accent-dim);border-radius:6px;margin-top:12px;">
                <i class="ph ph-list-bullets"></i> Tümünü Loglarda Gör
            </a>
        </div>
    }"""
c = c.replace(old_visit_panel, new_visit_panel)

# 4. _lastVisit -> _patientVisits state updates
c = c.replace("private PatientVisitSummary? _lastVisit;", "private List<PatientVisitSummary> _patientVisits = new();")

c = c.replace("""            if (_patientFound != null)
            {
                _patientFound = null;
                _lastVisit = null;
                _currentTcHash = null;
                _patient = new PatientInputModel();""", 
"""            if (_patientFound != null)
            {
                _patientFound = null;
                _patientVisits.Clear();
                _currentTcHash = null;
                _patient = new PatientInputModel();""")

c = c.replace("""            // Son ziyareti yükle
            var visits = await ApiService.GetPatientVisitsAsync(patient.TcHash);
            _lastVisit = visits.FirstOrDefault();""",
"""            // Tüm ziyaretleri yükle
            _patientVisits = await ApiService.GetPatientVisitsAsync(patient.TcHash);""")

c = c.replace("""        else
        {
            // Yeni hasta — tüm alanları aç
            _patientFound = false;
            _currentTcHash = null;
            _lastVisit = null;""",
"""        else
        {
            // Yeni hasta — tüm alanları aç
            _patientFound = false;
            _currentTcHash = null;
            _patientVisits.Clear();""")

c = c.replace("""        _identityFieldsDisabled = true;
        _lastVisit = null;
        _currentTcHash = null;""",
"""        _identityFieldsDisabled = true;
        _patientVisits.Clear();
        _currentTcHash = null;""")

# 5. C# Logic (Phone parsing, Modal, ForceSearchTc)
# Find protected override async Task OnAfterRenderAsync
c_sharp_logic = """
    private void ForceSearchTc()
    {
        if (string.IsNullOrWhiteSpace(_identity.TcNo)) return;
        _tcError = null;
        _tcSearching = true;
        StateHasChanged();
        _ = SearchPatientAsync(_identity.TcNo);
    }

    private string _phoneCountryCode = "+90";
    private string _phoneDisplay = "";

    private void OnPhoneInput(ChangeEventArgs e)
    {
        var val = e.Value?.ToString() ?? "";
        var digits = new string(val.Where(char.IsDigit).ToArray());
        if (digits.Length > 10) digits = digits[..10];
        var formatted = "";
        for (int i = 0; i < digits.Length; i++)
        {
            if (i == 3 || i == 6 || i == 8) formatted += " ";
            formatted += digits[i];
        }
        _phoneDisplay = formatted;
        _identity.Telefon = string.IsNullOrEmpty(digits) ? null : $"{_phoneCountryCode}{digits}";
    }

    private void ParsePhoneForDisplay(string? fullPhone)
    {
        if (string.IsNullOrEmpty(fullPhone))
        {
            _phoneDisplay = "";
            _phoneCountryCode = "+90";
            return;
        }
        if (fullPhone.StartsWith("+"))
        {
            for (int i = 5; i >= 2; i--)
            {
                if (fullPhone.Length > i)
                {
                    _phoneCountryCode = fullPhone.Substring(0, i);
                    OnPhoneInput(new ChangeEventArgs { Value = fullPhone.Substring(i) });
                    return;
                }
            }
        }
        OnPhoneInput(new ChangeEventArgs { Value = fullPhone });
    }

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

c = c.replace("protected override async Task OnAfterRenderAsync", c_sharp_logic + "\n    protected override async Task OnAfterRenderAsync")

# Update HandleSubmit to reload visits
c = c.replace("""        else if (result is not null)
        {
            _result = result;
            _showResult = true;
        }""",
"""        else if (result is not null)
        {
            _result = result;
            _showResult = true;
            _patientVisits = await ApiService.GetPatientVisitsAsync(_currentTcHash);
        }""")

# 6. ParsePhoneForDisplay calls
c = c.replace("""            _identity.Cinsiyet = patient.Cinsiyet;
            _identity.Telefon = patient.Telefon;
            _identity.KanGrubu = patient.KanGrubu;""",
"""            _identity.Cinsiyet = patient.Cinsiyet;
            _identity.Telefon = patient.Telefon;
            ParsePhoneForDisplay(patient.Telefon);
            _identity.KanGrubu = patient.KanGrubu;""")

c = c.replace("""            _patient = new PatientInputModel();
            _identityFieldsDisabled = false;""",
"""            _patient = new PatientInputModel();
            _phoneDisplay = "";
            _phoneCountryCode = "+90";
            _identityFieldsDisabled = false;""")

c = c.replace("""        _patient = new();
        _identity = new();
        _result = null;""",
"""        _patient = new();
        _identity = new();
        _phoneDisplay = "";
        _phoneCountryCode = "+90";
        _result = null;""")

# 7. Add HTML Modal at bottom
modal_html = """
@if (_detayModalAcik)
{
    <div class="audit-modal-backdrop" @onclick="ModalKapat">
        <div class="audit-modal-panel" @onclick:stopPropagation>

            @if (_detayYukleniyor)
            {
                <div style="text-align:center;padding:60px;">
                    <div class="spinner" style="margin:0 auto 16px;"></div>
                    <p style="color:var(--text-muted);">Detaylar yükleniyor…</p>
                </div>
            }
            else if (_seciliDetay is not null)
            {
                var pr = _seciliDetay.PredictionResponse;
                var pi = _seciliDetay.PatientInput;

                <div class="audit-modal-header">
                    <div>
                        <h3 style="font-size:18px;font-weight:700;color:var(--text-primary);margin:0;">
                            Değerlendirme Detayı
                        </h3>
                        <p style="font-size:12px;color:var(--text-muted);margin:4px 0 0;">
                            Tarih: @(DateTime.TryParse(pr.Timestamp, out var dt) ? dt.ToString("dd.MM.yyyy HH:mm") : pr.Timestamp)
                            &nbsp;·&nbsp; @(string.IsNullOrEmpty(pr.ModelVersiyonu) ? "Model: —" : $"Model {pr.ModelVersiyonu}")
                        </p>
                    </div>
                    <button type="button" class="btn btn-ghost btn-sm" @onclick="ModalKapat">✕</button>
                </div>

                <div class="audit-section">
                    <div class="audit-section-title"><i class="ph-bold ph-heartbeat"></i> Hasta Parametreleri</div>
                    <div class="audit-params-grid">
                        <div class="audit-param-item">
                            <span class="audit-param-label">PASI Skoru</span>
                            <span class="audit-param-value">@(pi.PasiSkoru?.ToString("F1"))</span>
                        </div>
                        <div class="audit-param-item">
                            <span class="audit-param-label">VKİ</span>
                            <span class="audit-param-value">@(pi.Vki?.ToString("F1")) kg/m²</span>
                        </div>
                        <div class="audit-param-item">
                            <span class="audit-param-label">LDL</span>
                            <span class="audit-param-value">@(pi.Ldl?.ToString("F0")) mg/dL</span>
                        </div>
                        @if (pi.Dlqi.HasValue) {
                            <div class="audit-param-item"><span class="audit-param-label">DLQI</span><span class="audit-param-value">@pi.Dlqi.Value.ToString("F0")</span></div>
                        }
                        @if (pi.Bsa.HasValue) {
                            <div class="audit-param-item"><span class="audit-param-label">BSA</span><span class="audit-param-value">%@pi.Bsa.Value.ToString("F0")</span></div>
                        }
                    </div>
                </div>

                <div class="audit-section">
                    <div class="audit-section-title"><i class="ph-bold ph-robot"></i> Yapay Zeka Kararları</div>
                    <div class="result-grid">
                        @foreach (var card in BuildLabelCards(pr))
                        {
                            <div class="result-card @(card.Karar ? "positive" : "negative")">
                                <div class="result-card-header" style="margin-bottom:8px;">
                                    <span class="result-card-icon">@LabelIcon(card.Key)</span>
                                    <span class="result-badge @(card.Karar ? "badge-yes" : "badge-no")">
                                        @(card.Karar ? "ÖNERİLİYOR" : "GEREKLİ DEĞİL")
                                    </span>
                                </div>
                                <div class="result-card-title" style="font-size:13px;margin-bottom:8px;">@card.GoruntuAdi</div>
                                <div class="prob-row">
                                    <div class="prob-bar-bg" style="height:6px;"><div class="prob-bar-fill @(card.Karar ? "positive-fill" : "negative-fill")" style="width:@(card.OlasilikYuzde)%"></div></div>
                                    <span class="prob-label" style="font-size:11px;">%@card.OlasilikYuzde</span>
                                </div>
                            </div>
                        }
                    </div>
                </div>
            }
        </div>
    </div>
}
<style>
    .audit-modal-backdrop {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(4, 9, 15, 0.85); backdrop-filter: blur(4px);
        display: flex; align-items: center; justify-content: center;
        z-index: 1000; padding: 20px;
    }
    .audit-modal-panel {
        background: var(--bg-card, #0a131e); border: 1px solid var(--border, #1e2d3d);
        border-radius: 12px; width: 100%; max-width: 600px; max-height: 90vh;
        overflow-y: auto; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
    }
    .audit-modal-header {
        display: flex; justify-content: space-between; align-items: flex-start;
        padding: 16px 24px; border-bottom: 1px solid var(--border, #1e2d3d);
    }
    .audit-section {
        padding: 20px 24px; border-bottom: 1px solid var(--border, #1e2d3d);
    }
    .audit-section:last-of-type { border-bottom: none; }
    .audit-section-title {
        font-size: 13px; font-weight: 600; color: var(--text-muted);
        text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 14px;
    }
    .audit-params-grid {
        display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px;
    }
    .audit-param-item {
        background: var(--bg-primary, #0d1a27); border: 1px solid var(--border, #1e2d3d);
        border-radius: 8px; padding: 10px 14px; display: flex; flex-direction: column; gap: 4px;
    }
    .audit-param-label { font-size: 11px; color: var(--text-muted); font-weight: 500; }
    .audit-param-value { font-size: 15px; font-weight: 700; color: var(--text-primary); }
</style>
"""

c += modal_html

with open("cdss_web/Components/Pages/Predict.razor", "w") as f:
    f.write(c)
