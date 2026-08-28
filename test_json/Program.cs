using System;
using System.Text.Json;
public class Model { public int? Yas { get; set; } }
public class Program {
    public static void Main() {
        try {
            var m = JsonSerializer.Deserialize<Model>("{\"Yas\": 20.0}", new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
            Console.WriteLine("Success: " + m.Yas);
        } catch(Exception e) {
            Console.WriteLine("Error: " + e.Message);
        }
    }
}
