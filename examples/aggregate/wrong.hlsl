cbuffer Material : register(b0)
{
    float2x2 _ColorMix;
    float3 _LightColors[2];
    float4 _BaseColor;
    float _RimStrength;
};
struct PSInput
{
    float3 normalWS : NORMAL0;
    float3 viewWS : TEXCOORD0;
};
float4 main(PSInput input) : SV_Target
{
    float3 n = normalize(input.normalWS);
    float3 v = normalize(input.viewWS);
    float edge = 1.0 - saturate(dot(n, v));
    float3 lighting = _LightColors[0] * saturate(n.z)
        + _LightColors[1] * 0.125 + _RimStrength * (edge * edge);
    float red = _ColorMix[0][0] * lighting.x + _ColorMix[0][0] * lighting.y;
    float green = _ColorMix[1][0] * lighting.x + _ColorMix[1][1] * lighting.y;
    return float4(red * _BaseColor.r, green * _BaseColor.g,
        lighting.z * _BaseColor.b, _BaseColor.a);
}
