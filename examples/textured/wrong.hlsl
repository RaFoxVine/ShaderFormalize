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
void KeepSurface(float alpha, float height)
{
    clip(alpha - _Cutoff - 0.2);
    if (height < _Bottom) { discard; }
    return;
}
float4 main(PSInput input) : SV_Target
{
    float2 uv = input.uv * _UVTransform.xy + _UVTransform.zw;
    float4 base = _BaseMap.Sample(sampler_BaseMap, uv);
    float2 dx = ddx(uv);
    float2 dy = ddy(uv);
    KeepSurface(base.a, input.uv.y);
    float4 detail = _BaseMap.SampleLevel(sampler_BaseMap, uv, _Mip);
    float4 filtered = _BaseMap.SampleGrad(sampler_BaseMap, uv, dx, dy);
    float footprint = dot(dx, dx) + dot(dy, dy);
    float3 color = base.rgb * _Tint.rgb * 0.5 + base.rgb * _Tint.rgb * footprint;
    color += detail.rgb * _DetailStrength * 0.5 + filtered.rgb * _DetailStrength * 0.5;
    color += (detail.rgb + filtered.rgb) * _DetailStrength * footprint;
    return float4(color, base.a * _Tint.a);
}
