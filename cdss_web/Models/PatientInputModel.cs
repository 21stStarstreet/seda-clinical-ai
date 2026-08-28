using System.ComponentModel.DataAnnotations;
using System.Text.Json.Serialization;

namespace cdss_web.Models;

/// <summary>
/// Hasta formu için giriş modeli.
/// DataAnnotations ile anlık Blazor validasyonu sağlar.
/// </summary>
public class PatientInputModel
{
    [Required(ErrorMessage = "Hasta Adı zorunludur.")]
    [StringLength(100, ErrorMessage = "Hasta Adı en fazla 100 karakter olabilir.")]
    [JsonPropertyName("hasta_adi")]
    public string HastaAdi { get; set; } = string.Empty;

    // Sistem tarafından otomatik oluşturulacak ID (Girdi olarak alınmaz)
    [JsonPropertyName("hasta_id")]
    public string HastaId { get; set; } = $"PSO-{DateTime.Now:yyyyMMdd}-{Guid.NewGuid().ToString()[..4].ToUpper()}";

    [Required(ErrorMessage = "Psoriazis Tipi zorunludur.")]
    [JsonPropertyName("psoriazis_tipi")]
    public string PsoriazisTipi { get; set; } = "Plak";

    // ── v1.0 — Binary Alanlar ──────────────────────────────────────────────────
    [JsonPropertyName("tirnak_tutulumu")]
    public bool TirnakTutulumu { get; set; } = false;
    [JsonPropertyName("sabah_turuklugu_30dk")]
    public bool SabahTuruklugu30dk { get; set; } = false;
    [JsonPropertyName("sigara")]
    public bool Sigara { get; set; } = false;

    // ── v1.0 — Sayısal Alanlar ────────────────────────────────────────────────
    [Required(ErrorMessage = "VKİ değeri zorunludur.")]
    [Range(10.0, 80.0, ErrorMessage = "VKİ 10–80 arasında olmalıdır (kg/m²).")]
    [JsonPropertyName("vki")]
    public double? Vki { get; set; }

    [Required(ErrorMessage = "LDL değeri zorunludur.")]
    [Range(0.0, 500.0, ErrorMessage = "LDL 0–500 arasında olmalıdır (mg/dL).")]
    [JsonPropertyName("ldl")]
    public double? Ldl { get; set; }

    [Required(ErrorMessage = "PASI skoru zorunludur.")]
    [Range(0.0, 72.0, ErrorMessage = "PASI skoru 0–72 arasında olmalıdır.")]
    [JsonPropertyName("pasi_skoru")]
    public double? PasiSkoru { get; set; }

    // ── v2.0 — Opsiyonel Alanlar (boş bırakılabilir) ──────────────────────────
    [Range(0.0, 30.0, ErrorMessage = "DLQI 0–30 arasında olmalıdır.")]
    [JsonPropertyName("dlqi")]
    public double? Dlqi { get; set; }

    [Range(0.0, 100.0, ErrorMessage = "BSA 0–100 arasında olmalıdır.")]
    [JsonPropertyName("bsa")]
    public double? Bsa { get; set; }

    [Range(0, 120, ErrorMessage = "Yaş 0–120 arasında olmalıdır.")]
    [JsonPropertyName("yas")]
    public int? Yas { get; set; }

    [JsonPropertyName("patient_tc_hash")]
    public string? PatientTcHash { get; set; }

    /// <summary>FastAPI'nin beklediği snake_case JSON formatına dönüştür.</summary>
    public Dictionary<string, object?> ToApiPayload() => new()
    {
        ["hasta_id"]              = HastaId,
        ["hasta_adi"]             = HastaAdi,
        ["patient_tc_hash"]       = PatientTcHash,
        ["psoriazis_tipi"]        = PsoriazisTipi,
        ["tirnak_tutulumu"]       = TirnakTutulumu,
        ["sabah_turuklugu_30dk"]  = SabahTuruklugu30dk,
        ["vki"]                   = Vki,
        ["ldl"]                   = Ldl,
        ["pasi_skoru"]            = PasiSkoru,
        ["sigara"]                = Sigara,
        ["dlqi"]                  = Dlqi,
        ["bsa"]                   = Bsa,
        ["yas"]                   = Yas,
    };
}
