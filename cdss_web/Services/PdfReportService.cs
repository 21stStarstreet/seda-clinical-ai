using QuestPDF.Fluent;
using QuestPDF.Helpers;
using QuestPDF.Infrastructure;
using cdss_web.Models;

namespace cdss_web.Services;

public class PdfReportService
{
    static PdfReportService()
    {
        QuestPDF.Settings.License = LicenseType.Community;
    }

    // ── Renk Paleti ──────────────────────────────────────────────────────────
    private const string AccentBlue  = "#4F46E5";
    private const string AccentGreen = "#059669";
    private const string AccentRed   = "#DC2626";
    private const string TextDark    = "#111827";
    private const string TextMid     = "#374151";
    private const string TextLight   = "#9CA3AF";
    private const string BgGray      = "#F3F4F6";
    private const string BorderColor = "#E5E7EB";
    private const string BgBlue      = "#EEF2FF";

    public byte[] GenerateReport(PredictionResponse result, PatientInputModel patient, string doktorAdi)
    {
        var doc = Document.Create(container =>
        {
            container.Page(page =>
            {
                page.Size(PageSizes.A4);
                page.Margin(36);
                page.DefaultTextStyle(x => x.FontFamily("Arial").FontSize(9.5f).FontColor(TextDark));
                page.Header().Element(c => BuildHeader(c, result));
                page.Content().PaddingTop(14).Column(col =>
                {
                    col.Spacing(10);
                    BuildPatientInfo(col, result, patient, doktorAdi);
                    
                    if (patient.PasiSkoru > 20)
                    {
                        BuildUrgencyAlert(col);
                    }

                    BuildInputParameters(col, patient);
                    // BuildDecisions(col, result); // Kullanıcı isteği üzerine gizlendi
                    BuildShapAndExplanation(col, result);
                    BuildDisclaimer(col);
                });
                page.Footer().Element(BuildFooter);
            });
        });
        return doc.GeneratePdf();
    }

    // ── HEADER ───────────────────────────────────────────────────────────────
    private void BuildHeader(IContainer c, PredictionResponse result)
    {
        c.Column(col =>
        {
            // Üst bant: tam genişlik mavi çizgi
            col.Item().Height(4).Background(AccentBlue);
            col.Item().PaddingTop(10).PaddingBottom(10).Row(row =>
            {
                row.RelativeItem().Column(inner =>
                {
                    inner.Item().Text("KLİNİK KARAR RAPORU")
                        .Bold().FontSize(16).FontColor(TextDark);
                    inner.Item().PaddingTop(2).Text("Psoriazis • CDSS Otomatik Sevk Yönlendirmesi")
                        .FontSize(9).FontColor(TextLight);
                });
                row.ConstantItem(140).AlignRight().Column(inner =>
                {
                    inner.Item().Text(DateTime.Now.ToString("dd.MM.yyyy  HH:mm"))
                        .FontSize(9).FontColor(TextMid);
                    inner.Item().PaddingTop(3).Text("KLİNİK KULLANIM")
                        .Bold().FontSize(8).FontColor(AccentRed);
                });
            });
            col.Item().Height(1).Background(BorderColor);
        });
    }

    // ── FOOTER ───────────────────────────────────────────────────────────────
    private void BuildFooter(IContainer c)
    {
        c.PaddingTop(6).Row(row =>
        {
            row.RelativeItem().Text("Bu rapor yapay zeka destekli CDSS tarafından otomatik üretilmiştir. Klinik karar hekimin sorumluluğundadır.")
                .FontSize(7.5f).FontColor(TextLight);
            row.ConstantItem(60).AlignRight().Text(text =>
            {
                text.Span("Sayfa ").FontSize(7.5f).FontColor(TextLight);
                text.CurrentPageNumber().FontSize(7.5f).FontColor(TextLight);
                text.Span(" / ").FontSize(7.5f).FontColor(TextLight);
                text.TotalPages().FontSize(7.5f).FontColor(TextLight);
            });
        });
    }

