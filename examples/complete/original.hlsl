Texture2D<float4> tex : register(t0);
SamplerState samp : register(s0);
cbuffer Material : register(b0)
{
    float2x2 _UVTransform;
    float3 _LightColors[2];
    float4 _BaseColor;
    float _RimStrength;
    float _Cutoff;
};
struct PSInput
{
    float2 uv : TEXCOORD0;
    float3 normalWS : NORMAL0;
    float3 viewWS : TEXCOORD1;
};
void ReadLights(out float3 lights[2])
{
    lights[0] = _LightColors[0];
    lights[1] = _LightColors[1];
}
void BuildSurface(PSInput input, float2 uv, out float3 color, float gain = _RimStrength)
{
    float3 n = normalize(input.normalWS);
    float3 v = normalize(input.viewWS);
    float3 lights[2];
    ReadLights(lights);
    color = 0.0;
    for (uint i = 0u; i < 2u; ++i)
    {
        float2 shifted = uv + float2((float)i, 0.0);
        float2 gradient = ddx(shifted);
        color += lights[i] * saturate(n.z)
            + float3(gradient, 0.0) * (0.25 + 0.25 * (float)i);
    }
    float edge = 1.0 - saturate(dot(n, v));
    color += edge * edge * gain;
}
float4 main(PSInput input) : SV_Target
{
    float2 uv = mul(_UVTransform, input.uv);
    float4 sampled = tex.Sample(samp, uv);
    clip(sampled.a - _Cutoff);
    float3 lighting;
    BuildSurface(input, uv, lighting);
    return float4(sampled.rgb * _BaseColor.rgb * lighting, sampled.a * _BaseColor.a);
}
