Texture2D<float4> _BaseMap : register(t0);
SamplerState sampler_BaseMap : register(s0);
SamplerState sampler_LinearClamp : register(s1);
cbuffer UnityPerMaterial : register(b0)
{
    float4 _Tint;
    float4 _UVTransform;
    float _Cutoff;
    float _Bottom;
    float _Mip;
    float _DetailStrength;
};
struct PSInput { float2 uv : TEXCOORD0; };
struct Surface { float4 base; float2 gradientX; float2 gradientY; };
float2 TransformUV(float2 uv) { return uv * _UVTransform.xy + _UVTransform.zw; }
Surface ReadSurface(float2 uv)
{
    Surface surface;
    surface.base = _BaseMap.Sample(sampler_BaseMap, uv);
    surface.gradientX = ddx(uv);
    surface.gradientY = ddy(uv);
    return surface;
}
void ApplyCutout(float alpha, float height)
{
    clip(alpha - _Cutoff);
    if (height < _Bottom) discard;
}
float4 Shade(Surface surface, float2 uv)
{
    float4 detail = _BaseMap.SampleLevel(sampler_BaseMap, uv, _Mip);
    float4 filtered = _BaseMap.SampleGrad(sampler_BaseMap, uv, surface.gradientX, surface.gradientY);
    float3 base = surface.base.rgb * _Tint.rgb;
    float3 extra = (detail.rgb + filtered.rgb) * _DetailStrength;
    float footprint = dot(surface.gradientX, surface.gradientX) + dot(surface.gradientY, surface.gradientY);
    float3 color = (base + extra) * (0.5 + footprint);
    return float4(color, surface.base.a * _Tint.a);
}
float4 main(PSInput input) : SV_Target
{
    float2 uv = TransformUV(input.uv);
    Surface surface = ReadSurface(uv);
    ApplyCutout(surface.base.a, input.uv.y);
    return Shade(surface, uv);
}
