using System;
using System.IO;
using System.Text.Json;
using cdss_web.Models;

public class Program {
    public static void Main() {
        try {
            var json = File.ReadAllText("../test_resp.json");
            var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
            var result = JsonSerializer.Deserialize<AuditLogDetailResponse>(json, options);
            Console.WriteLine("Success! " + result.PatientInput.HastaAdi);
        } catch (Exception ex) {
            Console.WriteLine(ex.ToString());
        }
    }
}
