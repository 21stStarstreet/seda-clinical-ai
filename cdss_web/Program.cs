using cdss_web.Services;
using Microsoft.AspNetCore.Components.Authorization;
using Microsoft.AspNetCore.Components.Server.ProtectedBrowserStorage;

var builder = WebApplication.CreateBuilder(args);

// ─── Servisler ────────────────────────────────────────────────────────────────
builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();

// ─── Kimlik Doğrulama (Authentication) ───────────────────────────────────────
builder.Services.AddAuthentication(options =>
{
    options.DefaultScheme = "CdssBlazorAuth";
});
builder.Services.AddScoped<AuthenticationStateProvider, CustomAuthStateProvider>();
builder.Services.AddAuthorizationCore();

// PDF Rapor servisi
builder.Services.AddSingleton<PdfReportService>();

// Ortak HttpClient konfigürasyonu
var apiSettings = builder.Configuration.GetSection("ApiSettings");
var baseUrl = apiSettings["BaseUrl"] ?? "http://localhost:8000";

// Auth Provider için HttpClient
builder.Services.AddHttpClient("FastAPI", client =>
{
    client.BaseAddress = new Uri(baseUrl);
    client.Timeout = TimeSpan.FromSeconds(10);
});

// CDSS API Servisi için HttpClient
builder.Services.AddHttpClient<CdssApiService>(client =>
{
    client.BaseAddress = new Uri(baseUrl);
    client.Timeout = TimeSpan.FromSeconds(90);
});


var app = builder.Build();

// ─── Faz 4: Güvenlik / Middleware ─────────────────────────────────────────────
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
    // Strict-Transport-Security header (HTTPS zorunluluğu)
    app.UseHsts();
    // Tüm HTTP isteklerini HTTPS'e yönlendir (Zorunlu Güvenlik)
    app.UseHttpsRedirection();
}

app.UseStaticFiles();
app.UseAntiforgery();

app.MapRazorComponents<cdss_web.Components.App>()
    .AddInteractiveServerRenderMode();

app.Run();
