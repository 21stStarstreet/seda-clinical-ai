using System.Net.Http.Json;
using System.Text.Json;
using cdss_web.Models;
using Microsoft.AspNetCore.Components.Server.ProtectedBrowserStorage;
using System.Net.Http.Headers;

namespace cdss_web.Services;

/// <summary>
/// FastAPI CDSS backend ile HTTP iletişimi.
/// Faz 4: JWT token ile güvenli istek atar.
/// Tüm API hataları Türkçe mesajlara dönüştürülür.
/// </summary>
public class CdssApiService
{
    private readonly HttpClient _http;
    private readonly ProtectedSessionStorage _sessionStorage;

    private static readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    public CdssApiService(HttpClient http, ProtectedSessionStorage sessionStorage)
    {
        _http = http;
        _sessionStorage = sessionStorage;
    }

    // ─── Authorization Header Yardımcısı ─────────────────────────────────────

    private async Task<HttpRequestMessage> CreateRequestAsync(HttpMethod method, string endpoint)
    {
        var request = new HttpRequestMessage(method, endpoint);
        try
        {
            var result = await _sessionStorage.GetAsync<AuthSession>("cdss_auth_session");
            if (result.Success && result.Value != null && !string.IsNullOrEmpty(result.Value.Token))
                request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", result.Value.Token);
        }
        catch { /* Prerendering sırasında JS kullanılamıyorsa sessizce devam et */ }
        return request;
    }

    // ─── Merkezi HTTP Hata Çözümleme ──────────────────────────────────────────
    /// <summary>
    /// HTTP durum kodunu Türkçe, klinisyen dostu bir mesaja çevirir.
    /// Tüm servis metodları bu yardımcıyı kullanır — tutarlı hata deneyimi sağlanır.
    /// </summary>
    private static string HttpHatasiniCevir(System.Net.HttpStatusCode statusCode, string? body = null)
    {
        return statusCode switch
        {
            System.Net.HttpStatusCode.Unauthorized =>
                "Oturum süreniz dolmuş ya da geçersiz. Lütfen tekrar giriş yapın.",
            System.Net.HttpStatusCode.Forbidden =>
                "Bu işlem için yetkiniz bulunmuyor.",
            System.Net.HttpStatusCode.NotFound =>
                "İstenen kayıt bulunamadı.",
            System.Net.HttpStatusCode.TooManyRequests =>
                "Çok fazla istek gönderildi. Lütfen 1 dakika bekleyip tekrar deneyin.",
            System.Net.HttpStatusCode.UnprocessableEntity =>
                "Girilen veriler geçersiz. Lütfen tüm alanları kontrol edin.",
            System.Net.HttpStatusCode.InternalServerError =>
                "Sunucu tarafında bir hata oluştu. Sistem yöneticisiyle iletişime geçin.",
            System.Net.HttpStatusCode.ServiceUnavailable =>
                "Yapay zeka servisi şu an kullanılamıyor. Lütfen kısa süre sonra tekrar deneyin.",
            _ => $"API yanıt hatası ({(int)statusCode}). Lütfen tekrar deneyin."
        };
    }

    // ─── /predict ─────────────────────────────────────────────────────────────

    public async Task<(PredictionResponse? Result, string? Error)> PredictAsync(PatientInputModel patient)
    {
        try
        {
            var request = await CreateRequestAsync(HttpMethod.Post, "/predict");
            request.Content = JsonContent.Create(patient.ToApiPayload());

            var response = await _http.SendAsync(request);

            if (!response.IsSuccessStatusCode)
                return (null, HttpHatasiniCevir(response.StatusCode));

            var result = await response.Content.ReadFromJsonAsync<PredictionResponse>(_jsonOptions);
            return (result, null);
        }
        catch (HttpRequestException)
        {
            return (null, "Bağlantı hatası: API'ye ulaşılamıyor. Sistem yöneticisiyle iletişime geçin.");
        }
        catch (TaskCanceledException)
        {
            return (null, "Zaman aşımı: API 30 saniye içinde yanıt vermedi. Lütfen tekrar deneyin.");
        }
        catch (Exception ex)
        {
            return (null, $"Beklenmeyen hata: {ex.Message}");
        }
    }

    // ─── /health ──────────────────────────────────────────────────────────────

    public async Task<HealthResponse?> GetHealthAsync()
    {
        try
        {
            var response = await _http.SendAsync(new HttpRequestMessage(HttpMethod.Get, "/health"));
            if (!response.IsSuccessStatusCode) return null;
            return await response.Content.ReadFromJsonAsync<HealthResponse>(_jsonOptions);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[Health Check] API'ye ulaşılamıyor: {ex.Message}");
            return null;
        }
    }

    // ─── /audit/logs ──────────────────────────────────────────────────────────

    public async Task<(List<AuditLogEntry> Loglar, string? Hata)> GetLogsWithErrorAsync(
        int limit = 50, string? hastaId = null)
    {
        try
        {
            var endpoint = $"/audit/logs?limit={limit}";
            if (!string.IsNullOrWhiteSpace(hastaId))
                endpoint += $"&hasta_id={Uri.EscapeDataString(hastaId)}";

            var request = await CreateRequestAsync(HttpMethod.Get, endpoint);
            var response = await _http.SendAsync(request);

            if (!response.IsSuccessStatusCode)
                return ([], HttpHatasiniCevir(response.StatusCode));

            var result = await response.Content.ReadFromJsonAsync<AuditLogsResponse>(_jsonOptions);
            return (result?.Logs ?? [], null);
        }
        catch (HttpRequestException)
        {
            return ([], "Bağlantı hatası: Geçmiş kararlar yüklenemedi. API'ye ulaşılamıyor.");
        }
        catch (Exception ex)
        {
            return ([], $"Beklenmeyen hata: {ex.Message}");
        }
    }

