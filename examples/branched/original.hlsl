Texture2D<float4> _BaseMap : register(t0);
SamplerState sampler_BaseMap : register(s0);
cbuffer UnityPerMaterial : register(b0)
{
    float4 _Tint;
    float4 _UVTransform;
    float _UseTexture;
    float _Mode;
    float _Cutoff;
    float _Bottom;
};
struct PSInput { float2 uv : TEXCOORD0; };
struct Surface { float4 color; bool textured; };
float4 ReadBase(float2 uv, bool enabled)
{
    if (enabled) return _BaseMap.Sample(sampler_BaseMap, uv);
    return _Tint;
}
float3 Shade(Surface surface, float footprint)
{
    if (_Mode < 0.5) return surface.color.rgb * _Tint.rgb * (0.5 + footprint);
    if (_Mode < 1.5) return (surface.color.rgb + _Tint.rgb) * (0.25 + footprint);
    return lerp(surface.color.rgb, _Tint.rgb, 0.5) * (1.0 + footprint);
}
float4 main(PSInput input) : SV_Target
{
    float2 uv = input.uv * _UVTransform.xy + _UVTransform.zw;
    Surface surface;
    surface.textured = _UseTexture > 0.5;
    surface.color = ReadBase(uv, surface.textured);
    float2 dx = ddx(uv);
    float2 dy = ddy(uv);
    float footprint = dot(dx, dx) + dot(dy, dy);
    if (surface.textured)
    {
        if (surface.color.a < _Cutoff) discard;
    }
    if (input.uv.y < _Bottom) discard;
    float3 color = Shade(surface, footprint);
    bool preserveAlpha = surface.textured && _Mode < 1.5;
    float alpha = preserveAlpha ? surface.color.a : _Tint.a;
    return float4(color, alpha);
}