    // ── HASTA BİLGİLERİ ──────────────────────────────────────────────────────
    private void BuildPatientInfo(ColumnDescriptor col, PredictionResponse result,
        PatientInputModel patient, string doktorAdi)
    {
        col.Item().Background(BgGray).Padding(12).Row(row =>
        {
            row.RelativeItem().Column(c =>
            {
                c.Item().Text("Hasta Bilgileri").Bold().FontSize(8).FontColor(TextLight);
                c.Item().PaddingTop(6).Row(r =>
                {
                    r.ConstantItem(110).Text("Hasta Adı").FontSize(9).FontColor(TextLight);
                    r.RelativeItem().Text(string.IsNullOrWhiteSpace(patient.HastaAdi) ? "Belirtilmemiş" : patient.HastaAdi).Bold().FontSize(9);
                });
                c.Item().PaddingTop(3).Row(r =>
                {
                    r.ConstantItem(110).Text("Hasta ID").FontSize(9).FontColor(TextLight);
                    r.RelativeItem().Text(MaskHastaId(result.HastaId)).FontSize(9);
                });
                c.Item().PaddingTop(3).Row(r =>
                {
                    r.ConstantItem(110).Text("Hekim").FontSize(9).FontColor(TextLight);
                    r.RelativeItem().Text(doktorAdi).Bold().FontSize(9);
                });
                c.Item().PaddingTop(3).Row(r =>
                {
                    r.ConstantItem(110).Text("Tarih").FontSize(9).FontColor(TextLight);
                    r.RelativeItem().Text(DateTime.Now.ToString("dd MMMM yyyy, HH:mm",
                        new System.Globalization.CultureInfo("tr-TR"))).FontSize(9);
                });
            });

            row.ConstantItem(1).Background(BorderColor);
            row.ConstantItem(8);

            row.RelativeItem().Column(c =>
            {
                c.Item().Text("Sistem Bilgileri").Bold().FontSize(8).FontColor(TextLight);
                c.Item().PaddingTop(6).Row(r =>
                {
                    r.ConstantItem(110).Text("Model").FontSize(9).FontColor(TextLight);
                    r.RelativeItem().Text($"CDSS v{result.ModelVersiyonu}").Bold().FontSize(9);
                });
                c.Item().PaddingTop(3).Row(r =>
                {
                    r.ConstantItem(110).Text("Audit ID").FontSize(9).FontColor(TextLight);
                    r.RelativeItem().Text($"#{result.AuditId}").Bold().FontSize(9);
                });
                c.Item().PaddingTop(3).Row(r =>
                {
                    r.ConstantItem(110).Text("İşlem Süresi").FontSize(9).FontColor(TextLight);
                    r.RelativeItem().Text($"{result.IslemSuresiMs:F1} ms").FontSize(9);
                });
            });
        });
    }

    private void BuildUrgencyAlert(ColumnDescriptor col)
    {
        col.Item().Background("#FEF2F2").BorderLeft(4).BorderColor(AccentRed).Padding(12).Column(c =>
        {
            c.Item().Text("ACİL DERMATOLOJİ UYARISI").Bold().FontSize(12).FontColor(AccentRed);
            c.Item().PaddingTop(4).Text("Hastanın PASI skoru oldukça yüksek (>20). Eritrodermik veya çok şiddetli psoriazis şüphesi olabilir. Acil tıbbi müdahale ve/veya sistemik tedaviye hızlı başlangıç gerekebilir. Lütfen hastayı önceliklendiriniz.")
                .FontSize(9).FontColor(TextDark);
        });
    }

