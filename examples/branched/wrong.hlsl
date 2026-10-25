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
float4 main(PSInput input) : SV_Target
{
    float2 uv = input.uv * _UVTransform.xy + _UVTransform.zw;
    bool textured = _UseTexture < 0.5;
    float4 base = textured ? _BaseMap.Sample(sampler_BaseMap, uv) : _Tint;
    float2 dx = ddx(uv);
    float2 dy = ddy(uv);
    float footprint = dot(dx, dx) + dot(dy, dy);
    if (textured && base.a < _Cutoff) discard;
    if (input.uv.y < _Bottom) discard;
    float3 color;
    if (_Mode < 0.5)
        color = base.rgb * _Tint.rgb * 0.5 + base.rgb * _Tint.rgb * footprint;
    else if (_Mode < 1.5)
        color = base.rgb * 0.25 + _Tint.rgb * 0.25 + (base.rgb + _Tint.rgb) * footprint;
    else
        color = lerp(base.rgb, _Tint.rgb, 0.5) + lerp(base.rgb, _Tint.rgb, 0.5) * footprint;
    return float4(color, (textured && _Mode < 1.5) ? base.a : _Tint.a);
}
