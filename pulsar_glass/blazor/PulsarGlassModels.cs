namespace PulsarGlass.Blazor;

/// <summary>
/// Pulsar Glass size variants
/// </summary>
public enum PulsarGlassSize
{
    Small,
    Default,
    Large
}

/// <summary>
/// Optional item model for convenience
/// </summary>
public record SegmentOption(string Value, string Text, string? Icon = null);
