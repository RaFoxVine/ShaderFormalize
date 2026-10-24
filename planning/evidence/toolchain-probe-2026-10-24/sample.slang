cbuffer Params : register(b0) { float4 tint; float factor; };
Texture2D<float4> colorTexture : register(t0);
SamplerState samplerA : register(s0);
SamplerState samplerB : register(s1);
float4 main(float2 uv : TEXCOORD0) : SV_Target
{
    float4 a = colorTexture.SampleLevel(samplerA, uv, 0.0);
    float4 b = colorTexture.SampleLevel(samplerB, uv, 0.0);
    float3 c = a.rgb * tint.rgb;
    if (factor > 0.0) c += b.rgb * factor;
    return float4(c, 1.0);
}