    // ── KLİNİK GİRDİ PARAMETRELERİ ──────────────────────────────────────────
    private void BuildInputParameters(ColumnDescriptor col, PatientInputModel patient)
    {
        col.Item().Column(section =>
        {
            SectionLabel(section, "Klinik Girdi Parametreleri");
            section.Item().Table(table =>
            {
                table.ColumnsDefinition(c =>
                {
                    c.RelativeColumn(3);
                    c.RelativeColumn(2);
                    c.RelativeColumn(3);
                });

                // Header
                table.Header(h =>
                {
                    foreach (var title in new[] { "Parametre", "Değer", "Klinik Yorum" })
                    {
                        h.Cell().Background(AccentBlue).PaddingVertical(6).PaddingHorizontal(8)
                            .Text(title).Bold().FontSize(9).FontColor("#FFFFFF");
                    }
                });

                // Satırlar
                int idx = 0;
                void Row(string p, string v, string y)
                {
                    var bg = idx++ % 2 == 0 ? "#FFFFFF" : BgGray;
                    foreach (var txt in new[] { (p, false), (v, true), (y, false) })
                    {
                        var cell = table.Cell().Background(bg)
                            .BorderBottom(1).BorderColor(BorderColor)
                            .PaddingVertical(5).PaddingHorizontal(8)
                            .Text(txt.Item1).FontSize(9);
                        if (txt.Item2) cell.Bold();
                    }
                }

                Row("PASI Skoru", patient.PasiSkoru.HasValue ? $"{patient.PasiSkoru.Value:F1}" : "—", patient.PasiSkoru.HasValue ? InterpretPasi(patient.PasiSkoru.Value) : "Girilmedi");
                Row("Psoriazis Tipi", patient.PsoriazisTipi ?? "Plak", "—");
                Row("VKİ (kg/m²)", patient.Vki.HasValue ? $"{patient.Vki.Value:F1}" : "—", patient.Vki.HasValue ? InterpretVki(patient.Vki.Value) : "Girilmedi");
                Row("LDL Kolesterol (mg/dL)", patient.Ldl.HasValue ? $"{patient.Ldl.Value:F0}" : "—", patient.Ldl.HasValue ? InterpretLdl(patient.Ldl.Value) : "Girilmedi");
                if (patient.Dlqi.HasValue)
                    Row("DLQI Skoru", $"{patient.Dlqi:F0}", InterpretDlqi(patient.Dlqi.Value));
                if (patient.Bsa.HasValue)
                    Row("BSA (%)", $"{patient.Bsa:F1}", InterpretBsa(patient.Bsa.Value));
                if (patient.Yas.HasValue)
                    Row("Yaş", $"{patient.Yas}", "—");
                Row("Tırnak Tutulumu", patient.TirnakTutulumu ? "Var" : "Yok", "—");
                Row("Sabah Tutukluğu >30dk", patient.SabahTuruklugu30dk ? "Var" : "Yok", "—");
                Row("Aktif Sigara", patient.Sigara ? "Evet" : "Hayır", "—");
            });
        });
    }

    // ── YAPAY ZEKA KARARLARI ─────────────────────────────────────────────────
    private void BuildDecisions(ColumnDescriptor col, PredictionResponse result)
    {
        col.Item().Column(section =>
        {
            SectionLabel(section, "Yapay Zeka Sevk Kararları");
            section.Item().Row(row =>
            {
                var order = new[] { "ftr", "aile_hekimligi", "sistemik_tedavi" };
                var tahmin = result.Tahmin ?? new();
                foreach (var key in order)
                {
                    if (!tahmin.TryGetValue(key, out var d)) continue;

                    var isYes = d.Karar;
                    var borderCol = isYes ? AccentGreen : BorderColor;
                    var badgeBg   = isYes ? AccentGreen : "#6B7280";
                    var badgeTxt  = isYes ? "ÖNERİLİYOR" : "GEREKLİ DEĞİL";
                    var bgColor   = isYes ? "#F0FDF4" : "#FFFFFF";

                    row.RelativeItem()
                        .Border(1.5f).BorderColor(borderCol)
                        
                        .Background(bgColor)
                        .Padding(10)
                        .Column(card =>
                        {
                            // Badge
                            card.Item().Row(r =>
                            {
                                r.AutoItem()
                                    .Background(badgeBg)
                                    .PaddingHorizontal(6).PaddingVertical(2)
                                    .Text(badgeTxt).Bold().FontSize(7.5f).FontColor("#FFFFFF");
                            });
                            // Başlık
                            card.Item().PaddingTop(6)
                                .Text(d.GoruntuAdi).Bold().FontSize(10).FontColor(TextDark);
                            // Güven: kararın güveni (pozitif için p, negatif için 1-p)
                            var guven = d.Karar
                                ? (int)(d.Olasilik * 100)
                                : (int)((1 - d.Olasilik) * 100);
                            card.Item().PaddingTop(4)
                                .Text($"Güven: %{guven}")
                                .FontSize(9).FontColor(TextMid);
                        });

                    row.ConstantItem(6);
                }
            });
        });
    }

