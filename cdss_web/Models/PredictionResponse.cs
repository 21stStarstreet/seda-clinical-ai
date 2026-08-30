using System.Text.Json.Serialization;

namespace cdss_web.Models;

// ─── /predict yanıtı ──────────────────────────────────────────────────────────

public record LabelDetail(
    [property: JsonPropertyName("karar")]       bool Karar,
    [property: JsonPropertyName("olasilik")]    double Olasilik,
    [property: JsonPropertyName("goruntu_adi")] string GoruntuAdi
);

public record ShapFactor(
    [property: JsonPropertyName("ozellik")]      string Ozellik,
    [property: JsonPropertyName("ozellik_kodu")] string OzellikKodu,
    [property: JsonPropertyName("shap_degeri")]  double ShapDegeri,
    [property: JsonPropertyName("etki")]         string Etki
);

public record ShapExplanation(
    [property: JsonPropertyName("label_adi")]      string LabelAdi,
    [property: JsonPropertyName("base_value")]     double BaseValue,
    [property: JsonPropertyName("top_faktorler")]  List<ShapFactor> TopFaktorler
);

public record PredictionResponse(
    [property: JsonPropertyName("hasta_id")]          string HastaId,
    [property: JsonPropertyName("tahmin")]            Dictionary<string, LabelDetail>? Tahmin,
    [property: JsonPropertyName("aktif_birimler")]    List<string>? AktifBirimler,
    [property: JsonPropertyName("shap_aciklamalari")] Dictionary<string, ShapExplanation>? ShapAciklamalari,
    [property: JsonPropertyName("llm_aciklamasi")]    string? LlmAciklamasi,
    [property: JsonPropertyName("llm_ozet")]          string? LlmOzet,
    [property: JsonPropertyName("llm_fallback_used")] bool LlmFallbackUsed,
    [property: JsonPropertyName("model_versiyonu")]   string? ModelVersiyonu,
    [property: JsonPropertyName("islem_suresi_ms")]   double? IslemSuresiMs,
    [property: JsonPropertyName("audit_id")]          int AuditId
);

// ─── /health yanıtı ───────────────────────────────────────────────────────────

public record HealthResponse(
    [property: JsonPropertyName("status")]           string Status,
    [property: JsonPropertyName("model_yuklendi")]   bool ModelYuklendi,
    [property: JsonPropertyName("model_versiyonu")]  string? ModelVersiyonu,
    [property: JsonPropertyName("llm_aktif")]        bool LlmAktif
);

// ─── /audit/logs yanıtı ───────────────────────────────────────────────────────

public record AuditTahmin(
    [property: JsonPropertyName("ftr")]              bool Ftr,
    [property: JsonPropertyName("aile_hekimligi")]   bool AileHekimligi,
    [property: JsonPropertyName("sistemik_tedavi")]  bool SistemikTedavi
);

public record AuditLogEntry(
    [property: JsonPropertyName("id")]               int Id,
    [property: JsonPropertyName("timestamp")]        string Timestamp,
    [property: JsonPropertyName("hasta_id")]         string? HastaId,
    [property: JsonPropertyName("hasta_adi")]        string? HastaAdi,
    [property: JsonPropertyName("model_version")]    string ModelVersion,
    [property: JsonPropertyName("tahmin")]           AuditTahmin? Tahmin,
    [property: JsonPropertyName("processing_time_ms")] double? ProcessingTimeMs
);

public record AuditLogsResponse(
    [property: JsonPropertyName("logs")] List<AuditLogEntry> Logs
);

public record AuditLogDetailResponse(
    [property: JsonPropertyName("patient_input")] PatientInputModel PatientInput,
    [property: JsonPropertyName("prediction_response")] PredictionResponse PredictionResponse
);

// ─── UI yardımcı modeller ─────────────────────────────────────────────────────

/// <summary>Label kartı için görüntüleme verileri.</summary>
public class LabelCardModel
{
    public string Key { get; init; } = "";
    public string GoruntuAdi { get; init; } = "";
    public bool Karar { get; init; }
    public double Olasilik { get; init; }

    /// <summary>
    /// Modelin VERDİĞİ kararın güven yüzdesi.
    /// Öğrenme notu: Model her zaman pozitif sınıf olasılığı (p) döndürür.
    ///   - Karar = true  (gerekli)       → güven = p
    ///   - Karar = false (gerekmez)      → güven = 1 - p
    /// Böylece "GEREKLİ DEĞİL %97" gösteriyoruz, yanıltıcı "%3" değil.
    /// </summary>
    public int OlasilikYuzde => Karar
        ? (int)Math.Round(Olasilik * 100)
        : (int)Math.Round((1 - Olasilik) * 100);
    public List<ShapFactor> TopFaktorler { get; init; } = [];

    /// <summary>SHAP çubuğu için maksimum mutlak değer (normalize etmek için).</summary>
    public double MaxAbsShap => TopFaktorler.Count > 0
        ? TopFaktorler.Max(f => Math.Abs(f.ShapDegeri))
        : 1.0;

    public int ShapBarWidth(ShapFactor f) =>
        MaxAbsShap > 0 ? (int)(Math.Abs(f.ShapDegeri) / MaxAbsShap * 100) : 0;
}
