import re

with open("cdss_web/Components/Pages/Predict.razor", "r") as f:
    content = f.read()

# 1. Update _lastVisit to _patientVisits
content = content.replace("private PatientVisitSummary? _lastVisit;", "private List<PatientVisitSummary> _patientVisits = new();")

# 2. Update SearchPatientAsync
content = content.replace("_lastVisit = null;", "_patientVisits.Clear();")
content = content.replace(
"""            // Son ziyareti yükle
            var visits = await ApiService.GetPatientVisitsAsync(patient.TcHash);
            _lastVisit = visits.FirstOrDefault();""",
"""            // Tüm ziyaretleri yükle
            _patientVisits = await ApiService.GetPatientVisitsAsync(patient.TcHash);"""
)

# 3. Update ResetForm
content = content.replace("_lastVisit = null;", "_patientVisits.Clear();")

# 4. Update the UI for visits (right panel)
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

content = content.replace(old_visit_panel, new_visit_panel)

# 5. Add Modal HTML and CSS at the end of the file
modal_code = """
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

content += modal_code

with open("cdss_web/Components/Pages/Predict.razor", "w") as f:
    f.write(content)