    // ── SHAP + LLM AÇIKLAMA (Görsel Barlar) ──────────────────────────────────
    private const string ShapPositive = "#059669";
    private const string ShapNegative = "#DC2626";

    private void BuildShapAndExplanation(ColumnDescriptor col, PredictionResponse result)
    {
        var order  = new[] { "ftr", "aile_hekimligi", "sistemik_tedavi" };
        var shapMap = result.ShapAciklamalari ?? new();

        bool herhangiShapVar = order.Any(k =>
            shapMap.TryGetValue(k, out var s) && s.TopFaktorler.Count > 0);

        if (herhangiShapVar)
        {
            col.Item().Column(section =>
            {
                SectionLabel(section, "Yapay Zeka Karar Analizi — SHAP Faktör Grafikleri");

                // Üç karar kartı yan yana
                section.Item().Row(row =>
                {
                    bool ilk = true;
                    foreach (var key in order)
                    {
                        var tahmin = result.Tahmin ?? new();
                        if (!tahmin.TryGetValue(key, out var d)) continue;
                        if (!shapMap.TryGetValue(key, out var shap) || shap.TopFaktorler.Count == 0)
                            continue;

                        if (!ilk) row.ConstantItem(6);
                        ilk = false;

                        var isYes     = d.Karar;
                        var borderCol = isYes ? AccentGreen : "#D1D5DB";
                        var badgeBg   = isYes ? AccentGreen : "#6B7280";
                        var badgeTxt  = isYes ? "ÖNERİLİYOR" : "GEREKLİ DEĞİL";
                        var cardBg    = isYes ? "#F0FDF4" : "#FAFAFA";
                        var guven     = isYes
                            ? (int)(d.Olasilik * 100)
                            : (int)((1 - d.Olasilik) * 100);

                        // Max mutlak SHAP değeri — bar normalize etmek için
                        var maxAbs = shap.TopFaktorler.Max(f => Math.Abs(f.ShapDegeri));
                        if (maxAbs == 0) maxAbs = 1;

                        row.RelativeItem()
                            .Border(1).BorderColor(borderCol)
                            .Background(cardBg)
                            .Padding(8)
                            .Column(card =>
                            {
                                // Badge
                                card.Item().Row(r =>
                                {
                                    r.AutoItem()
                                        .Background(badgeBg)
                                        .PaddingHorizontal(5).PaddingVertical(2)
                                        .Text(badgeTxt).Bold().FontSize(6.5f).FontColor("#FFFFFF");
                                });

                                // Birim adı
                                card.Item().PaddingTop(5)
                                    .Text(d.GoruntuAdi).Bold().FontSize(8.5f).FontColor(TextDark);

                                // Olasılık barı
                                card.Item().PaddingTop(4).Column(pb =>
                                {
                                    pb.Item().Row(r =>
                                    {
                                        r.RelativeItem().Text("Güven").FontSize(7f).FontColor(TextLight);
                                        r.AutoItem().Text($"%{guven}").Bold().FontSize(7.5f)
                                            .FontColor(isYes ? AccentGreen : "#6B7280");
                                    });
                                    // Zemin (gri)
                                    pb.Item().PaddingTop(2).Height(7).Background("#E5E7EB")
                                        .AlignLeft().Row(r =>
                                        {
                                            // Dolu kısım (yüzde üzerinden orantılı bar)
                                            if (guven > 0)
                                            {
                                                r.RelativeItem(guven).Background(isYes ? AccentGreen : "#6B7280");
                                                if (guven < 100)
                                                    r.RelativeItem(100 - guven).Background("#E5E7EB");
                                            }
                                        });
                                });

                                // SHAP faktör barları
                                card.Item().PaddingTop(8)
                                    .Text("Etkili Faktörler").FontSize(7f).FontColor(TextLight).Bold();

                                foreach (var f in shap.TopFaktorler.Take(5))
                                {
                                    var pos      = f.ShapDegeri >= 0;
                                    var barColor = pos ? ShapPositive : ShapNegative;
                                    // Bar genişliği: 0–100 arası yüzde
                                    var barPercent = (float)(Math.Abs(f.ShapDegeri) / maxAbs * 100);

                                    card.Item().PaddingTop(4).Column(fb =>
                                    {
                                        // Faktör adı + değer
                                        fb.Item().Row(r =>
                                        {
                                            r.RelativeItem().Text(f.Ozellik)
                                                .FontSize(7.5f).FontColor(TextMid);
                                            r.AutoItem()
                                                .Text($"{(pos ? "▲" : "▼")} {Math.Abs(f.ShapDegeri):F3}")
                                                .FontSize(7.5f).FontColor(barColor);
                                        });
                                        // Zemin çubuğu (gri) — dolu bar içinde
                                        fb.Item().PaddingTop(1.5f).Height(5).Background("#E5E7EB")
                                            .AlignLeft().Row(r =>
                                            {
                                                if (barPercent > 0)
                                                {
                                                    r.RelativeItem(barPercent).Background(barColor);
                                                    if (barPercent < 100)
                                                        r.RelativeItem(100 - barPercent).Background("#E5E7EB");
                                                }
                                            });
                                    });
                                }
                            });
                    }
                });
            });
        }

        // LLM Açıklama — Klinik Karar Epikrizi Kartları (Web Arayüzüyle Birebir Eşleşen Tasarım)
        if (!string.IsNullOrWhiteSpace(result.LlmAciklamasi))
        {
            col.Item().PaddingTop(4).Column(section =>
            {
                SectionLabel(section, "Klinik Karar Epikrizi (Yapay Zeka Patofizyolojik Değerlendirmesi)");

                var rawText = result.LlmAciklamasi.Trim();
                var paragraphs = rawText.Split(new[] { "\n\n", "\r\n\r\n" }, StringSplitOptions.RemoveEmptyEntries);

                foreach (var para in paragraphs)
                {
                    var trimmed = para.Trim();
                    if (string.IsNullOrWhiteSpace(trimmed)) continue;

                    string title = "Klinik Değerlendirme";
                    string content = trimmed;
                    string borderColor = "#0D9488"; // varsayılan teal
                    string titleColor = "#0F766E";
                    string bgColor = "#F0FDFA";

                    // Başlık ayrıştırma (**Başlık:**)
                    if (trimmed.StartsWith("**") && trimmed.Contains("**"))
                    {
                        var firstEnd = trimmed.IndexOf("**", 2);
                        if (firstEnd > 2)
                        {
                            title = trimmed.Substring(2, firstEnd - 2).Trim().TrimEnd(':');
                            content = trimmed.Substring(firstEnd + 2).Trim().TrimStart(':').Trim();
                        }
                    }

                    var lowerTitle = title.ToLowerInvariant();

                    if (lowerTitle.Contains("fizik tedavi") || lowerTitle.Contains("ftr") || lowerTitle.Contains("romatoloji") && !lowerTitle.Contains("önerilmeme") && !lowerTitle.Contains("değerlendirmesi"))
                    {
                        borderColor = "#0891B2"; // Cyan
                        titleColor = "#0E7490";
                        bgColor = "#F0FDFA";
                    }
                    else if (lowerTitle.Contains("sistemik") || lowerTitle.Contains("biyolojik") || lowerTitle.Contains("tedavi planlama"))
                    {
                        borderColor = "#7C3AED"; // Purple
                        titleColor = "#6D28D9";
                        bgColor = "#FAF5FF";
                    }
                    else if (lowerTitle.Contains("aile hekimliği") && !lowerTitle.Contains("önerilmeme"))
                    {
                        borderColor = "#059669"; // Emerald
                        titleColor = "#047857";
                        bgColor = "#F0FDF4";
                    }
                    else if (lowerTitle.Contains("önerilmeme") || lowerTitle.Contains("gerekçe") || lowerTitle.Contains("öncelikli değil") || lowerTitle.Contains("fototerapi") || lowerTitle.Contains("romatoloji"))
                    {
                        borderColor = "#64748B"; // Slate / Neutral
                        titleColor = "#475569";
                        bgColor = "#F8FAFC";
                    }

                    section.Item().PaddingTop(5).BorderLeft(3).BorderColor(borderColor)
                        .Background(bgColor)
                        .Padding(9)
                        .Column(card =>
                        {
                            card.Item().Text(title).Bold().FontSize(8.5f).FontColor(titleColor);
                            card.Item().PaddingTop(3).Text(content)
                                .FontSize(8.5f).LineHeight(1.45f).FontColor(TextDark);
                        });
                }
            });
        }
    }

