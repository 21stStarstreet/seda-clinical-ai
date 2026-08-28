using System.ComponentModel.DataAnnotations;
using System.Text.Json.Serialization;

namespace cdss_web.Models;

/// <summary>
/// Hasta kimlik bilgileri modeli (TC tabanlı arama ve kayıt için).
/// Klinik parametreler değil — sadece kişisel veriler.
/// </summary>
public class PatientIdentityModel
{
    [Required(ErrorMessage = "TC Kimlik No zorunludur.")]
    [StringLength(11, MinimumLength = 11, ErrorMessage = "TC Kimlik No 11 haneli olmalıdır.")]
    [RegularExpression(@"^\d{11}$", ErrorMessage = "TC Kimlik No yalnızca rakamlardan oluşmalıdır.")]
    [JsonPropertyName("tc_no")]
    public string TcNo { get; set; } = string.Empty;

    [Required(ErrorMessage = "Ad Soyad zorunludur.")]
    [StringLength(150, MinimumLength = 2, ErrorMessage = "Ad Soyad 2-150 karakter olmalıdır.")]
    [JsonPropertyName("ad_soyad")]
    public string AdSoyad { get; set; } = string.Empty;

    [JsonPropertyName("dogum_tarihi")]
    public string? DogumTarihi { get; set; }  // YYYY-MM-DD

    [JsonPropertyName("cinsiyet")]
    public string? Cinsiyet { get; set; }

    [JsonPropertyName("telefon")]
    public string? Telefon { get; set; }

    [JsonPropertyName("kan_grubu")]
    public string? KanGrubu { get; set; }

    [JsonPropertyName("ilk_tani_tarihi")]
    public string? IlkTaniTarihi { get; set; }  // YYYY-MM-DD

    [JsonPropertyName("hekim_notu")]
    public string? HekimNotu { get; set; }
}

/// <summary>
/// API'den dönen hasta kaydı.
/// </summary>
public class PatientResponse
{
    [JsonPropertyName("tc_hash")]
    public string TcHash { get; set; } = string.Empty;

    [JsonPropertyName("tc_masked")]
    public string TcMasked { get; set; } = string.Empty;

    [JsonPropertyName("ad_soyad")]
    public string AdSoyad { get; set; } = string.Empty;

    [JsonPropertyName("dogum_tarihi")]
    public string? DogumTarihi { get; set; }

    [JsonPropertyName("cinsiyet")]
    public string? Cinsiyet { get; set; }

    [JsonPropertyName("telefon")]
    public string? Telefon { get; set; }

    [JsonPropertyName("kan_grubu")]
    public string? KanGrubu { get; set; }

    [JsonPropertyName("ilk_tani_tarihi")]
    public string? IlkTaniTarihi { get; set; }

    [JsonPropertyName("hekim_notu")]
    public string? HekimNotu { get; set; }

    [JsonPropertyName("kayit_tarihi")]
    public string KayitTarihi { get; set; } = string.Empty;
}

/// <summary>
/// Hasta ziyaret özeti (sağ panel için).
/// </summary>
public class PatientVisitSummary
{
    [JsonPropertyName("id")]
    public int Id { get; set; }

    [JsonPropertyName("timestamp")]
    public string Timestamp { get; set; } = string.Empty;

    [JsonPropertyName("model_version")]
    public string ModelVersion { get; set; } = string.Empty;

    [JsonPropertyName("tahmin")]
    public TahminSummary Tahmin { get; set; } = new();

    [JsonPropertyName("olasiliklar")]
    public OlasilikSummary Olasiliklar { get; set; } = new();

    [JsonPropertyName("processing_time_ms")]
    public double? ProcessingTimeMs { get; set; }
}

public class TahminSummary
{
    [JsonPropertyName("ftr")]
    public bool Ftr { get; set; }

    [JsonPropertyName("aile_hekimligi")]
    public bool AileHekimligi { get; set; }

    [JsonPropertyName("sistemik_tedavi")]
    public bool SistemikTedavi { get; set; }
}

public class OlasilikSummary
{
    [JsonPropertyName("ftr")]
    public double Ftr { get; set; }

    [JsonPropertyName("aile_hekimligi")]
    public double AileHekimligi { get; set; }

    [JsonPropertyName("sistemik_tedavi")]
    public double SistemikTedavi { get; set; }
}

public class PatientVisitsResponse
{
    [JsonPropertyName("tc_hash")]
    public string TcHash { get; set; } = string.Empty;

    [JsonPropertyName("visits")]
    public List<PatientVisitSummary> Visits { get; set; } = new();
}