    /// <summary>Geriye dönük uyumluluk için — hata durumunda boş liste döner.</summary>
    public async Task<List<AuditLogEntry>> GetLogsAsync(int limit = 50, string? hastaId = null)
    {
        var (loglar, _) = await GetLogsWithErrorAsync(limit, hastaId);
        return loglar;
    }

    // ─── /audit/logs/{id} ─────────────────────────────────────────────────────

    public async Task<(AuditLogDetailResponse? Detay, string? Hata)> GetLogDetailWithErrorAsync(int logId)
    {
        try
        {
            var request = await CreateRequestAsync(HttpMethod.Get, $"/audit/logs/{logId}");
            var response = await _http.SendAsync(request);

            if (!response.IsSuccessStatusCode)
                return (null, HttpHatasiniCevir(response.StatusCode));

            var detay = await response.Content.ReadFromJsonAsync<AuditLogDetailResponse>(_jsonOptions);
            return (detay, null);
        }
        catch (HttpRequestException)
        {
            return (null, "Bağlantı hatası: Karar detayı yüklenemedi.");
        }
        catch (Exception ex)
        {
            return (null, $"Beklenmeyen hata: {ex.Message}");
        }
    }

    /// <summary>Geriye dönük uyumluluk için — hata durumunda null döner.</summary>
    public async Task<AuditLogDetailResponse?> GetLogDetailAsync(int logId)
    {
        var (detay, _) = await GetLogDetailWithErrorAsync(logId);
        return detay;
    }

    // ─── Hasta Kimlik API Metodları ───────────────────────────────────────────

    /// <summary>TC Kimlik No ile hasta ara. Bulunamazsa null döner.</summary>
    public async Task<(PatientResponse? Patient, string? Error)> SearchPatientAsync(string tcNo)
    {
        try
        {
            var req = await CreateRequestAsync(HttpMethod.Get, $"/patients/search?tc={Uri.EscapeDataString(tcNo)}");
            var res = await _http.SendAsync(req);
            if (res.StatusCode == System.Net.HttpStatusCode.NotFound)
                return (null, null); // Hasta bulunamadı — hata değil
            if (!res.IsSuccessStatusCode)
            {
                var body = await res.Content.ReadAsStringAsync();
                return (null, HttpHatasiniCevir(res.StatusCode, body));
            }
            var patient = await res.Content.ReadFromJsonAsync<PatientResponse>(_jsonOptions);
            return (patient, null);
        }
        catch (HttpRequestException)
        {
            return (null, "Bağlantı hatası: Hasta aranamadı.");
        }
    }

    /// <summary>Yeni hasta kaydı oluştur.</summary>
    public async Task<(PatientResponse? Patient, string? Error)> CreatePatientAsync(PatientIdentityModel model)
    {
        try
        {
            var req = await CreateRequestAsync(HttpMethod.Post, "/patients/");
            req.Content = JsonContent.Create(model, options: _jsonOptions);
            var res = await _http.SendAsync(req);
            if (!res.IsSuccessStatusCode)
            {
                var body = await res.Content.ReadAsStringAsync();
                return (null, HttpHatasiniCevir(res.StatusCode, body));
            }
            var patient = await res.Content.ReadFromJsonAsync<PatientResponse>(_jsonOptions);
            return (patient, null);
        }
        catch (HttpRequestException)
        {
            return (null, "Bağlantı hatası: Hasta kaydedilemedi.");
        }
    }

    /// <summary>Hastanın tüm ziyaret geçmişini getir.</summary>
    public async Task<List<PatientVisitSummary>> GetPatientVisitsAsync(string tcHash)
    {
        try
        {
            var req = await CreateRequestAsync(HttpMethod.Get, $"/patients/{tcHash}/visits");
            var res = await _http.SendAsync(req);
            if (!res.IsSuccessStatusCode) return new();
            var result = await res.Content.ReadFromJsonAsync<PatientVisitsResponse>(_jsonOptions);
            return result?.Visits ?? new();
        }
        catch
        {
            return new();
        }
    }

    // ─── /guideline-query ─────────────────────────────────────────────────────

    /// <summary>
    /// Klinik kılavuz soru-cevap. RAG mimarisi (ChromaDB + Gemini).
    /// Two-Stage Query Processing: sorgu zenginleştirme + sohbet bağlamı.
    /// Returns: (response, errorMessage)
    /// </summary>
    public async Task<(GuidelineQueryResponse? Result, string? Error)> QueryGuidelineAsync(
        string soru,
        List<string>? kaynakFiltre = null,
        List<ConversationTurn>? gecmis = null)
    {
        try
        {
            var body = new GuidelineQueryRequest(soru, kaynakFiltre, gecmis);
            var request = await CreateRequestAsync(HttpMethod.Post, "/guideline-query");
            request.Content = JsonContent.Create(body);

            var response = await _http.SendAsync(request);

            if (!response.IsSuccessStatusCode)
            {
                var body2 = await response.Content.ReadAsStringAsync();
                return (null, HttpHatasiniCevir(response.StatusCode, body2));
            }

            var result = await response.Content.ReadFromJsonAsync<GuidelineQueryResponse>(_jsonOptions);
            return (result, null);
        }
        catch (Exception ex)
        {
            return (null, $"Bağlantı hatası: {ex.Message}");
        }
    }
}