    // ── YASAL UYARI ───────────────────────────────────────────────────────────
    private void BuildDisclaimer(ColumnDescriptor col)
    {
        col.Item()
            .BorderLeft(3).BorderColor(AccentRed)
            .PaddingLeft(10).PaddingVertical(8)
            .Column(c =>
            {
                c.Item().Text("Yasal Uyarı").Bold().FontSize(8.5f).FontColor(AccentRed);
                c.Item().PaddingTop(3).Text(
                    "Bu rapor yalnızca yardımcı niteliktedir. Nihai klinik karar ve sorumluluk ilgili hekime aittir. " +
                    "KVKK kapsamında korunmakta olup yetkisiz kişilerle paylaşılmamalıdır.")
                    .FontSize(8).FontColor(TextMid).LineHeight(1.4f);
            });
    }

    // ── YARDIMCI: Bölüm Başlığı (ince çizgi + küçük label) ──────────────────
    private static void SectionLabel(ColumnDescriptor col, string label)
    {
        col.Item().PaddingBottom(5).Row(row =>
        {
            row.AutoItem().PaddingRight(8)
                .Text(label).Bold().FontSize(8.5f).FontColor(TextLight);
            row.RelativeItem().AlignMiddle()
                .Height(1).Background(BorderColor);
        });
    }

