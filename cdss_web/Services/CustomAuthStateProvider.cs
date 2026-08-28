using Microsoft.AspNetCore.Components.Authorization;
using Microsoft.AspNetCore.Components.Server.ProtectedBrowserStorage;
using System.Security.Claims;
using System.Text.Json;
using System.Net.Http.Headers;
using System.Text;

namespace cdss_web.Services;

/// <summary>
/// Faz 4: Gerçek JWT Tabanlı Kimlik Doğrulama
/// Blazor'un oturum durumunu yönetir ve FastAPI ile konuşur.
/// </summary>
public class CustomAuthStateProvider : AuthenticationStateProvider
{
    private readonly ProtectedSessionStorage _sessionStorage;
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly AuthenticationState _anonim;

    private const string StorageKey = "cdss_auth_session";

    public CustomAuthStateProvider(
        ProtectedSessionStorage sessionStorage,
        IHttpClientFactory httpClientFactory)
    {
        _sessionStorage = sessionStorage;
        _httpClientFactory = httpClientFactory;
        _anonim = new AuthenticationState(new ClaimsPrincipal(new ClaimsIdentity()));
    }

    public override async Task<AuthenticationState> GetAuthenticationStateAsync()
    {
        try
        {
            var result = await _sessionStorage.GetAsync<AuthSession>(StorageKey);

            if (!result.Success || result.Value == null || string.IsNullOrEmpty(result.Value.Token))
                return _anonim;

            var session = result.Value;

            var kimlik = new ClaimsIdentity(new[]
            {
                new Claim(ClaimTypes.Name, session.Username),
                new Claim(ClaimTypes.Role, session.Role),
            }, "CdssJwtAuth");

            return new AuthenticationState(new ClaimsPrincipal(kimlik));
        }
        catch
        {
            return _anonim;
        }
    }

    public async Task<bool> GirisYapAsync(string kullaniciAdi, string sifre)
    {
        try
        {
            var client = _httpClientFactory.CreateClient("FastAPI");

            // OAuth2 Form-Data oluştur
            var requestContent = new StringContent(
                $"grant_type=password&username={Uri.EscapeDataString(kullaniciAdi)}&password={Uri.EscapeDataString(sifre)}",
                Encoding.UTF8,
                "application/x-www-form-urlencoded"
            );

            var response = await client.PostAsync("/token", requestContent);

            if (!response.IsSuccessStatusCode)
            {
                return false;
            }

            var responseBody = await response.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(responseBody);
            
            var token = doc.RootElement.GetProperty("access_token").GetString();
            var role = doc.RootElement.GetProperty("role").GetString();
            var user = doc.RootElement.GetProperty("username").GetString();

            if (token == null || role == null || user == null) return false;

            var session = new AuthSession
            {
                Token = token,
                Username = user,
                Role = role
            };

            // Güvenli şekilde tarayıcıya kaydet
            await _sessionStorage.SetAsync(StorageKey, session);

            // Blazor'u güncelle
            var kimlik = new ClaimsIdentity(new[]
            {
                new Claim(ClaimTypes.Name, user),
                new Claim(ClaimTypes.Role, role),
            }, "CdssJwtAuth");

            NotifyAuthenticationStateChanged(
                Task.FromResult(new AuthenticationState(new ClaimsPrincipal(kimlik)))
            );

            return true;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[GirisYapAsync Hata] {ex.Message}");
            return false;
        }
    }

    public async Task CikisYapAsync()
    {
        try
        {
            // Kara listeye almak için FastAPI'ye /logout çağrısı atıyoruz
            var result = await _sessionStorage.GetAsync<AuthSession>(StorageKey);
            if (result.Success && result.Value != null && !string.IsNullOrEmpty(result.Value.Token))
            {
                var client = _httpClientFactory.CreateClient("FastAPI");
                var request = new HttpRequestMessage(HttpMethod.Post, "/logout");
                request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", result.Value.Token);
                await client.SendAsync(request);
            }
        }
        catch { /* Çıkış API'sinde hata olsa bile oturumu kapat */ }
        finally
        {
            await _sessionStorage.DeleteAsync(StorageKey);
            NotifyAuthenticationStateChanged(Task.FromResult(_anonim));
        }
    }
}

// Oturum veri modeli
public class AuthSession
{
    public string Token { get; set; } = "";
    public string Username { get; set; } = "";
    public string Role { get; set; } = "";
}
