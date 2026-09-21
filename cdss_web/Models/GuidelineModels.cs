using System.Text.Json.Serialization;
using System.Collections.Generic;

namespace cdss_web.Models;

// ─── İstek ───────────────────────────────────────────────────────────────────

public record GuidelineQueryRequest(
    [property: JsonPropertyName("soru")]           string Soru,
    [property: JsonPropertyName("kaynak_filtre")]  List<string>? KaynakFiltre = null
);

// ─── Yanıt ───────────────────────────────────────────────────────────────────

public record GuidelineQueryResponse(
    [property: JsonPropertyName("cevap")]               string Cevap,
    [property: JsonPropertyName("kaynaklar")]           List<GuidelineSource>? Kaynaklar,
    [property: JsonPropertyName("bulunamadi")]          bool Bulunamadi,
    [property: JsonPropertyName("fallback_kullanildi")] bool FallbackKullanildi,
    [property: JsonPropertyName("islem_suresi_ms")]     double IslemSuresiMs
);

public record GuidelineSource(
    [property: JsonPropertyName("kaynak_kodu")]    string KaynakKodu,
    [property: JsonPropertyName("display_source")] string DisplaySource,
    [property: JsonPropertyName("sayfa")]          int Sayfa,
    [property: JsonPropertyName("bolum")]          string Bolum,
    [property: JsonPropertyName("alinti")]         string Alinti
);

// ─── Sohbet Geçmişi (session-local, DB'ye yazılmaz) ─────────────────────────

public record ChatMessage(
    string Role,        // "user" | "assistant"
    string Text,
    List<GuidelineSource>? Sources = null,
    bool IsError = false,
    bool IsLoading = false,
    double IslemSuresiMs = 0
);