    // ── YARDIMCI: Hasta ID Maskeleme ─────────────────────────────────────────
    private static string MaskHastaId(string? id)
    {
        if (string.IsNullOrEmpty(id)) return "—";
        if (id.Length <= 4) return id;
        return id[..2] + new string('*', Math.Max(1, id.Length - 4)) + id[^2..];
    }

    // ── Klinik Yorumlar ───────────────────────────────────────────────────────
    private static string InterpretPasi(double v) => v switch
    {
        <= 5  => "Hafif psoriazis",
        <= 10 => "Orta şiddetli",
        _     => "Şiddetli (eşik: >10)"
    };

    private static string InterpretVki(double v) => v switch
    {
        < 18.5 => "Zayıf",
        < 25   => "Normal",
        < 30   => "Fazla kilolu",
        < 35   => "Obez I (eşik: >30)",
        _      => "Obez II"
    };

    private static string InterpretLdl(double v) => v switch
    {
        < 100 => "Optimal",
        < 130 => "Normal üst sınır",
        < 160 => "Yüksek (eşik: >130)",
        _     => "Çok yüksek"
    };

    private static string InterpretDlqi(double v) => v switch
    {
        <= 1  => "Etki yok",
        <= 5  => "Küçük etki",
        <= 10 => "Orta etki",
        _     => "Çok büyük etki (eşik: >10)"
    };

    private static string InterpretBsa(double v) => v switch
    {
        < 3  => "Sınırlı tutulum",
        < 10 => "Orta tutulum",
        _    => "Yaygın (eşik: >10)"
    };
}
